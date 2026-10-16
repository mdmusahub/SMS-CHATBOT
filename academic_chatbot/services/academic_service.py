from django.utils import timezone

from director.models import ClassPeriod, Subject
from student.models import StudentYearLevel


class AcademicService:

    @staticmethod
    def get_current_enrollment(student_id: int):
        """
        Return the student's enrollment for the currently active
        school year.

        We intentionally do not silently fall back to an old
        enrollment because that could return stale academic data.
        """

        today = timezone.localdate()

        return (
            StudentYearLevel.objects
            .select_related(
                "level",
                "year",
                "section",
            )
            .filter(
                student_id=student_id,
                year__start_date__lte=today,
                year__end_date__gte=today,
            )
            .first()
        )

    @classmethod
    def get_subjects_for_student(
        cls,
        student_id: int,
    ) -> dict:

        enrollment = cls.get_current_enrollment(
            student_id
        )

        if enrollment is None:
            return {
                "student_id": student_id,
                "has_data": False,
                "message": (
                    "No active academic enrollment was found "
                    "for this student."
                ),
                "subjects": [],
            }

        subjects = list(
            Subject.objects
            .filter(
                year_levels__id=enrollment.level_id
            )
            .order_by("subject_name")
            .values(
                "id",
                "subject_name",
            )
            .distinct()
        )

        return {
            "student_id": student_id,
            "has_data": bool(subjects),
            "year_level_id": enrollment.level_id,
            "year_level": enrollment.level.level_name,
            "section_id": enrollment.section_id,
            "section": (
                enrollment.section.section_label
                if enrollment.section
                else None
            ),
            "school_year_id": enrollment.year_id,
            "school_year": enrollment.year.year_name,
            "subjects": subjects,
            "message": (
                None
                if subjects
                else "No subjects are configured for this class."
            ),
        }

    @classmethod
    def get_subject_teacher(
        cls,
        *,
        student_id: int,
        subject_name: str,
    ) -> dict:

        enrollment = cls.get_current_enrollment(
            student_id
        )

        if enrollment is None:
            return {
                "student_id": student_id,
                "has_data": False,
                "message": (
                    "No active academic enrollment was found "
                    "for this student."
                ),
                "teachers": [],
            }

        subject_name = subject_name.strip()

        subject = (
            Subject.objects
            .filter(
                year_levels__id=enrollment.level_id,
                subject_name__iexact=subject_name,
            )
            .first()
        )

        # Safe relaxed matching only when exactly one subject matches.
        if subject is None:

            possible_subjects = list(
                Subject.objects
                .filter(
                    year_levels__id=enrollment.level_id,
                    subject_name__icontains=subject_name,
                )
                .distinct()[:2]
            )

            if len(possible_subjects) == 1:
                subject = possible_subjects[0]

        if subject is None:
            return {
                "student_id": student_id,
                "has_data": False,
                "subject": subject_name,
                "message": (
                    "The requested subject was not found "
                    "for the student's current class."
                ),
                "teachers": [],
            }

        assignments = (
            ClassPeriod.objects
            .filter(
                year_level_id=enrollment.level_id,
                subject_id=subject.id,
                teacher__isnull=False,
            )
            .select_related(
                "teacher",
                "teacher__user",
            )
        )

        teachers = {}

        for assignment in assignments:

            teacher = assignment.teacher
            user = teacher.user

            full_name = " ".join(
                part
                for part in [
                    user.first_name,
                    user.middle_name,
                    user.last_name,
                ]
                if part
            )

            teachers[teacher.id] = {
                "teacher_id": teacher.id,
                "name": full_name,
                "subject": subject.subject_name,
            }

        teacher_list = list(
            teachers.values()
        )

        if not teacher_list:
            return {
                "student_id": student_id,
                "has_data": False,
                "subject_id": subject.id,
                "subject": subject.subject_name,
                "teachers": [],
                "message": (
                    "No class teacher assignment is currently "
                    "configured for this subject."
                ),
            }

        return {
            "student_id": student_id,
            "has_data": True,
            "subject_id": subject.id,
            "subject": subject.subject_name,
            "teachers": teacher_list,
            "ambiguous": len(teacher_list) > 1,
            "message": (
                "Multiple teacher assignments were found."
                if len(teacher_list) > 1
                else None
            ),
        }
    