from rest_framework.exceptions import ValidationError
from .models import *
from datetime import date, timedelta

def validate_basic_attendance_rules(marked_at):

    # Future date not allowed
    if marked_at > date.today():
        raise ValidationError("You cannot mark attendance for a future date.")

    # Only last 7 days allowed
    seven_days_ago = date.today() - timedelta(days=7)
    if marked_at < seven_days_ago:
        raise ValidationError("You can only mark attendance for the last 7 days.")

    # Sunday not allowed
    if marked_at.weekday() == 6:
        raise ValidationError("Attendance cannot be marked on Sunday.")

    # Specific school holiday
    if SchoolHoliday.objects.filter(date=marked_at).exists():
        raise ValidationError("Attendance cannot be marked on a school holiday.")

    # Holiday range
    if Holiday.objects.filter(
        start_date__lte=marked_at,
        end_date__gte=marked_at
    ).exists():
        raise ValidationError("Attendance cannot be marked on a holiday.")
