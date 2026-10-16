from django.conf import settings

from academic_chatbot.exceptions import InvalidQueryError


class QueryPreprocessor:

    @staticmethod
    def process(message: str) -> str:

        if not isinstance(message, str):
            raise InvalidQueryError(
                "Message must be a string."
            )

        normalized = " ".join(
            message.strip().split()
        )

        if not normalized:
            raise InvalidQueryError(
                "Message cannot be empty."
            )

        max_length = settings.ACADEMIC_CHATBOT_MAX_QUERY_LENGTH

        if len(normalized) > max_length:
            raise InvalidQueryError(
                "Your message is too long. "
                "Please shorten your request."
            )

        return normalized

    