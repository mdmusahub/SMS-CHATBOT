from django.conf import settings
from django.utils.module_loading import import_string

from academic_chatbot.context.user_context import UserContext
from academic_chatbot.exceptions import (
    UserContextUnavailableError,
)


class UserContextProvider:

    @staticmethod
    def resolve(request) -> UserContext:

        provider_path = (
            settings.ACADEMIC_CHATBOT_CONTEXT_PROVIDER
        )

        if not provider_path:
            raise UserContextUnavailableError(
                "Authentication/User Context provider "
                "is not configured."
            )

        try:
            provider_class = import_string(
                provider_path
            )

            provider = provider_class()

            context = provider.resolve(request)

        except UserContextUnavailableError:
            raise

        except Exception as exc:
            raise UserContextUnavailableError(
                "Unable to resolve authenticated user context."
            ) from exc

        if not isinstance(
            context,
            UserContext,
        ):
            raise UserContextUnavailableError(
                "Invalid UserContext returned by provider."
            )

        return context