"""
定义接口数据模型：和前端进行交互
继承BaseModel:在运行期间完成类型的校验和类型的转换
"""
from typing import Any

from pydantic import BaseModel


class ChatObject(BaseModel):
    id: str  # 订单号 / 课程ID / 班次ID
    title: str  # 订单标题 / 课程名称 / 班次名称
    type: str  # 卡片类型：order=订单卡片 course=课程卡片 cohort=班次卡片
    attributes: dict[str, Any]  # 业务对象的额外信息


class ChatBotMessage(BaseModel):
    text: str  # 机器人回复的内容
    object: ChatObject | None = None  # 附带业务对象卡片时使用


class ChatRequest(BaseModel):
    """
    聊天请求接口数据模型
    """
    sender_id: str  # 会话ID（对话状态持久化的主键）
    user_id: str | None = None  # 当前服务的学员身份（edu-api 的 X-User-Id），首轮传入后会被记住
    stream: bool = False  # 兼容字段：流式请走 /api/chat/stream
    text: str | None = None
    object: ChatObject | None = None


class ChatResponse(BaseModel):
    """
    聊天响应接口数据模型
    """
    message_id: str
    messages: list[ChatBotMessage]
    session_state: "SessionState | None" = None  # 本轮处理后的会话状态快照


class SessionCreateRequest(BaseModel):
    """创建新会话请求"""
    user_id: str | None = None  # 模拟学员身份（可选）


class SessionCreatedResponse(BaseModel):
    session_id: str
    user_id: str | None = None


class TaskContextView(BaseModel):
    flow_id: str
    step_id: str
    slots: dict[str, Any]


class SessionState(BaseModel):
    """当前会话状态视图：激活流程 / 已收集槽位 / 暂停栈"""
    session_id: str
    user_id: str | None = None
    current_session_id: str | None = None
    active_task: TaskContextView | None = None
    active_system_task_flow_id: str | None = None
    paused_tasks: list[TaskContextView]
    focused_object: dict[str, Any] | None = None


class HistoryMessage(BaseModel):
    role: str  # user / bot
    type: str  # text / object
    text: str | None = None
    object: ChatObject | None = None
    turn_id: str


class SessionMessagesResponse(BaseModel):
    session_id: str
    messages: list[HistoryMessage]


ChatResponse.model_rebuild()  # ChatResponse 前向引用了 SessionState
