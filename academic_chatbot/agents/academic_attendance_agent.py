from academic_chatbot.context.user_context import UserContext
from academic_chatbot.domain.schemas import AgentResponse
from academic_chatbot.services.llm_service import (
    GeminiLLMService,
)
from academic_chatbot.services.query_preprocessor import (
    QueryPreprocessor,
)
from academic_chatbot.services.task_executor import (
    TaskExecutor,
)


class AcademicAttendanceAgent:

    def __init__(
        self,
        llm_service: GeminiLLMService | None = None,
        task_executor: TaskExecutor | None = None,
    ):
        self.llm_service = (
            llm_service or GeminiLLMService()
        )

        self.task_executor = (
            task_executor or TaskExecutor()
        )

    def handle(
        self,
        *,
        message: str,
        user_context: UserContext,
    ) -> AgentResponse:

        normalized_message = (
            QueryPreprocessor.process(message)
        )

        plan = self.llm_service.plan(
            normalized_message
        )

        results = self.task_executor.execute(
            plan=plan,
            user_context=user_context,
        )

        answer = (
            self.llm_service.generate_final_answer(
                user_message=normalized_message,
                results=results,
            )
        )

        return AgentResponse(
            answer=answer,
            results=results,
        )

    