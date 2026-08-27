from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from edu_service.infrastructure.llm_client import llm_client
from edu_service.chat_history.builder import ChatHistoryBuilder
from edu_service.domain.messages import BotMessage
from edu_service.domain.state import DialogueState
from edu_service.prompt.loader import load_prompt_template_content


class ChitChatResponder:

    async def response(self, chat: str, state: DialogueState) -> list[BotMessage]:
        # 1. 加载提示词内容
        prompt_template_str = load_prompt_template_content("chitchat_respond")

        # 2. 定义提示词模版对象
        prompt_template = PromptTemplate.from_template(template=prompt_template_str, template_format="jinja2")

        # 3. 定义chain
        chain = prompt_template | llm_client | StrOutputParser()

        # 4. 调用链chain
        result = await  chain.ainvoke({
            "user_message": chat,
            "history": ChatHistoryBuilder.build(state.current_session().turns[-10:])
        })

        return [BotMessage(text=result)]
