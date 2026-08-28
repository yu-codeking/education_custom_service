from edu_service.domain.messages import BotMessage
from edu_service.domain.state import DialogueState
from edu_service.knowledge.intents import KnowledgeIntent
from edu_service.knowledge.responder import KnowledgeResponder


class KnowledgeHandler:
    def __init__(
        self, knowledge_intents: dict[str, KnowledgeIntent], knowledge_register
    ):
        self.knowledge_intents = knowledge_intents
        self.knowledge_register = knowledge_register

    async def handle(
        self, intents: list[str], dialogue_state: DialogueState
    ) -> list[BotMessage]:
        """
        职责：知识轨道处理器——按意图逐个调用对应 Provider 检索，再汇总生成自然语言回复
        Args:
            intents: 本轮规划命中的知识意图ID列表
            dialogue_state:

        Returns:

        """
        # 1. 并行收集所有意图命中的知识内容（同一意图可能多个来源：API/FAQ/RAG）
        chunks = []
        for intent_id in intents[:3]:  # 防御性截断：一轮最多处理3个意图
            intent = self.knowledge_intents.get(intent_id)
            if intent is None:
                continue
            for provider_id in intent.provider_ids:
                try:
                    provider = self.knowledge_register.get_provider_by_id(provider_id)
                    provider_chunks = await provider.retrival(dialogue_state)
                except Exception:
                    provider_chunks = []
                chunks.extend(provider_chunks or [])

        # 2. 交给响应器组织自然语言回复
        return await KnowledgeResponder().response(chunks, dialogue_state)
