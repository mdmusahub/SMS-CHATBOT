from django.test import SimpleTestCase

from academic_chatbot.context.user_context import UserContext
from academic_chatbot.domain.enums import (
    Intent,
    TargetType,
)
from academic_chatbot.domain.schemas import (
    AcademicTask,
    StudentTarget,
)
from academic_chatbot.exceptions import AccessDeniedError
from academic_chatbot.services.authorization_service import (
    AuthorizationService,
)
from academic_chatbot.tools.registry import TOOL_REGISTRY


class AuthorizationServiceTests(SimpleTestCase):

    def setUp(self):

        self.context = UserContext(
            user_id=100,
            roles=("STUDENT",),
            student_id=8,
            allowed_student_ids=frozenset({8}),
            capabilities=frozenset({
                "attendance.read",
                "academic.read",
            }),
            can_access_all_students=False,
        )

    def test_student_can_access_self(self):

        task = AcademicTask(
            intent=Intent.ATTENDANCE_SUMMARY,
            target=StudentTarget(
                type=TargetType.SELF
            ),
        )

        result = AuthorizationService.authorize(
            user_context=self.context,
            task=task,
            tool=TOOL_REGISTRY[
                Intent.ATTENDANCE_SUMMARY
            ],
        )

        self.assertEqual(
            result.student_id,
            8,
        )

    def test_student_cannot_access_other_student(self):

        task = AcademicTask(
            intent=Intent.ATTENDANCE_SUMMARY,
            target=StudentTarget(
                type=TargetType.STUDENT,
                student_id=9,
            ),
        )

        with self.assertRaises(
            AccessDeniedError
        ):
            AuthorizationService.authorize(
                user_context=self.context,
                task=task,
                tool=TOOL_REGISTRY[
                    Intent.ATTENDANCE_SUMMARY
                ],
            )