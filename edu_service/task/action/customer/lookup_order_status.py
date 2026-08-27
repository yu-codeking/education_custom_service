from typing import Any

from edu_service.domain.state import DialogueState
from edu_service.task.action.base import Action, ActionResult
from edu_service.task.action.customer.shared import (
    find_order_by_no,
    get_order_detail,
    get_order_items,
    order_status_name,
)


def _build_order_summary(detail: dict[str, Any], item_name: str | None) -> str:
    parts: list[str] = []
    if item_name:
        parts.append(f"报名课程：{item_name}")
    paid_amount = detail.get("paidAmount")
    payable_amount = detail.get("payableAmount")
    if paid_amount not in (None, "", 0):
        parts.append(f"实付金额 ¥{paid_amount}")
    elif payable_amount not in (None, ""):
        parts.append(f"应付金额 ¥{payable_amount}")
    payment_summary = detail.get("paymentSummary") or {}
    if payment_summary.get("paidAt"):
        parts.append(f"支付时间 {payment_summary['paidAt']}")
    refund_summary = detail.get("refundSummary") or {}
    if refund_summary.get("refundRequestCount"):
        parts.append(f"已有 {refund_summary['refundRequestCount']} 笔退款记录，退款 ¥{refund_summary.get('refundAmount', 0)}")
    return "。".join(parts) + ("。" if parts else "")


class ActionLookupOrderStatus(Action):
    name = "action_lookup_order_status"

    async def run(self, action_kwargs: dict[str, Any], state: DialogueState) -> ActionResult:
        """
        职责：根据订单号查询订单状态与报名信息（订单号 → 订单ID → 详情/明细）
        """
        order_number = str(state.active_task.slots.get("order_number") or "").strip()

        order_brief = await find_order_by_no(order_number, state)
        if order_brief is None:
            return ActionResult(updated_slots={
                "order_number": order_number,
                "order_status": "未找到",
                "order_summary": "没有查到这个订单号对应的订单，麻烦核对一下是不是输错了～",
            })

        detail = await get_order_detail(order_brief.get("orderId"), state) or {}
        items = await get_order_items(order_brief.get("orderId"), state)
        item_name = str(items[0].get("itemName")) if items else None

        status_text = order_status_name(detail.get("orderStatusCode") or order_brief.get("orderStatusCode"))

        return ActionResult(updated_slots={
            "order_number": str(order_brief.get("orderNo") or order_number),
            "order_status": status_text,
            "order_summary": _build_order_summary(detail, item_name),
        })
