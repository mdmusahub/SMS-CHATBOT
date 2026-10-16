from django.conf import settings

from academic_chatbot.context.user_context import UserContext
from academic_chatbot.domain.enums import Capability
from academic_chatbot.exceptions import UserContextUnavailableError


class LocalDevelopmentContextProvider:
    """
    Development-only UserContext provider.

    Allows developers to simulate different authorization scopes
    until the real Authentication/User Context Agent is available.

    This provider must never operate in production.
    """

    def resolve(self, request) -> UserContext:

        if not settings.DEBUG:
            raise UserContextUnavailableError(
                "Development context provider is disabled."
            )

        if not settings.ACADEMIC_CHATBOT_ALLOW_DEV_CONTEXT:
            raise UserContextUnavailableError(
                "Development chatbot context is not enabled."
            )

        raw_context = request.data.get("dev_context")

        if not isinstance(raw_context, dict):
            raise UserContextUnavailableError(
                "dev_context is required for local chatbot testing."
            )

        user_id = self._positive_int(
            raw_context.get("user_id"),
            "user_id",
        )

        student_id = self._optional_positive_int(
            raw_context.get("student_id"),
            "student_id",
        )

        roles = self._string_collection(
            raw_context.get("roles", []),
            "roles",
        )

        allowed_student_ids = self._student_ids(
            raw_context.get("allowed_student_ids", [])
        )

        capabilities = self._capabilities(
            raw_context.get("capabilities", [])
        )

        can_access_all_students = raw_context.get(
            "can_access_all_students",
            False,
        )

        if not isinstance(can_access_all_students, bool):
            raise UserContextUnavailableError(
                "can_access_all_students must be a boolean."
            )

        return UserContext(
            user_id=user_id,
            roles=tuple(roles),
            student_id=student_id,
            allowed_student_ids=frozenset(
                allowed_student_ids
            ),
            capabilities=frozenset(
                capabilities
            ),
            can_access_all_students=can_access_all_students,
        )

    @staticmethod
    def _positive_int(value, field_name: str) -> int:

        try:
            value = int(value)
        except (TypeError, ValueError):
            raise UserContextUnavailableError(
                f"{field_name} must be a valid integer."
            )

        if value <= 0:
            raise UserContextUnavailableError(
                f"{field_name} must be greater than zero."
            )

        return value

    @classmethod
    def _optional_positive_int(
        cls,
        value,
        field_name: str,
    ) -> int | None:

        if value is None:
            return None

        return cls._positive_int(
            value,
            field_name,
        )

    @staticmethod
    def _string_collection(
        value,
        field_name: str,
    ) -> list[str]:

        if not isinstance(value, list):
            raise UserContextUnavailableError(
                f"{field_name} must be a list."
            )

        cleaned = []

        for item in value:
            if not isinstance(item, str):
                raise UserContextUnavailableError(
                    f"{field_name} must contain only strings."
                )

            item = item.strip()

            if item:
                cleaned.append(item)

        return cleaned

    @classmethod
    def _student_ids(
        cls,
        values,
    ) -> list[int]:

        if not isinstance(values, list):
            raise UserContextUnavailableError(
                "allowed_student_ids must be a list."
            )

        return [
            cls._positive_int(
                value,
                "allowed_student_ids",
            )
            for value in values
        ]

    @staticmethod
    def _capabilities(values) -> list[str]:

        if not isinstance(values, list):
            raise UserContextUnavailableError(
                "capabilities must be a list."
            )

        valid_capabilities = {
            capability.value
            for capability in Capability
        }

        result = []

        for capability in values:

            if capability not in valid_capabilities:
                raise UserContextUnavailableError(
                    f"Unknown capability: {capability}"
                )

            result.append(capability)

        return result

    