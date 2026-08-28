import importlib
import inspect
import pkgutil

from edu_service.task.action.base import Action
from edu_service.task.action.builtin.listener import ActionListener
from edu_service.task.action.builtin.response import ActionResponse
from edu_service.task.action.register import ActionRegister
from edu_service.task.action.runner import ActionRunner


def registry_builtin_action(action_runner: ActionRunner):
    """
    职责： 将内置的两个action注册到runner中的注册中心
    Args:
        action_runner:

    Returns:

    """
    action_runner.action_register.registry_action(ActionResponse())
    action_runner.action_register.registry_action(ActionListener())


def registry_customer_action(action_runner: ActionRunner):
    """
      职责： 将自定义的三个action注册到runner中的注册中心(自动发现)
    Args:
        action_runner:

    Returns:

    """
    customer_action_package = importlib.import_module(
        "edu_service.task.action.customer"
    )

    for _, module_name, is_pkg in pkgutil.iter_modules(
        path=customer_action_package.__path__,
        prefix=f"{customer_action_package.__name__}.",
    ):
        if is_pkg:
            continue
        module = importlib.import_module(module_name)

        for _, class_obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(class_obj, Action) or class_obj is Action:
                continue

            action_runner.action_register.registry_action(class_obj())


def build_action_runner() -> ActionRunner:
    action_runner = ActionRunner(ActionRegister())

    registry_builtin_action(action_runner)
    registry_customer_action(action_runner)

    return action_runner


if __name__ == "__main__":
    build_action_runner()
