from dataclasses import dataclass
from typing import Optional

from academic_chatbot.context.user_context import UserContext
from academic_chatbot.domain.enums import TargetType
from academic_chatbot.domain.schemas import AcademicTask
from academic_chatbot.exceptions import AccessDeniedError
from academic_chatbot.tools.registry import ToolDefinition


@dataclass(frozen=True)
class AuthorizationResult:
    student_id: Optional[int] = None


class AuthorizationService:
    """
    Performs deterministic authorization.

    The LLM is never involved in this decision.
    """

    @staticmethod
    def authorize(
        *,
        user_context: UserContext,
        task: AcademicTask,
        tool: ToolDefinition,
    ) -> AuthorizationResult:

        required_capability = tool.required_capability.value

        if (
            required_capability
            not in user_context.capabilities
        ):
            raise AccessDeniedError(
                "You do not have permission to perform this request."
            )

        if not tool.student_scoped:
            return AuthorizationResult()

        student_id = (
            AuthorizationService._resolve_student_target(
                user_context=user_context,
                task=task,
            )
        )

        AuthorizationService._validate_student_scope(
            user_context=user_context,
            student_id=student_id,
        )

        return AuthorizationResult(
            student_id=student_id
        )

    @staticmethod
    def _resolve_student_target(
        *,
        user_context: UserContext,
        task: AcademicTask,
    ) -> int:

        if task.target.type == TargetType.SELF:

            if user_context.student_id is None:
                raise AccessDeniedError(
                    "No student profile is associated with this account."
                )

            return user_context.student_id

        if task.target.type == TargetType.STUDENT:

            if task.target.student_id is None:
                raise AccessDeniedError(
                    "A valid student target is required."
                )

            return task.target.student_id

        raise AccessDeniedError(
            "Invalid student target."
        )

    @staticmethod
    def _validate_student_scope(
        *,
        user_context: UserContext,
        student_id: int,
    ) -> None:

        if user_context.can_access_all_students:
            return

        if student_id in user_context.allowed_student_ids:
            return

        raise AccessDeniedError(
            "You are not authorized to access this student's information."
        )


    