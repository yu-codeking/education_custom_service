from typing import Any

from edu_service.domain.state import DialogueState
from edu_service.task.action.base import Action, ActionResult
from edu_service.task.action.customer.shared import (
    create_service_ticket,
    find_latest_refund_request,
    find_order_by_no,
    get_order_items,
    get_student_profile,
    normalize_ticket_type,
)

TICKET_TYPE_NAMES = {
    "after_sales": "售后服务",
    "complaint": "投诉",
    "refund": "退费",
}


def _fallback_summary(reason_detail: str) -> str:
    return f"工单暂时没能创建成功：{reason_detail} 你的问题描述我已经记下来了，可以稍后再试，或者让我帮你转人工客服。"


class ActionCreateTicket(Action):
    name = "action_create_ticket"

    async def run(
        self, action_kwargs: dict[str, Any], state: DialogueState
    ) -> ActionResult:
        """
        职责：创建售后/投诉工单（学员档案 + 关联订单明细自动反查，不追问用户）
        """
        slots = state.active_task.slots
        order_number = str(slots.get("order_number") or "").strip()
        description = str(slots.get("problem_description") or "").strip()
        ticket_type = normalize_ticket_type(
            str(slots.get("ticket_type") or "") + description
        )

        profile = await get_student_profile(state)
        if profile is None or profile.get("studentId") is None:
            return ActionResult(
                updated_slots={
                    "ticket_summary": _fallback_summary("当前账号还没有学员档案。")
                }
            )

        order_brief = (
            await find_order_by_no(order_number, state) if order_number else None
        )
        if order_brief is None:
            return ActionResult(
                updated_slots={
                    "ticket_summary": f"没有查到订单 {order_number or '（未提供）'}，工单需要一个有效的关联订单号，麻烦再确认下～",
                }
            )

        items = await get_order_items(order_brief.get("orderId"), state)
        if not items:
            return ActionResult(
                updated_slots={
                    "ticket_summary": _fallback_summary(
                        "该订单下找不到可关联的课程明细。"
                    )
                }
            )

        priority_level = "high" if ticket_type == "complaint" else "medium"

        refund_request_id = None
        if ticket_type == "refund":
            latest_refund = await find_latest_refund_request(state)
            if latest_refund is not None:
                refund_request_id = latest_refund.get("refundRequestId")
            else:
                ticket_type = "after_sales"

        title = (
            description[:20] if description else f"{TICKET_TYPE_NAMES[ticket_type]}工单"
        )
        result = await create_service_ticket(
            ticket_type=ticket_type,
            title=title,
            ticket_content=description or "学员通过智能客服反馈问题",
            student_id=profile.get("studentId"),
            order_item_id=items[0].get("orderItemId"),
            priority_level=priority_level,
            refund_request_id=refund_request_id,
            state=state,
        )

        if result.ok and isinstance(result.data, dict):
            ticket_no = result.data.get("ticketNo")
            type_name = TICKET_TYPE_NAMES[ticket_type]
            return ActionResult(
                updated_slots={
                    "ticket_summary": (
                        f"工单已为你创建！工单编号 {ticket_no}，类型：{type_name}"
                        f"{'（高优先级）' if priority_level == 'high' else ''}，"
                        f"关联课程「{items[0].get('itemName')}」。"
                        "会有专属老师尽快跟进处理，处理进展可以在 App 的我的工单里查看。"
                    ),
                }
            )

        return ActionResult(
            updated_slots={
                "ticket_summary": _fallback_summary(result.message or "服务暂时不可用")
            }
        )
