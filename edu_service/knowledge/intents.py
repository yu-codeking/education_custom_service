from dataclasses import dataclass


@dataclass(slots=True)
class KnowledgeIntent:
    id: str
    description: str
    provider_ids: list[str]
    requires_object_type: str | None = None


# 系统支持的所有知识意图
KNOWLEDGE_INTENTS: dict[str, KnowledgeIntent] = {
    "course_info": KnowledgeIntent(
        id="course_info",
        description="课程信息查询（需要先发送课程卡片）",
        provider_ids=["api.course"],
        requires_object_type="course",
    ),
    "order_info": KnowledgeIntent(
        id="order_info",
        description="订单信息查询（需要先发送订单卡片）",
        provider_ids=["api.order"],
        requires_object_type="order",
    ),
    "refund_policy": KnowledgeIntent(
        id="refund_policy",
        description="退费政策咨询（退费条件、时限、到账时间等）",
        provider_ids=["faq.default", "rag.default"],
    ),
    "open_course_policy": KnowledgeIntent(
        id="open_course_policy",
        description="开课与调班政策咨询（开课时间、转班、延期等）",
        provider_ids=["faq.default", "rag.default"],
    ),
    "learning_service_policy": KnowledgeIntent(
        id="learning_service_policy",
        description="学习服务咨询（考勤规则、视频回放、作业与考试安排等）",
        provider_ids=["faq.default", "rag.default"],
    ),
    "platform_rule": KnowledgeIntent(
        id="platform_rule",
        description="平台规则咨询",
        provider_ids=["rag.default"],
    ),
    "general_edu_info": KnowledgeIntent(
        id="general_edu_info",
        description="在线教育通用信息咨询",
        provider_ids=["faq.default", "rag.default"],
    ),
}
