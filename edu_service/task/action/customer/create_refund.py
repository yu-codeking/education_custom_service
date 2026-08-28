from typing import Any

from edu_service.domain.state import DialogueState
from edu_service.task.action.base import Action, ActionResult
from edu_service.task.action.customer.shared import (
    create_refund_request,
    find_order_by_no,
    get_order_items,
    normalize_refund_type,
)


def _refund_type_name(refund_type: str) -> str:
    return {
        "personal_reason": "个人原因",
        "course_unsatisfied": "课程不满意",
        "schedule_conflict": "时间冲突",
        "duplicate_purchase": "重复购买",
    }.get(refund_type, refund_type)


class ActionCreateRefund(Action):
    name = "action_create_refund"

    async def run(
        self, action_kwargs: dict[str, Any], state: DialogueState
    ) -> ActionResult:
        """
        职责：提交退款申请（订单号 → 可退明细 → 按明细全额金额创建退款单）
        """
        slots = state.active_task.slots
        order_number = str(slots.get("order_number") or "").strip()
        reason = str(slots.get("refund_reason") or "").strip()
        refund_type = normalize_refund_type(
            str(slots.get("refund_type") or "") + reason
        )

        order_brief = await find_order_by_no(order_number, state)
        if order_brief is None:
            return ActionResult(
                updated_slots={
                    "refund_summary": f"没有查到订单 {order_number}，退款申请先没有提交。麻烦确认一下订单号～",
                }
            )

        items = await get_order_items(order_brief.get("orderId"), state)
        refundable = [
            item
            for item in items
            if item.get("orderItemStatusCode") in ("paid", "completed")
        ]
        if not refundable:
            return ActionResult(
                updated_slots={
                    "refund_summary": "这笔订单当前状态不支持退费（只有已支付/已完成的订单才能申请）。"
                    "如果确实需要处理，我可以帮你转人工或提交工单哦。",
                }
            )

        target_item = refundable[0]
        apply_amount = float(target_item.get("payableAmount") or 0)
        result = await create_refund_request(
            order_item_id=target_item.get("orderItemId"),
            refund_type=refund_type,
            refund_reason=reason,
            apply_amount=apply_amount,
            state=state,
        )

        if result.ok and isinstance(result.data, dict):
            refund_no = result.data.get("refundNo")
            return ActionResult(
                updated_slots={
                    "refund_summary": (
                        f"你的退费申请已提交成功！退费单号 {refund_no}，"
                        f"关联课程「{target_item.get('itemName')}」，"
                        f"申请金额 ¥{apply_amount:.2f}，类型：{_refund_type_name(refund_type)}。"
                        "我们会在 1-3 个工作日内完成审核，审核通过后原路退回，请留意短信通知。"
                    ),
                }
            )

        message = result.message or "服务暂时不可用"
        if result.code == "REFUND_IN_PROGRESS":
            message = "这个课程已经有一笔正在处理中的退费申请了，不用重复提交哦。"
        return ActionResult(
            updated_slots={
                "refund_summary": f"退费申请没有提交成功：{message}",
            }
        )
