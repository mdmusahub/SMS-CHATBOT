# import logging

# from rest_framework.permissions import IsAuthenticated
# from rest_framework.response import Response
# from rest_framework.views import APIView

# from academic_chatbot.agents.academic_attendance_agent import (
#     AcademicAttendanceAgent,
# )
# from academic_chatbot.context.context_provider import (
#     UserContextProvider,
# )
# from academic_chatbot.exceptions import (
#     InvalidQueryError,
#     LLMServiceError,
#     UserContextUnavailableError,
# )


# logger = logging.getLogger(__name__)


# class AcademicChatbotQueryView(APIView):

#     permission_classes = [
#         IsAuthenticated
#     ]

#     def post(self, request):

#         message = request.data.get(
#             "message"
#         )

#         try:
#             user_context = (
#                 UserContextProvider.resolve(
#                     request
#                 )
#             )

#             agent = AcademicAttendanceAgent()

#             result = agent.handle(
#                 message=message,
#                 user_context=user_context,
#             )

#             return Response(
#                 {
#                     "success": True,
#                     "answer": result.answer,
#                     "results": [
#                         item.model_dump(
#                             mode="json"
#                         )
#                         for item in result.results
#                     ],
#                 },
#                 status=200,
#             )

#         except InvalidQueryError as exc:

#             return Response(
#                 {
#                     "success": False,
#                     "message": str(exc),
#                 },
#                 status=400,
#             )

#         except UserContextUnavailableError:

#             logger.exception(
#                 "Unable to resolve chatbot user context."
#             )

#             return Response(
#                 {
#                     "success": False,
#                     "message": (
#                         "Your account context could not "
#                         "be verified."
#                     ),
#                 },
#                 status=403,
#             )

#         except LLMServiceError:

#             logger.exception(
#                 "Chatbot LLM service failure."
#             )

#             return Response(
#                 {
#                     "success": False,
#                     "message": (
#                         "The chatbot is temporarily unavailable. "
#                         "Please try again shortly."
#                     ),
#                 },
#                 status=503,
#             )

#         except Exception:

#             logger.exception(
#                 "Unexpected Academic chatbot error."
#             )

#             return Response(
#                 {
#                     "success": False,
#                     "message": (
#                         "Something went wrong while processing "
#                         "your request."
#                     ),
#                 },
#                 status=500,
#             )

        








import logging

from rest_framework.response import Response
from rest_framework.views import APIView

from academic_chatbot.agents.academic_attendance_agent import (
    AcademicAttendanceAgent,
)
from academic_chatbot.context.context_provider import (
    UserContextProvider,
)
from academic_chatbot.exceptions import (
    InvalidQueryError,
    LLMServiceError,
    UserContextUnavailableError,
)
from academic_chatbot.permissions import (
    AcademicChatbotPermission,
)


logger = logging.getLogger(__name__)


class AcademicChatbotQueryView(APIView):

    permission_classes = [
        AcademicChatbotPermission
    ]

    def post(self, request):

        message = request.data.get("message")

        try:
            user_context = UserContextProvider.resolve(
                request
            )

            agent = AcademicAttendanceAgent()

            result = agent.handle(
                message=message,
                user_context=user_context,
            )

            return Response(
                {
                    "success": True,
                    "answer": result.answer,
                    "results": [
                        item.model_dump(
                            mode="json"
                        )
                        for item in result.results
                    ],
                },
                status=200,
            )

        except InvalidQueryError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=400,
            )

        except UserContextUnavailableError as exc:

            logger.warning(
                "Unable to resolve chatbot user context: %s",
                exc,
            )

            return Response(
                {
                    "success": False,
                    "message": (
                        "Your account context could not "
                        "be verified."
                    ),
                },
                status=403,
            )

        except LLMServiceError:

            logger.exception(
                "Academic chatbot LLM failure."
            )

            return Response(
                {
                    "success": False,
                    "message": (
                        "The chatbot is temporarily unavailable. "
                        "Please try again shortly."
                    ),
                },
                status=503,
            )

        except Exception:

            logger.exception(
                "Unexpected Academic chatbot failure."
            )

            return Response(
                {
                    "success": False,
                    "message": (
                        "Something went wrong while processing "
                        "your request."
                    ),
                },
                status=500,
            )