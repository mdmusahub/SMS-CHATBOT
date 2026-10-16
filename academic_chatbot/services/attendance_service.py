from attendance.models import Attendance


class AttendanceService:

    VALID_STATUSES = ["P", "A", "L"]

    @staticmethod
    def get_attendance_summary(
        student_id: int,
        month: int | None = None,
        year: int | None = None,
    ) -> dict:

        queryset = Attendance.objects.filter(
            student_id=student_id,
            status__in=AttendanceService.VALID_STATUSES,
        )

        if month is not None:
            queryset = queryset.filter(marked_at__month=month)

        if year is not None:
            queryset = queryset.filter(marked_at__year=year)

        total = queryset.count()

        if total == 0:
            return {
                "student_id": student_id,
                "month": month,
                "year": year,
                "has_data": False,
                "message": "No attendance records found.",
                "total_days": 0,
                "present_days": 0,
                "absent_days": 0,
                "leave_days": 0,
                "attendance_percentage": None,
            }

        present = queryset.filter(status="P").count()
        absent = queryset.filter(status="A").count()
        leave = queryset.filter(status="L").count()

        attendance_percentage = round(
            (present / total) * 100,
            2
        )

        return {
            "student_id": student_id,
            "month": month,
            "year": year,
            "has_data": True,
            "total_days": total,
            "present_days": present,
            "absent_days": absent,
            "leave_days": leave,
            "attendance_percentage": attendance_percentage,
        }