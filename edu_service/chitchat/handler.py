from edu_service.chitchat.responder import ChitChatResponder
from edu_service.domain.messages import BotMessage
from edu_service.domain.state import DialogueState


class ChitChatHandler:

    async def handle(self,
                     chat: str,
                     dialogue_state: DialogueState) -> list[BotMessage]:
        """
        职责：闲聊兜底轨道处理器——交给闲聊响应器生成自然的闲聊回复
        """
        return await ChitChatResponder().response(chat, dialogue_state)
