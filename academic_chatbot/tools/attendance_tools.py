from academic_chatbot.domain.schemas import AcademicTask
from academic_chatbot.services.attendance_service import (
    AttendanceService,
)


def execute_attendance_summary(
    *,
    task: AcademicTask,
    student_id: int,
) -> dict:
    """
    Execute attendance retrieval for an already-authorized student.

    This function must only be called by TaskExecutor after
    authorization succeeds.
    """

    return AttendanceService.get_attendance_summary(
        student_id=student_id,
        month=task.month,
        year=task.year,
    )