from rest_framework import serializers
from .models import *
from datetime import date
from .utils import validate_basic_attendance_rules

class StudentAttendanceSerializer(serializers.ModelSerializer):
    # ----- Input-only fields -----
    teacher_id = serializers.IntegerField(write_only=True, required=False)
    year_level_id = serializers.IntegerField(write_only=True, required=False)
    status = serializers.CharField(required=False)

    P = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    A = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    L = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )

    # ----- Output-only fields -----
    student_name = serializers.CharField(
        source="student.user.get_full_name",
        read_only=True
    )
    teacher_name = serializers.CharField(
        source="teacher.user.get_full_name",
        read_only=True
    )

    class Meta:
        model = Attendance
        fields = ["id","student_name","teacher_name","status","marked_at","teacher_id","year_level_id","P","A","L",
                   "student", "teacher","year_level",]
        read_only_fields = ["id", "student", "teacher","year_level",]


    def validate(self, attrs):
        request = self.context.get("request")

        # If updating single record → skip bulk validation
        if request and request.method in ["PUT"]:
            return attrs

        marked_at = attrs.get("marked_at", date.today())
        validate_basic_attendance_rules(marked_at)

        teacher_id = attrs.get("teacher_id")
        year_level_id = attrs.get("year_level_id")

        #Check Teacher-YearLevel match
        teacher = Teacher.objects.filter(id=teacher_id).first()
        if not teacher:
            raise serializers.ValidationError("Invalid teacher.")

        if not TeacherYearLevel.objects.filter(
                teacher_id=teacher_id,
                year_level_id=year_level_id
        ).exists():
            raise serializers.ValidationError(
                "Teacher is not assigned to this year level."
            )

        allowed_statuses = {"P", "A", "L"}
        all_student_ids = []

        for status_code in allowed_statuses:
            all_student_ids.extend(attrs.get(status_code, []))

        if not all_student_ids:
            raise serializers.ValidationError(
                "At least one attendance status must be provided."
            )
        if len(all_student_ids) != len(set(all_student_ids)):
            raise serializers.ValidationError(
                "A student ID cannot appear in multiple status lists."
            )
        
        students = Student.objects.filter(id__in=all_student_ids, is_active=True)
        for student in students:
            if not student.student_year_levels.filter(
                    level_id=year_level_id
            ).exists():
                raise serializers.ValidationError(
                    f"{student.id} - {student.user.get_full_name()} does not belong to this year level."
                )

        # Duplicate check here (student specific)
        already_marked = Attendance.objects.filter(
            student_id__in=all_student_ids,
            marked_at=marked_at
        ).values_list("student_id", flat=True)

        if already_marked:
            raise serializers.ValidationError({
                "error": "Attendance already marked for this date.",
                "student_ids": list(already_marked)
            })

        return attrs


class StudentAttendancePercentSerializer(serializers.Serializer):
    student_name = serializers.CharField()
    class_name = serializers.CharField()
    monthly_percentage = serializers.FloatField()
    yearly_percentage = serializers.FloatField()
    
    
class HolidaySerializer(serializers.ModelSerializer):
    title = serializers.CharField(required=True, allow_blank=False)
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)

    class Meta:
        model = Holiday
        fields = '__all__'

    def validate(self, data):
        start = data["start_date"]
        end = data["end_date"]

        if start > end:
            raise serializers.ValidationError("Start date must be before end date.")

        # max 45 days check
        if (end - start).days > 45:
            raise serializers.ValidationError("Holiday duration cannot exceed 45 days.")

        # optional: prevent overlapping holidays.
        qs = Holiday.objects.filter(
            start_date__lte=end,
            end_date__gte=start
        )
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Holiday dates overlap with another holiday.")

        return data

        
class SchoolHolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolHoliday
        fields = ['id', 'title', 'date', 'description']
        
class SchoolEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolEvent
        fields = ['id', 'title', 'start_date', 'end_date', 'description']


class OfficeStaffAttendanceSerializer(serializers.ModelSerializer):
    marked_at = serializers.DateField(required=False)
    P = serializers.ListField(child=serializers.IntegerField(), required=False)
    A = serializers.ListField(child=serializers.IntegerField(), required=False)
    L = serializers.ListField(child=serializers.IntegerField(), required=False)
    status = serializers.CharField(required=False)

    office_staff_name = serializers.CharField(source="office_staff.user.get_full_name", read_only=True)
    
    class Meta:
        model = Attendance
        fields = [
            'id',
            'marked_at',
            'status',
            'office_staff',
            'office_staff_name','P','A','L'
        ]
        read_only_fields = ["id",'office_staff_name','office_staff']


    def validate(self, attrs):
        request = self.context.get("request")

        # If updating single record → skip bulk validation
        if request and request.method in ["PUT"]:
            return attrs
    
        marked_at = attrs.get("marked_at") or date.today()
        validate_basic_attendance_rules(marked_at)

        present = attrs.get("P", [])
        absent = attrs.get("A", [])
        leave = attrs.get("L", [])

        all_ids = present + absent + leave

        if not all_ids:
            raise serializers.ValidationError(
                "At least one office staff ID must be provided."
            )

        if len(all_ids) != len(set(all_ids)):
            raise serializers.ValidationError(
                "A staff ID cannot appear in multiple status lists."
            )
        
        existing_staff_ids = set(
            OfficeStaff.objects.filter(id__in=all_ids)
            .values_list("id", flat=True)
        )

        missing_ids = set(all_ids) - existing_staff_ids

        if missing_ids:
            raise serializers.ValidationError({
                "error": "Some office staff IDs do not exist.",
                "missing_ids": list(missing_ids)
            })


        # DB duplicate safety check
        already_marked = Attendance.objects.filter(
            office_staff_id__in=all_ids,
            marked_at=marked_at
        ).values_list("office_staff_id", flat=True)

        if already_marked:
            raise serializers.ValidationError({
                "error": "Attendance already marked for some staff.",
                "office_staff_ids": list(already_marked)
            })

        attrs["marked_at"] = marked_at
        return attrs


class TeacherAttendanceSerializer(serializers.ModelSerializer):
    marked_at = serializers.DateField(required=False)
    P = serializers.ListField(child=serializers.IntegerField(), required=False)
    A = serializers.ListField(child=serializers.IntegerField(), required=False)
    L = serializers.ListField(child=serializers.IntegerField(), required=False)
    status = serializers.CharField(required=False)

    teacher_name = serializers.CharField(source="teacher.user.get_full_name", read_only=True)
    
    class Meta:
        model = Attendance
        fields = [
            'id',
            'marked_at',
            'status',
            'teacher',
            'teacher_name','P','A','L'
        ]
        read_only_fields = ["id","teacher_name",'teacher']

    def validate(self, attrs):
        request = self.context.get("request")

        # If updating single record → skip bulk validation
        if request and request.method in ["PUT"]:
            return attrs

        marked_at = attrs.get("marked_at") or date.today()
        validate_basic_attendance_rules(marked_at)

        present = attrs.get("P", [])
        absent = attrs.get("A", [])
        leave = attrs.get("L", [])

        all_ids = present + absent + leave

        # At least one teacher required
        if not all_ids:
            raise serializers.ValidationError(
                "At least one teacher ID must be provided."
            )

        # Prevent duplicate IDs across lists
        if len(all_ids) != len(set(all_ids)):
            raise serializers.ValidationError(
                "A teacher ID cannot appear in multiple status lists."
            )

        # Check teacher existence
        existing_teacher_ids = set(
            Teacher.objects.filter(id__in=all_ids)
            .values_list("id", flat=True)
        )

        missing_ids = set(all_ids) - existing_teacher_ids
        if missing_ids:
            raise serializers.ValidationError({
                "error": "Some teacher IDs do not exist.",
                "missing_ids": list(missing_ids)
            })

        # Duplicate attendance check
        already_marked = Attendance.objects.filter(
            teacher_id__in=all_ids,
            marked_at=marked_at,
            student__isnull=True
        ).values_list("teacher_id", flat=True)

        if already_marked:
            raise serializers.ValidationError({
                "error": "Attendance already marked for some teachers.",
                "teacher_ids": list(already_marked)
            })

        attrs["marked_at"] = marked_at
        return attrs

