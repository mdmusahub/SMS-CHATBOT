from rest_framework import serializers
from . models import SubstituteAssignment, Teacher, TeacherYearLevel, SubstituteAssignment
from authentication . models import User
from director . models import Role
from django.db import IntegrityError
from django.core.exceptions import MultipleObjectsReturned
from director.models import *    #YearLevel , Subject
from director.serializers import *  # ClassPeriodSerializer , subjectSerializer, YearLevelSerializer
from django.core.validators import RegexValidator







class TeacherSerializer(serializers.ModelSerializer):
    # User-related fields (write_only)
    first_name = serializers.CharField(max_length=250, write_only=True)
    middle_name = serializers.CharField(
        max_length=250, write_only=True, required=False, allow_blank=True
    )
    last_name = serializers.CharField(max_length=250, write_only=True)
    password = serializers.CharField(max_length=250, write_only=True, required=False)
    email = serializers.EmailField(max_length=250, write_only=True)
    user_profile = serializers.ImageField(
        required=False, allow_null=True, write_only=True
    )

    # Teacher model explicit fields
    # phone_no = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    # gender = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    # adhaar_no = serializers.IntegerField(required=False, allow_null=True)
    # pan_no = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    qualification = serializers.CharField(
        max_length=250, required=False, allow_blank=True, allow_null=True
    )
    phone_no = serializers.CharField(
        required=False,
        allow_blank=True,
        validators=[
            RegexValidator(
                regex=r"^\+?(\d[\s-]?){10,15}$",
                message="Enter a valid phone number (10-15 digits, optional + at start).",
            )
        ],
    )
    adhaar_no = serializers.CharField(
        required=False,
        allow_blank=True,
        validators=[
            RegexValidator(
                regex=r"^\d{12}$", message="Enter a valid 12-digit Aadhaar number."
            )
        ],
    )

    pan_no = serializers.CharField(
        required=False,
        allow_blank=True,
        validators=[
            RegexValidator(
                regex=r"^[A-Z]{5}[0-9]{4}[A-Z]$",
                message="Enter a valid PAN number (e.g., ABCDE1234F).",
            )
        ],
    )
    gender = serializers.ChoiceField(
        choices=[("Male", "Male"), ("Female", "Female"), ("Other", "Other")],
        required=False,
        error_messages={"invalid_choice": "Gender must be Male, Female, or Other."},
    )
    address_input = AddressSerializer(write_only=True, required=False, allow_null=True)
    banking_detail_input = BankingDetailsSerializer(
        write_only=True, required=False, allow_null=True
    )
    subject_name = serializers.CharField(source='subject.subject_name', read_only=True, allow_null=True)

    class Meta:
        model = Teacher
        fields = [
            "id",
            "first_name",
            "middle_name",
            "last_name",
            "password",
            "email",
            "phone_no",
            "gender",
            "adhaar_no",
            "pan_no",
            "qualification",
            "user_profile",
            "joining_date",
            "is_active",
            "cadre",
            "subject",
            "subject_name",
            "banking_detail_input",
            "address_input",
        ]

    def get_address(self, obj):
        address = Address.objects.filter(user=obj.student.user).first()
        return AddressSerializer(address).data if address else None

    def get_banking_detail(self, obj):
        banking = BankingDetail.objects.filter(user=obj.student.user).first()
        return BankingDetailsSerializer(banking).data if banking else None

    def validate_adhaar_no(self, value):
        from director.models import (
            OfficeStaff,
        )  # Importing here to avoid circular import issues

        teacher_id = self.instance.id if self.instance else None

        # Check in Teacher
        teacher_exists = (
            Teacher.objects.exclude(id=teacher_id).filter(adhaar_no=value).exists()
        )

        # Check in OfficeStaff
        staff_exists = OfficeStaff.objects.filter(adhaar_no=value).exists()

        if teacher_exists or staff_exists:
            raise serializers.ValidationError(
                "This Aadhaar number is already registered."
            )
        return value

    def validate_pan_no(self, value):
        from director.models import (
            OfficeStaff,
        )  # Importing here to avoid circular import issues

        teacher_id = self.instance.id if self.instance else None

        # Check in Teacher
        teacher_exists = (
            Teacher.objects.exclude(id=teacher_id).filter(pan_no=value).exists()
        )

        # Check in OfficeStaff
        staff_exists = OfficeStaff.objects.filter(pan_no=value).exists()

        if teacher_exists or staff_exists:
            raise serializers.ValidationError("This PAN number is already registered.")
        return value

    def create(self, validated_data):
        user_data = {
            "first_name": validated_data.pop("first_name", ""),
            "middle_name": validated_data.pop("middle_name", ""),
            "last_name": validated_data.pop("last_name", ""),
            "password": validated_data.pop("password", ""),
            "email": validated_data.pop("email", ""),
            "user_profile": validated_data.pop("user_profile", None),
        }

        try:
            role, _ = Role.objects.get_or_create(name="teacher")
        except MultipleObjectsReturned:
            raise serializers.ValidationError("Multiple 'teacher' roles found.")

        existing_user = User.objects.filter(email=user_data["email"]).first()

        if existing_user:
            if not existing_user.role.filter(name="teacher").exists():
                existing_user.role.add(role)
                existing_user.save()
            else:
                raise serializers.ValidationError(
                    "User email already exists with this role."
                )
            user = existing_user
        else:
            user = User.objects.create_user(**user_data)
            user.role.add(role)
            user.save()

        teacher = Teacher.objects.create(user=user, **validated_data)
        return teacher

    def update(self, instance, validated_data):
        user = instance.user
        address_data = validated_data.pop("address_input", None)
        banking_data = validated_data.pop("banking_detail_input", None)
        # --- Address and banking ---
        if address_data:
            Address.objects.update_or_create(user=user, defaults=address_data)
        # if banking_data:
        #     BankingDetail.objects.update_or_create(user=user, defaults=banking_data)

        if banking_data:
            try:
                BankingDetail.objects.update_or_create(user=user, defaults=banking_data)
            except IntegrityError:
                raise serializers.ValidationError(
                    {
                        "banking_detail_input": {
                            "non_field_errors": [
                                "The fields account_no, ifsc_code must make a unique set. This combination already exists for another user."
                            ]
                        }
                    }
                )

        # Update user fields
        user.first_name = validated_data.get("first_name", user.first_name)
        user.middle_name = validated_data.get("middle_name", user.middle_name or "")
        user.last_name = validated_data.get("last_name", user.last_name)
        user.email = validated_data.get("email", user.email)

        if "user_profile" in validated_data:
            user.user_profile = validated_data.get("user_profile")

        if "password" in validated_data:
            user.set_password(validated_data["password"])

        try:
            user.save()
        except IntegrityError:
            raise serializers.ValidationError("Email already exists.")

        # Update teacher fields
        instance.phone_no = validated_data.get("phone_no", instance.phone_no)
        instance.gender = validated_data.get("gender", instance.gender)
        instance.adhaar_no = validated_data.get("adhaar_no", instance.adhaar_no)
        instance.pan_no = validated_data.get("pan_no", instance.pan_no)
        instance.qualification = validated_data.get(
            "qualification", instance.qualification
        )
        instance.joining_date = validated_data.get(
            "joining_date", instance.joining_date
        )

        instance.save()

        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Banking detail
        banking = getattr(instance.user, "bankingdetail", None) if instance.user else None
        representation["banking_data"] = (
            BankingDetailsSerializer(banking).data if banking else None
        )

        # Address
        last_address = instance.user.address_set.last() if instance.user else None
        representation["address_data"] = (
            AddressSerializer(last_address).data if last_address else None
        )

        representation.update(
            {
                "user_id": instance.user.id,
                "first_name": instance.user.first_name if instance.user else "",
                "middle_name": instance.user.middle_name if instance.user else "",
                "last_name": instance.user.last_name if instance.user else "",
                "email": instance.user.email if instance.user else "",
                "user_profile": (
                    instance.user.user_profile.url
                    if instance.user and instance.user.user_profile
                    else None
                ),
                "phone_no": instance.phone_no,
                "gender": instance.gender,
                "adhaar_no": instance.adhaar_no,
                "pan_no": instance.pan_no,
                "qualification": instance.qualification,
                "cadre": instance.cadre,
                "subject": instance.subject_id,
                "subject_name": instance.subject.subject_name if instance.subject else None,
            }
        )
        return representation




# ******************TeacherYearLevelSerializer***********************************


from rest_framework import serializers
from .models import TeacherYearLevel

class TeacherYearLevelSerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()
    year_level_name = serializers.CharField(source='year_level.level_name', read_only=True)

    class Meta:
        model = TeacherYearLevel
        fields = "__all__"
       
    def get_teacher_name(self, obj):
        if obj.teacher and obj.teacher.user:
            return obj.teacher.user.get_full_name() or f"{obj.teacher.user.first_name} {obj.teacher.user.last_name}".strip()
        return ""

    def validate(self, data):
        teacher = data.get('teacher')  
        year_level = data.get('year_level')
        instance = self.instance  # None if create, else update

        # Check if this teacher already has any year_level assigned
        qs = TeacherYearLevel.objects.filter(teacher=teacher)
        if instance:
            qs = qs.exclude(pk=instance.pk)  # exclude current record if updating

        if qs.exists():
            assigned_year_level = qs.first().year_level
            teacher_name = f"{teacher.user.get_full_name()}" if teacher and hasattr(teacher, 'user') else str(teacher)
            raise serializers.ValidationError({
                'teacher': f"Teacher {teacher_name} is already assigned to '{assigned_year_level}'. Cannot assign another class."
            })

        # Check if this year_level is already assigned to another teacher
        qs_year_level = TeacherYearLevel.objects.filter(year_level=year_level)
        if instance:
            qs_year_level = qs_year_level.exclude(pk=instance.pk)

        if qs_year_level.exists():
            assigned_teacher = qs_year_level.first().teacher
            teacher_name = f"{assigned_teacher.user.get_full_name()}" if assigned_teacher and hasattr(assigned_teacher, 'user') else str(assigned_teacher)
            raise serializers.ValidationError({
                'year_level': [
                    f"Class '{year_level}' is already assigned to teacher '{teacher_name}'.",
                    "Cannot assign the same class to another teacher."
                ]
            })
        return data



from django.utils import timezone

class SubstituteAssignmentSerializer(serializers.ModelSerializer):
    absent_teacher_name = serializers.SerializerMethodField()
    substitute_teacher_name = serializers.SerializerMethodField()
    
    class Meta:
        model = SubstituteAssignment
        fields = [
            'id', 'period', 'date', 'absent_teacher', 'substitute_teacher',
            'year_level', 'absent_teacher_name', 'substitute_teacher_name'
        ]
        extra_kwargs = {
            "date": {"required": False}  # <- date ko optional banaya
        }

    def get_absent_teacher_name(self, obj):
        return f"{obj.absent_teacher.user.first_name} {obj.absent_teacher.user.last_name}"
    
    def get_substitute_teacher_name(self, obj):
        return f"{obj.substitute_teacher.user.first_name} {obj.substitute_teacher.user.last_name}"

    def validate(self, attrs):
        absent_teacher = attrs.get("absent_teacher")
        substitute_teacher = attrs.get("substitute_teacher")
        period = attrs.get("period")
        year_level = attrs.get("year_level")
        date = attrs.get("date")

        # same teacher check
        if absent_teacher == substitute_teacher:
            raise serializers.ValidationError({
                "errors": [
                    "Invalid assignment: Absent teacher and substitute teacher cannot be the same."
                ]
            })

        # default date
        if not date:
            date = timezone.now().date()
            attrs["date"] = date  

        instance_id = self.instance.id if self.instance else None

        duplicate_qs = SubstituteAssignment.objects.filter(
            absent_teacher=absent_teacher,
            period=period,
            date=date,
            year_level=year_level
        )
        if instance_id:
            duplicate_qs = duplicate_qs.exclude(id=instance_id)

        if duplicate_qs.exists():
            dup = duplicate_qs.first()
            raise serializers.ValidationError({
                "errors": [
                    f"Assignment already exists: "
                    f"{absent_teacher.user.first_name} {absent_teacher.user.last_name} "
                    f"is already assigned substitute "
                    f"{dup.substitute_teacher.user.first_name} {dup.substitute_teacher.user.last_name} "
                    f"for period {period} on {date} ({year_level})."
                ]
            })

        return attrs

