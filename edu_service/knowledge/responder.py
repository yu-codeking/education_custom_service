from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from edu_service.chat_history.builder import ChatHistoryBuilder
from edu_service.domain.messages import BotMessage
from edu_service.domain.state import DialogueState
from edu_service.infrastructure.llm_client import llm_client
from edu_service.knowledge.provider.provider import KnowledgeChunk
from edu_service.prompt.loader import load_prompt_template_content


class KnowledgeResponder:
    async def response(
        self, knowledge_chunks: list[KnowledgeChunk], state: DialogueState
    ) -> list[BotMessage]:
        # 1. 加载提示词内容
        prompt_template_str = load_prompt_template_content("knowledge_respond")

        # 2. 定义提示词模版对象
        prompt_template = PromptTemplate.from_template(
            template=prompt_template_str, template_format="jinja2"
        )

        # 3. 定义chain
        chain = prompt_template | llm_client | StrOutputParser()

        # 4. 调用链chain
        result = await chain.ainvoke(
            {
                "user_message": ChatHistoryBuilder.build_user_message_str(
                    state.pending_turn.user_message
                ),
                "history": ChatHistoryBuilder.build(
                    state.current_session().turns[-10:]
                ),
                "knowledge_content": "\n\n".join(
                    [chunk.content for chunk in knowledge_chunks]
                ),
            }
        )

        return [BotMessage(text=result)]
