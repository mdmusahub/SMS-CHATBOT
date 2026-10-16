from academic_chatbot.domain.schemas import AcademicTask
from academic_chatbot.services.academic_service import (
    AcademicService,
)


def execute_subject_list(
    *,
    task: AcademicTask,
    student_id: int,
) -> dict:

    return AcademicService.get_subjects_for_student(
        student_id=student_id
    )


def execute_teacher_lookup(
    *,
    task: AcademicTask,
    student_id: int,
) -> dict:

    return AcademicService.get_subject_teacher(
        student_id=student_id,
        subject_name=task.subject_name,
    )


