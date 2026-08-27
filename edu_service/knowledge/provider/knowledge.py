import json
from typing import Any

from edu_service.domain.state import DialogueState
from edu_service.knowledge.provider.provider import Provider, KnowledgeChunk
from edu_service.task.action.customer.shared import (
    find_order_by_no,
    get_order_detail,
    get_series_cohorts,
    get_series_detail,
)


class ApiOrderProvider(Provider):
    provider_id = "api.order"

    async def retrival(self, state: DialogueState) -> list[KnowledgeChunk]:
        """
        职责：基于当前聚焦的订单卡片调用订单接口，把订单实时数据作为知识内容返回
        """
        focused_object = state.focused_object
        order_brief = await find_order_by_no(focused_object.id, state)
        if order_brief is None:
            return [KnowledgeChunk(content=f"未查到订单 {focused_object.id} 的信息")]

        detail = await get_order_detail(order_brief.get("orderId"), state) or {}
        text = json.dumps(detail, ensure_ascii=False, indent=2, default=str)
        return [KnowledgeChunk(content=f"订单实时信息（订单号 {focused_object.id}）：\n{text}")]


class ApiCourseProvider(Provider):
    provider_id = "api.course"

    async def retrival(self, state: DialogueState) -> list[KnowledgeChunk]:
        """
        职责：基于当前聚焦的课程卡片调用课程接口，把课程与班次实时数据作为知识内容返回
        """
        focused_object = state.focused_object
        series_id = focused_object.id

        detail = await get_series_detail(series_id, state)
        if detail is None:
            # 卡片 id 可能传的是课程名，兜底按关键词搜索
            from edu_service.task.action.customer.shared import search_series
            rows = await search_series(str(series_id), state)
            detail = await get_series_detail(rows[0].get("seriesId"), state) if rows else None
        if detail is None:
            return [KnowledgeChunk(content=f"未查到课程 {series_id} 的信息")]
        cohorts = await get_series_cohorts(detail.get("seriesId"), state)

        payload: dict[str, Any] = {"course": detail, "cohorts": cohorts[:5]}
        text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        return [KnowledgeChunk(content=f"课程实时信息：\n{text}")]


class RagDefaultProvider(Provider):
    provider_id = "rag.default"

    async def retrival(self, state: DialogueState) -> list[KnowledgeChunk]:
        """
        调用知识库（TODO） 自行接入

        """
        return [KnowledgeChunk(content="未检索到相关信息")]


class FaqDefaultProvider(Provider):
    provider_id = "faq.default"

    async def retrival(self, state: DialogueState) -> list[KnowledgeChunk]:
        """
        调用常见问题集文档（TODO） 自行接入【语义检索：向量化】

        """
        return [KnowledgeChunk(content="未检索到相关问题")]
