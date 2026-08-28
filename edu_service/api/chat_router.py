"""
定义路由：聊天接口（非流式 + SSE 流式）与会话管理接口
"""

import asyncio
import json
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from edu_service.api.dependencies import DialogueStateServiceDep
from edu_service.api.schemas import (
    ChatBotMessage,
    ChatObject,
    ChatRequest,
    ChatResponse,
    HistoryMessage,
    SessionCreatedResponse,
    SessionCreateRequest,
    SessionMessagesResponse,
    SessionState,
    TaskContextView,
)
from edu_service.domain.contexts import TaskContext
from edu_service.domain.messages import (
    FocusedObject,
    MessageType,
    ProcessedResult,
    UserMessage,
)
from edu_service.domain.state import DialogueState

router = APIRouter()


#################### 聊天接口 ####################


@router.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(chat_request: ChatRequest, service: DialogueStateServiceDep):
    # 1.将接口数据模型转成领域数据模型
    user_message = _build_user_message(chat_request)

    # 2.调用service处理领域数据模型---返回的还是领域数据模型
    processed_result = await service.process_message(user_message)

    # 3. 将处理后的领域数据 模型转成接口数据模型
    chat_response = _build_chat_response(processed_result)

    # 4. 附带最新会话状态快照，前端可以据此展示当前流程与槽位
    dialogue_state = await service.load_state(chat_request.sender_id)
    chat_response.session_state = _build_session_state(dialogue_state)

    return chat_response


@router.post("/api/chat/stream")
async def chat_stream_endpoint(
    chat_request: ChatRequest, service: DialogueStateServiceDep
):
    """
    SSE 流式响应：meta -> delta(逐段) -> object(卡片) -> done(完整消息+会话状态快照) / error
    """
    return StreamingResponse(
        _stream_chat(chat_request, service),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_chat(chat_request: ChatRequest, service: DialogueStateServiceDep):
    session_id = chat_request.sender_id

    # 1. meta 事件
    yield _sse("meta", {"session_id": session_id})

    try:
        # 2. 走与非流式完全相同的处理链路（保证两种模式语义一致）
        user_message = _build_user_message(chat_request)
        processed_result = await service.process_message(user_message)

        # 3. delta 打字机推送 + 卡片事件
        for bot_message in processed_result.messages:
            text = bot_message.text or ""
            step = 6
            for index in range(0, len(text), step):
                yield _sse("delta", {"text": text[index : index + step]})
                await asyncio.sleep(0.02)
            if bot_message.object is not None:
                yield _sse("object", {"object": _object_payload(bot_message.object)})

        # 4. done 事件：完整回复 + 最新会话状态
        dialogue_state = await service.load_state(session_id)
        yield _sse(
            "done",
            {
                "message_id": processed_result.message_id,
                "messages": [
                    _message_payload(message) for message in processed_result.messages
                ],
                "session_state": _build_session_state(dialogue_state).model_dump(),
            },
        )
    except Exception as error:  # 单次处理失败不影响服务可用性，错误通过 SSE 事件返回
        yield _sse("error", {"message": f"本次处理失败，请稍后重试：{error}"})


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _build_user_message(chat_request: ChatRequest) -> UserMessage:
    """
    职责：接口数据模型转成领域数据模型
    """

    return UserMessage(
        sender_id=chat_request.sender_id,
        message_id=str(uuid.uuid4().hex),
        type=MessageType.OBJECT
        if chat_request.object is not None
        else MessageType.TEXT,
        user_id=chat_request.user_id,
        text=chat_request.text,
        object=FocusedObject(
            id=chat_request.object.id,
            type=chat_request.object.type,
            title=chat_request.object.title,
            attributes=chat_request.object.attributes,
        )
        if chat_request.object is not None
        else None,
    )


def _build_chat_response(processed_result: ProcessedResult) -> ChatResponse:
    """
    职责：处理后的领域数据模型转成接口数据模型
    """

    return ChatResponse(
        message_id=processed_result.message_id,
        messages=[
            ChatBotMessage(
                text=bot_message.text,
                object=_interface_object(bot_message.object),
            )
            for bot_message in processed_result.messages
        ],
    )


def _interface_object(object: FocusedObject | None) -> ChatObject | None:
    if object is None:
        return None
    return ChatObject(
        id=object.id, type=object.type, title=object.title, attributes=object.attributes
    )


def _object_payload(object: FocusedObject) -> dict:
    return {
        "id": object.id,
        "type": object.type,
        "title": object.title,
        "attributes": object.attributes,
    }


def _message_payload(bot_message) -> dict:
    payload = {"text": bot_message.text}
    if bot_message.object is not None:
        payload["object"] = _object_payload(bot_message.object)
    return payload


#################### 会话管理接口 ####################


@router.post("/api/sessions", response_model=SessionCreatedResponse)
async def create_session(
    create_request: SessionCreateRequest, service: DialogueStateServiceDep
):
    """创建新会话：生成 session_id 并初始化持久化状态（支持后续会话恢复）"""
    session_id = uuid.uuid4().hex
    await service.load_state(session_id, ensure=True, user_id=create_request.user_id)
    return SessionCreatedResponse(session_id=session_id, user_id=create_request.user_id)


@router.get("/api/sessions/{session_id}/state", response_model=SessionState)
async def get_session_state(session_id: str, service: DialogueStateServiceDep):
    """获取当前会话状态：激活的任务流程、已收集槽位、暂存任务栈"""
    dialogue_state = await service.load_state(session_id)
    return _build_session_state(dialogue_state)


@router.get(
    "/api/sessions/{session_id}/messages", response_model=SessionMessagesResponse
)
async def get_session_messages(session_id: str, service: DialogueStateServiceDep):
    """获取会话历史消息（跨轮次）"""
    dialogue_state = await service.load_state(session_id)

    messages: list[HistoryMessage] = []
    for session in dialogue_state.sessions:
        for turn in session.turns:
            user_message = turn.user_message
            if user_message.type is MessageType.TEXT:
                messages.append(
                    HistoryMessage(
                        role="user",
                        type="text",
                        text=user_message.text,
                        turn_id=turn.turn_id,
                    )
                )
            elif user_message.object is not None:
                messages.append(
                    HistoryMessage(
                        role="user",
                        type="object",
                        object=_interface_object(user_message.object),
                        turn_id=turn.turn_id,
                    )
                )

            for bot_message in turn.bot_messages:
                messages.append(
                    HistoryMessage(
                        role="bot",
                        type="text",
                        text=bot_message.text,
                        object=_interface_object(bot_message.object),
                        turn_id=turn.turn_id,
                    )
                )

    return SessionMessagesResponse(session_id=session_id, messages=messages)


def _task_context_view(task_context: TaskContext | None) -> TaskContextView | None:
    if task_context is None:
        return None
    return TaskContextView(
        flow_id=task_context.flow_id,
        step_id=task_context.step_id,
        slots=dict(task_context.slots),
    )


def _build_session_state(dialogue_state: DialogueState) -> SessionState:
    system_flow_id = (
        dialogue_state.active_system_task.flow_id
        if dialogue_state.active_system_task is not None
        else None
    )
    focused_object_dict = (
        dialogue_state.focused_object.to_dict()
        if dialogue_state.focused_object is not None
        else None
    )

    return SessionState(
        session_id=dialogue_state.sender_id,
        user_id=dialogue_state.user_id,
        current_session_id=dialogue_state.current_session_id,
        active_task=_task_context_view(dialogue_state.active_task),
        active_system_task_flow_id=system_flow_id,
        paused_tasks=[
            view
            for view in (
                _task_context_view(paused) for paused in dialogue_state.paused_tasks
            )
            if view is not None
        ],
        focused_object=focused_object_dict,
    )
