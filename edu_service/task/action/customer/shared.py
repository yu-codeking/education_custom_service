"""
封装自定义 action 统一访问教育业务数据中台（edu-data FastAPI）的工具函数
约定：
1. 所有请求都需要 X-User-Id 学员身份头（从对话状态 state.user_id 取）
2. 统一响应结构 {code, message, data}，这里归一化成 EduResult
"""

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from edu_service.config.settings import settings
from edu_service.domain.state import DialogueState
from edu_service.infrastructure import http_client


@dataclass(slots=True)
class EduResult:
    """edu-api 调用结果的统一封装"""
    ok: bool
    code: str = ""
    message: str = ""
    data: Any = None


DELIVERY_MODE_NAMES = {
    "online_live": "直播",
    "online_recorded": "录播",
    "offline_face_to_face": "线下面授",
}

ORDER_STATUS_NAMES = {
    "pending": "待支付",
    "paid": "已支付",
    "completed": "已完成",
    "cancelled": "已取消",
    "partial_refunded": "部分退款",
    "refunded": "已退款",
}


def _base_url() -> str:
    """
    职责：获取教育业务中台服务的地址
    """
    return settings.edu_api_base_url.rstrip("/")


def _headers(state: DialogueState) -> dict[str, str]:
    user_id = str(state.user_id) if state.user_id is not None else ""
    return {"X-User-Id": user_id}


async def _request(method: str, path: str, state: DialogueState, body: dict | None = None) -> EduResult:
    """
    职责：发送请求并做错误归一化（网络异常、HTTP 错误、业务错误码都转成 EduResult）
    """
    url = f"{_base_url()}{path}"
    try:
        if method == "GET":
            response = await http_client.http_client.get(url, headers=_headers(state))
        else:
            response = await http_client.http_client.post(url, headers=_headers(state), json=body)
    except Exception:
        return EduResult(ok=False, code="NETWORK_ERROR", message="服务暂时不可用")

    if response.status_code >= 500:
        return EduResult(ok=False, code="SERVER_ERROR", message="服务暂时不可用")

    try:
        payload = response.json()
    except Exception:
        return EduResult(ok=False, code="BAD_RESPONSE", message="服务响应异常")

    result = payload if isinstance(payload, dict) else {}
    # 业务失败示例：{"code": "ORDER_NOT_FOUND", "message": "..."}
    biz_code = str(result.get("code", ""))
    if response.status_code >= 400 or (biz_code and biz_code not in ("0", "ok", "")):
        return EduResult(
            ok=False,
            code=biz_code or f"HTTP_{response.status_code}",
            message=str(result.get("message") or "请求失败"),
            data=result.get("data"),
        )
    return EduResult(ok=True, data=result.get("data"))


def _extract_list(result: EduResult) -> list[dict[str, Any]]:
    if not result.ok or result.data is None:
        return []
    if isinstance(result.data, list):
        return [row for row in result.data if isinstance(row, dict)]
    page = result.data if isinstance(result.data, dict) else {}
    rows = page.get("list")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


#################### 课程域 ####################

async def search_series(keyword: str, state: DialogueState) -> list[dict[str, Any]]:
    rows, page_no = [], 1
    while len(rows) == 0 and page_no <= 3:
        result = await _request("GET", f"/series?keyword={quote(keyword)}&pageNo={page_no}&pageSize=20", state)
        rows = _extract_list(result)
        page_no += 1
    return rows


async def get_series_detail(series_id: int | str, state: DialogueState) -> dict | None:
    result = await _request("GET", f"/series/{series_id}", state)
    return result.data if result.ok and isinstance(result.data, dict) else None


async def get_series_cohorts(series_id: int | str, state: DialogueState) -> list[dict[str, Any]]:
    result = await _request("GET", f"/series/{series_id}/cohorts", state)
    return _extract_list(result)


#################### 订单域 ####################

async def list_my_orders(state: DialogueState, page_size: int = 50) -> list[dict[str, Any]]:
    result = await _request("GET", f"/orders?pageNo=1&pageSize={page_size}", state)
    return _extract_list(result)


async def find_order_by_no(order_no: str, state: DialogueState) -> dict | None:
    """订单号（ORDxxx）→ 订单列表条目：edu-api 以数字 ID 驱动，先按单号在本人订单里反查"""
    orders = await list_my_orders(state)
    wanted = order_no.strip().upper()
    for order in orders:
        if str(order.get("orderNo", "")).upper() == wanted:
            return order
    return None


async def get_order_detail(order_id: int | str, state: DialogueState) -> dict | None:
    result = await _request("GET", f"/orders/{order_id}", state)
    return result.data if result.ok and isinstance(result.data, dict) else None


async def get_order_items(order_id: int | str, state: DialogueState) -> list[dict[str, Any]]:
    result = await _request("GET", f"/orders/{order_id}/items", state)
    return _extract_list(result)


#################### 学习履约域 ####################

async def list_my_cohorts(state: DialogueState, page_size: int = 50) -> list[dict[str, Any]]:
    result = await _request("GET", f"/me/cohorts?pageNo=1&pageSize={page_size}", state)
    return _extract_list(result)


async def find_cohort_by_name(cohort_name: str, state: DialogueState) -> tuple[dict | None, list[dict[str, Any]]]:
    """班次名称模糊匹配：返回（最佳匹配, 我的全部报名），供未命中时给出候选提示"""
    cohorts = await list_my_cohorts(state)
    keyword = cohort_name.strip()
    if not keyword:
        return None, cohorts
    for cohort in cohorts:
        name = str(cohort.get("cohortName", ""))
        series = str(cohort.get("seriesName", ""))
        if keyword in name or keyword in series:
            return cohort, cohorts
    return None, cohorts


async def get_my_progress(cohort_id: int | str, state: DialogueState) -> dict | None:
    result = await _request("GET", f"/me/cohorts/{cohort_id}/progress", state)
    return result.data if result.ok and isinstance(result.data, dict) else None


#################### 用户档案域 ####################

async def get_student_profile(state: DialogueState) -> dict | None:
    result = await _request("GET", "/me/student-profile", state)
    return result.data if result.ok and isinstance(result.data, dict) else None


#################### 售后服务域 ####################

REFUND_TYPE_KEYWORDS = [
    ("duplicate_purchase", ("重复", "买重", "重复购买")),
    ("schedule_conflict", ("冲突", "没时间", "时间不行", "档期", "调不开")),
    ("course_unsatisfied", ("不满意", "太差", "不好", "课程质量", "不适合我", "讲得")),
]


def normalize_refund_type(text: str) -> str:
    """把学员的口语化退款原因归类到 edu-api 的退款类型枚举"""
    content = (text or "").strip()
    for refund_type, words in REFUND_TYPE_KEYWORDS:
        if any(word in content for word in words):
            return refund_type
    return "personal_reason"


async def create_refund_request(order_item_id: int | str,
                                refund_type: str,
                                refund_reason: str,
                                apply_amount: float,
                                state: DialogueState) -> EduResult:
    body = {
        "refundType": refund_type,
        "refundReason": refund_reason,
        "applyAmount": round(float(apply_amount), 2),
    }
    return await _request("POST", f"/order-items/{order_item_id}/refund-requests", state, body)


TICKET_TYPE_KEYWORDS = [
    ("complaint", ("投诉", "举报", "态度差", "不满")),
    ("after_sales", ("售后", "视频", "卡顿", "加载", "播放", "不能看", "打不开", "故障", "异常")),
]


def normalize_ticket_type(text: str) -> str:
    """工单类型归一化：售后 / 投诉 / 退款相关默认登记为售后（退费类优先走退款申请流程）"""
    content = (text or "").strip()
    for ticket_type, words in TICKET_TYPE_KEYWORDS:
        if any(word in content for word in words):
            return ticket_type
    return "after_sales"


async def find_latest_refund_request(state: DialogueState) -> dict | None:
    """退款类工单必须关联退款申请：取本人最近一条退款记录"""
    result = await _request("GET", "/refund-requests?pageNo=1&pageSize=10", state)
    rows = _extract_list(result)
    return rows[0] if rows else None


async def create_service_ticket(ticket_type: str,
                                title: str,
                                ticket_content: str,
                                student_id: int | str,
                                order_item_id: int | str,
                                priority_level: str = "medium",
                                refund_request_id: int | str | None = None,
                                state: DialogueState = None) -> EduResult:
    body: dict[str, Any] = {
        "ticketType": ticket_type,
        "priorityLevel": priority_level,
        "ticketSource": "customer_service",
        "title": title,
        "ticketContent": ticket_content,
        "studentId": student_id,
        "orderItemId": order_item_id,
    }
    if refund_request_id is not None:
        body["refundRequestId"] = refund_request_id
    return await _request("POST", "/service-tickets", state, body)


#################### 文案工具 ####################

def delivery_mode_name(code: Any) -> str:
    return DELIVERY_MODE_NAMES.get(str(code), "线上")


def order_status_name(code: Any) -> str:
    return ORDER_STATUS_NAMES.get(str(code), str(code) or "未知")
