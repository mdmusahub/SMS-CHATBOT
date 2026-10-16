import logging

from academic_chatbot.context.user_context import UserContext
from academic_chatbot.domain.enums import (
    Intent,
    TaskStatus,
)
from academic_chatbot.domain.schemas import (
    AcademicQueryPlan,
    TaskExecutionResult,
)
from academic_chatbot.exceptions import AccessDeniedError
from academic_chatbot.services.authorization_service import (
    AuthorizationService,
)
from academic_chatbot.tools.registry import TOOL_REGISTRY

from django.conf import settings

from academic_chatbot.exceptions import InvalidQueryError

logger = logging.getLogger(__name__)


class TaskExecutor:

    def execute(
        self,
        *,
        plan: AcademicQueryPlan,
        user_context: UserContext,
    ) -> list[TaskExecutionResult]:

        results: list[TaskExecutionResult] = []

        for index, task in enumerate(
            plan.tasks,
            start=1,
        ):
            task_id = f"task_{index}"

            if task.intent == Intent.UNSUPPORTED:
                results.append(
                    TaskExecutionResult(
                        task_id=task_id,
                        intent=task.intent.value,
                        status=TaskStatus.UNSUPPORTED,
                        message=(
                            "This request is not currently "
                            "supported by the Academic & Attendance chatbot."
                        ),
                    )
                )

                continue

            tool = TOOL_REGISTRY.get(
                task.intent
            )

            if tool is None:
                logger.warning(
                    "No tool registered for intent=%s",
                    task.intent.value,
                )

                results.append(
                    TaskExecutionResult(
                        task_id=task_id,
                        intent=task.intent.value,
                        status=TaskStatus.UNSUPPORTED,
                        message=(
                            "This request is not currently supported."
                        ),
                    )
                )

                continue

            try:
                authorization = (
                    AuthorizationService.authorize(
                        user_context=user_context,
                        task=task,
                        tool=tool,
                    )
                )

            except AccessDeniedError as exc:

                results.append(
                    TaskExecutionResult(
                        task_id=task_id,
                        intent=task.intent.value,
                        status=TaskStatus.ACCESS_DENIED,
                        message=str(exc),
                    )
                )

                continue

            try:
                data = tool.handler(
                    task=task,
                    student_id=authorization.student_id,
                )

                results.append(
                    TaskExecutionResult(
                        task_id=task_id,
                        intent=task.intent.value,
                        status=TaskStatus.SUCCESS,
                        data=data,
                    )
                )

            except Exception:
                logger.exception(
                    "Tool execution failed. "
                    "task_id=%s intent=%s user_id=%s",
                    task_id,
                    task.intent.value,
                    user_context.user_id,
                )

                results.append(
                    TaskExecutionResult(
                        task_id=task_id,
                        intent=task.intent.value,
                        status=TaskStatus.FAILED,
                        message=(
                            "This part of your request could not "
                            "be completed right now."
                        ),
                    )
                )

        return results




class TaskExecutor:

    def execute(
        self,
        *,
        plan,
        user_context,
    ):

        executable_count = sum(
            1
            for task in plan.tasks
            if task.intent in TOOL_REGISTRY
        )

        if (
            executable_count
            > settings.ACADEMIC_CHATBOT_MAX_TOOL_EXECUTIONS
        ):
            raise InvalidQueryError(
                "Your request requires too many operations. "
                "Please split it into smaller requests."
            )

        results = []

        # existing for-loop continues here...