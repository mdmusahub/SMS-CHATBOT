class AcademicChatbotError(Exception):
    """Base exception for chatbot domain errors."""


class AccessDeniedError(AcademicChatbotError):
    """Raised when the authenticated user cannot access a resource."""


class UnsupportedIntentError(AcademicChatbotError):
    """Raised when no registered tool supports an intent."""


class LLMServiceError(AcademicChatbotError):
    """Raised when the configured LLM provider fails."""


class InvalidQueryError(AcademicChatbotError):
    """Raised when the user query cannot be processed."""


class UserContextUnavailableError(AcademicChatbotError):
    """Raised when authenticated user context cannot be resolved."""