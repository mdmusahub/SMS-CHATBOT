from django.conf import settings

from academic_chatbot.domain.enums import (
    Intent,
    TargetType,
)
from academic_chatbot.domain.schemas import (
    AcademicQueryPlan,
    AcademicTask,
)
from academic_chatbot.exceptions import LLMServiceError


class PlanValidator:

    MIN_YEAR = 2000
    MAX_YEAR = 2100

    @classmethod
    def validate(
        cls,
        plan: AcademicQueryPlan,
    ) -> AcademicQueryPlan:

        if not plan.tasks:
            raise LLMServiceError(
                "The language model returned an empty task plan."
            )

        if (
            len(plan.tasks)
            > settings.ACADEMIC_CHATBOT_MAX_PLANNER_TASKS
        ):
            raise LLMServiceError(
                "The request contains too many independent tasks."
            )

        for task in plan.tasks:
            cls._validate_task(task)

        return plan

    @classmethod
    def _validate_task(
        cls,
        task: AcademicTask,
    ) -> None:

        if task.intent == Intent.UNSUPPORTED:
            return

        cls._validate_target(task)
        cls._validate_month(task)
        cls._validate_year(task)

        if task.intent == Intent.TEACHER_LOOKUP:
            cls._validate_subject(task)

    @staticmethod
    def _validate_target(
        task: AcademicTask,
    ) -> None:

        if task.target.type == TargetType.SELF:
            return

        if task.target.type == TargetType.STUDENT:

            student_id = task.target.student_id

            if (
                student_id is None
                or not isinstance(student_id, int)
                or student_id <= 0
            ):
                raise LLMServiceError(
                    "The planner returned an invalid student target."
                )

            return

        raise LLMServiceError(
            "The planner returned an invalid target."
        )

    @staticmethod
    def _validate_month(
        task: AcademicTask,
    ) -> None:

        if task.month is None:
            return

        if not 1 <= task.month <= 12:
            raise LLMServiceError(
                "The planner returned an invalid month."
            )

    @classmethod
    def _validate_year(
        cls,
        task: AcademicTask,
    ) -> None:

        if task.year is None:
            return

        if not cls.MIN_YEAR <= task.year <= cls.MAX_YEAR:
            raise LLMServiceError(
                "The planner returned an invalid year."
            )

    @staticmethod
    def _validate_subject(
        task: AcademicTask,
    ) -> None:

        if (
            not task.subject_name
            or not task.subject_name.strip()
        ):
            raise LLMServiceError(
                "A subject name is required for teacher lookup."
            )