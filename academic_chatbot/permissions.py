from django.conf import settings
from rest_framework.permissions import BasePermission


class AcademicChatbotPermission(BasePermission):
    """
    Allows unauthenticated requests only when the explicit
    development-context mode is enabled.

    Production requires a genuinely authenticated user.
    """

    message = "Authentication is required."

    def has_permission(self, request, view):

        development_mode = (
            settings.DEBUG
            and settings.ACADEMIC_CHATBOT_ALLOW_DEV_CONTEXT
        )

        if development_mode:
            return True

        return bool(
            request.user
            and request.user.is_authenticated
        )