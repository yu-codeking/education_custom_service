from pathlib import Path

from edu_service.chitchat.handler import ChitChatHandler
from edu_service.clarify.responder import ClarifyResponder
from edu_service.engines.dialogue_engine import DialogueEngine
from edu_service.knowledge.handler import KnowledgeHandler
from edu_service.knowledge.intents import KNOWLEDGE_INTENTS
from edu_service.knowledge.provider.register import build_knowledge_register
from edu_service.plan.planner import TurnPlanner
from edu_service.plan.validator import TurnPlanValidator
from edu_service.task.action.builder import build_action_runner
from edu_service.task.commands.processor import CommandProcessor
from edu_service.task.flows.executor import FlowExecutor
from edu_service.task.flows.loader import FlowLoader
from edu_service.task.handler import TaskHandler

PROJECT_ROOT_DIR = Path(__file__).resolve().parents[2]

FLOW_CONFIG_DIR = PROJECT_ROOT_DIR / "flow_config"


def build_dialogue_engine():
    # 1. 加载流程
    flow_list = FlowLoader().load_multi_yaml(
        [FLOW_CONFIG_DIR / yaml for yaml in ("system_flows.yml", "user_flows.yml")])

    return DialogueEngine(
        turn_planner=TurnPlanner(),
        turn_plan_validator=TurnPlanValidator(),
        clarify_responder=ClarifyResponder(),
        task_handler=TaskHandler(
            flow_list=flow_list,
            command_processor=CommandProcessor(),
            flow_executor=FlowExecutor(),
            action_runner=build_action_runner()
        ),
        knowledge_handler=KnowledgeHandler(
            knowledge_intents=KNOWLEDGE_INTENTS,
            knowledge_register=build_knowledge_register()),
        chitchat_handler=ChitChatHandler()
    )
