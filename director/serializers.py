from datetime import date, datetime, timedelta, time as dt_time
import re
from rest_framework import serializers

from director.utils import get_fee_due_year
from .models import *
from django.core.exceptions import MultipleObjectsReturned
from django.db import IntegrityError, transaction
from student.serializers import *

# from authentication.serializers import UserSerializer
from uuid import uuid4
from django.utils import timezone
from decimal import Decimal
from collections import defaultdict
from django.db.models import Max
from django.db.models import Sum
import calendar
from django.core.exceptions import ValidationError
import os
from dateutil.relativedelta import relativedelta
from django.conf import settings


class YearLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = YearLevel
        fields = "__all__"


class SectionSerializer(serializers.ModelSerializer):
    year_level_name = serializers.CharField(source='year_level.level_name', read_only=True)

    class Meta:
        model = Section
        fields = ['id', 'year_level', 'year_level_name', 'section_label']


class SchoolYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolYear
        fields = "__all__"


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"


class ClassRoomTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassRoomType
        fields = "__all__"


class ClassRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassRoom
        fields = ["id", "room_type", "room_name", "capacity"]
        read_only_fields = ["id"]

class BankNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankName
        fields = ['id', 'name']

class BankingDetailsSerializer(serializers.ModelSerializer):
    account_no = serializers.IntegerField(required=False, allow_null=True)
    ifsc_code = serializers.CharField(required=False, allow_blank=True)
    holder_name = serializers.CharField(required=False, allow_blank=True)
    bank_name = serializers.PrimaryKeyRelatedField(
        queryset=BankName.objects.all(),
        required=False,
        allow_null=True
    )
    class Meta:
        model = BankingDetail
        fields = ["id", "account_no", "ifsc_code", "holder_name", 'bank_name']
        extra_kwargs = {"user": {"read_only": True}}

    def create(self, validated_data):
        user = self.context.get("user")
        if not user:
            raise serializers.ValidationError(
                "User is required to create banking detail."
            )
        return BankingDetail.objects.create(user=user, **validated_data)

    def update(self, instance, validated_data):
        account_no = validated_data.get("account_no", instance.account_no)

        # Only check for duplicates if account_no is provided and not null
        if account_no not in [None, ""] and account_no != instance.account_no:
            if (
                BankingDetail.objects.filter(account_no=account_no)
                .exclude(id=instance.id)
                .exists()
            ):
                raise serializers.ValidationError(
                    {
                        "account_no": "This account number is already in use by another user."
                    }
                )

        # Apply even if user clears the field
        instance.account_no = validated_data.get("account_no", None)
        instance.ifsc_code = validated_data.get("ifsc_code", "")
        instance.holder_name = validated_data.get("holder_name", "")
        instance.bank_name = validated_data.get("bank_name", None)
        instance.save()
        return instance

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name"]

    def create_or_get_role(self, role_name):
        existing_role = Role.objects.filter(name=role_name).first()
        if existing_role:
            return existing_role
        else:
            new_role = Role.objects.create(name=role_name)
            return new_role


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = "__all__"


class subjectSerializer(serializers.ModelSerializer):
    department_name = (serializers.SerializerMethodField())  # repalced department to department_name because of SerializerMethodField (Read Only Field).

    class Meta:
        model = Subject
        fields = ["id", "subject_name", "department", "department_name", "year_levels"]

    def get_department_name(self, obj):
        return obj.department.department_name if obj.department else None


class StateSerializer(serializers.ModelSerializer):
    class Meta:
        model = State
        fields = "__all__"


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = "__all__"


class AddressSerializer(serializers.ModelSerializer):
    country = serializers.PrimaryKeyRelatedField(
        queryset=Country.objects.all(), write_only=True
    )
    state = serializers.PrimaryKeyRelatedField(
        queryset=State.objects.all(), write_only=True
    )
    city = serializers.PrimaryKeyRelatedField(
        queryset=City.objects.all(), write_only=True
    )

    country_name = serializers.CharField(source="country.name", read_only=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    city_name = serializers.CharField(source="city.name", read_only=True)

    class Meta:
        model = Address
        fields = [
            "id",
            "user",
            "house_no",
            "habitation",
            "ward_no",
            "zone_no",
            "block",
            "district",
            "division",
            "area_code",
            "country",
            "state",
            "city",
            "address_line",
            "country_name",
            "state_name",
            "city_name",
        ]
        extra_kwargs = {"user": {"read_only": True}}

    def validate(self, data):
        # user = data.get('user')  # No need to get user here, it's read-only
        house_no = data.get("house_no")
        area_code = data.get("area_code")
        country = data.get("country")
        state = data.get("state")
        city = data.get("city")
        address_line = data.get("address_line")

        # Access the user from the serializer context
        user = self.context.get("user")

        if Address.objects.all_including_inactive().filter(
            user=user,
            house_no=house_no,
            area_code=area_code,
            country=country,
            state=state,
            city=city,
            address_line=address_line,
        ).exists():
            raise serializers.ValidationError("Address already exists for the user.")

        return data

    def create(self, validated_data):
        user = self.context["request"].user  # assuming request is passed in context
        return Address.objects.create(user=user, **validated_data)


class SchoolYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolYear
        fields = "__all__"


class PeriodSerializer(serializers.ModelSerializer):
    year = serializers.PrimaryKeyRelatedField(queryset=SchoolYear.objects.all())

    class Meta:
        model = Period
        fields = ["id","year", "name", "start_period_time", "end_period_time"]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        try:
            representation["year"] = instance.year.year_name
        except AttributeError:
            representation["year"] = None
        return representation


class TermSerializer(serializers.ModelSerializer):
    year = serializers.PrimaryKeyRelatedField(queryset=SchoolYear.objects.all())

    class Meta:
        model = Term
        fields = ["id", "year", "term_number", "start_date", "end_date"]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["year"] = instance.year.year_name
        return representation


class DirectorProfileSerializer(serializers.ModelSerializer):
    # User fields
    first_name = serializers.CharField(max_length=100, write_only=True)
    middle_name = serializers.CharField(
        max_length=100, write_only=True, allow_blank=True, required=False
    )
    last_name = serializers.CharField(max_length=100, write_only=True)
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, required=False, allow_null=True)
    user_profile = serializers.ImageField(
        required=False, allow_null=True, write_only=True
    )

    # Director fields
    phone_no = serializers.CharField(
        required=False,
        allow_blank=True,
        validators=[
            RegexValidator(
                regex=r"^\+?(\d[\s-]?){10,15}$",
                message="Enter a valid contact number (10-15 digits, optional + at start).",
            )
        ],
    )
    gender = serializers.ChoiceField(
        choices=[("Male", "Male"), ("Female", "Female"), ("Other", "Other")],
        required=False,
        error_messages={"invalid_choice": "Gender must be Male, Female, or Other."},
    )

    class Meta:
        model = Director
        exclude = ["user"]

    def create(self, validated_data):
        # Extract user-related data
        user_data = {
            "first_name": validated_data.pop("first_name"),
            "middle_name": validated_data.pop("middle_name", ""),
            "last_name": validated_data.pop("last_name"),
            "email": validated_data.pop("email"),
            "password": validated_data.pop("password", ""),
            "user_profile": validated_data.pop("user_profile", None),
        }

        phone_no = validated_data.pop("phone_no", None)
        gender = validated_data.pop("gender", None)

        # Assign role
        try:
            role, _ = Role.objects.get_or_create(name="director")
        except MultipleObjectsReturned:
            raise serializers.ValidationError(
                "Multiple 'director' roles exist. Please fix your roles table."
            )

        # Get or create user
        user = User.objects.filter(email=user_data["email"]).first()
        if user:
            if not user.role.filter(name="director").exists():
                user.role.add(role)
        else:
            user = User.objects.create_user(**user_data)
            user.role.add(role)
            user.save()

        try:
            director_profile = Director.objects.create(
                user=user, phone_no=phone_no, gender=gender, **validated_data
            )
        except IntegrityError:
            raise serializers.ValidationError("User with this email already exists.")

        return director_profile

    def update(self, instance, validated_data):
        user = instance.user

        # Update user info
        user.first_name = validated_data.get("first_name", user.first_name)
        user.middle_name = validated_data.get("middle_name", user.middle_name)
        user.last_name = validated_data.get("last_name", user.last_name)
        user.email = validated_data.get("email", user.email)

        if "password" in validated_data and validated_data["password"]:
            user.set_password(validated_data["password"])

        if "user_profile" in validated_data:
            user.user_profile = validated_data.get("user_profile")

        # Update director fields
        instance.phone_no = validated_data.get("phone_no", instance.phone_no)
        instance.gender = validated_data.get("gender", instance.gender)

        try:
            user.save()
            instance.save()
        except IntegrityError:
            raise serializers.ValidationError(
                "Failed to update. Email may already exist."
            )

        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation.update({
            "first_name": instance.user.first_name if instance.user else "",
            "middle_name": instance.user.middle_name if instance.user else "",
            "last_name": instance.user.last_name if instance.user else "",
            "email": instance.user.email if instance.user else "",
            "user_profile": instance.user.user_profile.url if instance.user and instance.user.user_profile else None,
            "phone_no": instance.phone_no,
            "gender": instance.gender,
        })
        return representation

class AdmissionSerializer(serializers.ModelSerializer):
    student_input = serializers.SerializerMethodField(read_only=True)
    guardian_input = serializers.SerializerMethodField(read_only=True)
    address = serializers.SerializerMethodField(read_only=True)
    banking_detail = serializers.SerializerMethodField(read_only=True)
    guardian_type = serializers.SerializerMethodField(read_only=True)

    guardian_type_input = serializers.SlugRelatedField(
        slug_field='name',
        queryset=GuardianType.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    year_level = serializers.SlugRelatedField(
        slug_field='level_name',
        queryset=YearLevel.objects.all(),
        required=False,
        allow_null=True,
    )

    school_year = serializers.SlugRelatedField(
        slug_field='year_name',
        queryset=SchoolYear.objects.all(),
        required=False,
        allow_null=True,
    )

    student = StudentSerializer(write_only=True, required=False)
    guardian = GuardianSerializer(write_only=True, required=False)
    address_input = AddressSerializer(write_only=True, required=False, allow_null=True)
    banking_detail_input = BankingDetailsSerializer(write_only=True, required=False, allow_null=True)

    CLASS_SECTION_CHOICES = [('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D'), ('PCM','PCM'), ('PCB','PCB'), ('COMM','COMM'), ('ARTS','ARTS')]
    class_section = serializers.ChoiceField(choices=CLASS_SECTION_CHOICES, required=False, allow_null=True, allow_blank=True)
    house = serializers.ChoiceField(choices=StudentYearLevelSerializer.HOUSE_CHOICES, required=False, allow_null=True)

    class Meta:
        model = Admission
        fields = [
            'id',
            'student_input', 'guardian_input',
            'address', 'banking_detail',
            'student', 'guardian',
            'address_input', 'banking_detail_input',
            'guardian_type', 'guardian_type_input',
            'year_level', 'school_year', 'class_section', #'department',
            'house', 'admission_date', 'previous_school_name', 'previous_standard_studied',
            'tc_letter', 'emergency_contact_no', 'entire_road_distance_from_home_to_school',
            'obtain_marks', 'total_marks', 'previous_percentage', 'enrollment_no', 'is_rte', 'rte_number'
        ]
        read_only_fields = [
            'admission_date', 'student_input', 'guardian_input',
            'guardian_type', 'address', 'banking_detail'
        ]

    def get_student_input(self, obj):
        return StudentSerializer(obj.student).data if obj.student else None

    def get_guardian_input(self, obj):
        return GuardianSerializer(obj.guardian).data if obj.guardian else None

    def get_address(self, obj):
        if obj.student and obj.student.user:
            address = Address.objects.filter(user=obj.student.user).first()
            return AddressSerializer(address).data if address else None
        return None

    def get_banking_detail(self, obj):
        if obj.student and obj.student.user:
            banking = BankingDetail.objects.filter(user=obj.student.user).first()
            return BankingDetailsSerializer(banking).data if banking else None
        return None

    def get_guardian_type(self, obj):
        # Guard against None guardian
        if not obj.guardian:
            return None
        try:
            sg = StudentGuardian.objects.get(student=obj.student, guardian=obj.guardian)
            return sg.guardian_type.name
        except (StudentGuardian.DoesNotExist, AttributeError):
            return None

    # -------------------- CREATE --------------------
    def create(self, validated_data):
        try:
            return self._do_create(validated_data)
        except serializers.ValidationError:
            raise
        except IntegrityError as e:
            raise serializers.ValidationError({"error": f"A record with this data already exists. Details: {e}"})
        except Exception as e:
            raise serializers.ValidationError({"error": f"Something went wrong while creating the admission: {str(e)}"})

    def _do_create(self, validated_data):
        is_rte = validated_data.pop('is_rte', False)
        rte_number = validated_data.pop('rte_number', None)
        student_data = validated_data.pop('student')
        guardian_data = validated_data.pop('guardian', None)
        address_data = validated_data.pop('address_input', None)
        banking_data = validated_data.pop('banking_detail_input', None)
        guardian_type = validated_data.pop('guardian_type_input', None)
        year_level = validated_data.pop('year_level', None)
        school_year = validated_data.pop('school_year', None)
        class_section = validated_data.pop('class_section', None)
        # department = validated_data.pop('department', None)   # pop not get
        house = validated_data.pop('house', None)

        # -------------------- STUDENT --------------------
        classes_data = student_data.pop('classes', [])
        if isinstance(classes_data, str):
            classes_data = [int(classes_data)]

        user_data = {
            'first_name': student_data.pop('first_name', ''),
            'middle_name': student_data.pop('middle_name', ''),
            'last_name': student_data.pop('last_name', ''),
            'email': student_data.pop('email'),
            'password': student_data.pop('password', None),
            'user_profile': student_data.pop('user_profile', None),
        }

        if User.objects.filter(email__iexact=user_data['email']).exists():
            raise serializers.ValidationError({
                "student": f"A user with email '{user_data['email']}' already exists. Please use a different email."
            })

        role, _ = Role.objects.get_or_create(name='student')
        user = User.objects.create_user(**user_data)
        user.role.add(role)

        try:
            student, created = Student.objects.get_or_create(user=user, defaults=student_data)
            if not created:
                raise serializers.ValidationError({
                    "student": f"A student profile already exists for '{user.email}'."
                })
        except IntegrityError:
            raise serializers.ValidationError({
                "student": f"Could not create student profile for '{user.email}'. Please check the submitted data."
            })

        if classes_data:
            student.classes.set(classes_data)

        # -------------------- ADDRESS --------------------
        if address_data:
            try:
                Address.objects.update_or_create(user=user, defaults=address_data)
            except IntegrityError as e:
                raise serializers.ValidationError({"address": f"Could not save address: {str(e)}"})

        # -------------------- BANKING --------------------
        # Skip if all values are None/empty — avoids NOT NULL DB errors
        if banking_data:
            has_any_value = any(
                v not in (None, '', []) for v in banking_data.values()
            )
            if has_any_value:
                try:
                    BankingDetail.objects.update_or_create(user=user, defaults=banking_data)
                except IntegrityError as e:
                    raise serializers.ValidationError({"banking_detail": f"Could not save banking details: {str(e)}"})

        # -------------------- GUARDIAN --------------------
        guardian_instance = None

        if guardian_data:
            user_fields = ['first_name', 'middle_name', 'last_name', 'email', 'password', 'user_profile']
            guardian_user_data = {k: guardian_data.pop(k) for k in user_fields if k in guardian_data}
            email = guardian_user_data.get('email', '').strip()

            guardian_user = User.objects.filter(email__iexact=email).first() if email else None

            if guardian_user:
                guardian_instance = Guardian.objects.all_including_inactive().filter(user=guardian_user).first()
            elif email:
                try:
                    password = guardian_user_data.pop('password', 'Guardian123')
                    guardian_user = User.objects.create_user(password=password, **guardian_user_data)
                    role, _ = Role.objects.get_or_create(name='guardian')
                    guardian_user.role.add(role)
                    guardian_instance = Guardian.objects.create(user=guardian_user, **guardian_data)
                except IntegrityError as e:
                    raise serializers.ValidationError({"guardian": f"Could not create guardian account: {str(e)}"})

        # -------------------- ADMISSION --------------------
        admission = Admission.objects.create(
            student=student,
            guardian=guardian_instance,
            previous_school_name=validated_data.get('previous_school_name'),
            previous_standard_studied=validated_data.get('previous_standard_studied'),
            tc_letter=validated_data.get('tc_letter'),
            year_level=year_level,
            school_year=school_year,
            class_section=class_section,
            emergency_contact_no=validated_data.get('emergency_contact_no'),
            entire_road_distance_from_home_to_school=validated_data.get('entire_road_distance_from_home_to_school'),
            obtain_marks=validated_data.get('obtain_marks'),
            total_marks=validated_data.get('total_marks'),
            enrollment_no=validated_data.get('enrollment_no'),
            is_rte=is_rte,
            rte_number=rte_number,
            # department=department,
        )

        if guardian_type and guardian_instance:
            StudentGuardian.objects.update_or_create(
                student=student,
                guardian=guardian_instance,
                defaults={'guardian_type': guardian_type}
            )

        if year_level and school_year:
            syl_defaults = {}
            if house is not None:   # only set house if explicitly provided
                syl_defaults['house'] = house
            StudentYearLevel.objects.update_or_create(
                student=student,
                level=year_level,
                year=school_year,
                defaults=syl_defaults
            )

        return admission

    # -------------------- UPDATE --------------------
    def update(self, instance, validated_data):
        try:
            return self._do_update(instance, validated_data)
        except serializers.ValidationError:
            raise
        except IntegrityError as e:
            raise serializers.ValidationError({"error": f"A record with this data already exists: {str(e)}"})
        except Exception as e:
            raise serializers.ValidationError({"error": f"Something went wrong while updating the admission: {str(e)}"})

    def _do_update(self, instance, validated_data):
        instance.is_rte = validated_data.pop('is_rte', instance.is_rte)
        instance.rte_number = validated_data.pop('rte_number', instance.rte_number)
        student_data = validated_data.pop('student', None)
        guardian_data = validated_data.pop('guardian', None)
        address_data = validated_data.pop('address_input', None)
        banking_data = validated_data.pop('banking_detail_input', None)
        guardian_type = validated_data.pop('guardian_type_input', None)
        year_level = validated_data.pop('year_level', None)
        school_year = validated_data.pop('school_year', None)
        class_section = validated_data.pop('class_section', None)
        house = validated_data.pop('house', None)

        user = instance.student.user

        # --- STUDENT ---
        if student_data:
            student_serializer = StudentSerializer(instance.student, data=student_data, partial=True)
            student_serializer.is_valid(raise_exception=True)
            student_serializer.save()
            classes_data = student_data.get('classes')
            if isinstance(classes_data, str):
                classes_data = [int(classes_data)]
            if classes_data:
                instance.student.classes.set(classes_data)

        # --- GUARDIAN ---
        if guardian_data:
            if instance.guardian:
                guardian_user = instance.guardian.user
                if guardian_user is None:
                    user_fields = ['first_name', 'middle_name', 'last_name', 'email', 'password', 'user_profile']
                    guardian_user_data = {k: guardian_data.pop(k) for k in user_fields if k in guardian_data}
                    email = guardian_user_data.get('email', '').strip()
                    if email:
                        if User.objects.filter(email__iexact=email).exists():
                            raise serializers.ValidationError({
                                "guardian": f"Email '{email}' is already registered. Please use a different email."
                            })
                        password = guardian_user_data.pop('password', 'Guardian123')
                        guardian_user = User.objects.create_user(password=password, **guardian_user_data)
                        role, _ = Role.objects.get_or_create(name='guardian')
                        guardian_user.role.add(role)
                        instance.guardian.user = guardian_user
                        instance.guardian.save()
                else:
                    for attr in ['first_name', 'middle_name', 'last_name', 'email', 'user_profile']:
                        val = guardian_data.get(attr)
                        if val:
                            setattr(guardian_user, attr, val)
                    if guardian_data.get('password'):
                        guardian_user.set_password(guardian_data['password'])
                    guardian_user.save()

                guardian_serializer = GuardianSerializer(instance.guardian, data=guardian_data, partial=True)
                guardian_serializer.is_valid(raise_exception=True)
                guardian_serializer.save()
            else:
                user_fields = ['first_name', 'middle_name', 'last_name', 'email', 'password', 'user_profile']
                guardian_user_data = {k: guardian_data.pop(k) for k in user_fields if k in guardian_data}
                email = guardian_user_data.get('email', '').strip()
                if email:
                    if User.objects.filter(email__iexact=email).exists():
                        raise serializers.ValidationError({
                            "guardian": f"Email '{email}' is already registered. Please use a different email."
                        })
                    password = guardian_user_data.pop('password', 'Guardian123')
                    guardian_user = User.objects.create_user(password=password, **guardian_user_data)
                    role, _ = Role.objects.get_or_create(name='guardian')
                    guardian_user.role.add(role)
                    instance.guardian = Guardian.objects.create(user=guardian_user, **guardian_data)
                else:
                    instance.guardian = Guardian.objects.create(**guardian_data)

        # --- ADDRESS ---
        if address_data:
            try:
                Address.objects.update_or_create(user=user, defaults=address_data)
            except IntegrityError as e:
                raise serializers.ValidationError({"address": f"Could not save address: {str(e)}"})

        # --- BANKING ---
        if banking_data:
            has_any_value = any(v not in (None, '', []) for v in banking_data.values())
            if has_any_value:
                try:
                    BankingDetail.objects.update_or_create(user=user, defaults=banking_data)
                except IntegrityError as e:
                    raise serializers.ValidationError({"banking_detail": f"Could not save banking details: {str(e)}"})

        # --- ADMISSION ---
        old_year_level = instance.year_level
        old_school_year = instance.school_year

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if year_level:
            instance.year_level = year_level
        if school_year:
            instance.school_year = school_year
        if class_section is not None:
            instance.class_section = class_section
        instance.save()

        if guardian_type and instance.guardian:
            StudentGuardian.objects.update_or_create(
                student=instance.student,
                guardian=instance.guardian,
                defaults={'guardian_type': guardian_type}
            )

        new_year_level = instance.year_level
        new_school_year = instance.school_year

        if old_year_level and old_school_year:
            syl = StudentYearLevel.objects.filter(
                student=instance.student,
                level=old_year_level,
                year=old_school_year
            ).first()
            if syl:
                if new_year_level:
                    syl.level = new_year_level
                if new_school_year:
                    syl.year = new_school_year
                if house is not None:
                    syl.house = house
                syl.save()
            else:
                if new_year_level and new_school_year:
                    syl_defaults = {}
                    if house is not None:
                        syl_defaults['house'] = house
                    StudentYearLevel.objects.update_or_create(
                        student=instance.student,
                        level=new_year_level,
                        year=new_school_year,
                        defaults=syl_defaults
                    )
        elif new_year_level and new_school_year:
            syl_defaults = {}
            if house is not None:
                syl_defaults['house'] = house
            StudentYearLevel.objects.update_or_create(
                student=instance.student,
                level=new_year_level,
                year=new_school_year,
                defaults=syl_defaults
            )

        return instance

    # -------------------- REPRESENTATION --------------------
    def to_representation(self, instance):
        rep = super().to_representation(instance)

        if rep.get('previous_percentage') is not None:
            rep['previous_percentage'] = f"{rep['previous_percentage']:.2f}"

        # Guard against None year_level / school_year before querying
        if instance.year_level and instance.school_year:
            syl = StudentYearLevel.objects.filter(
                student=instance.student,
                level=instance.year_level,
                year=instance.school_year
            ).first()
            rep['house'] = syl.house if syl else None
        else:
            rep['house'] = None

        return rep

class ClassPeriodSerializer(serializers.ModelSerializer):
    # Alias: accept `year_level_id` instead of `year_level`
    yearlevel_id = serializers.PrimaryKeyRelatedField(
        source="year_level",  # map it to the actual FK
        queryset=YearLevel.objects.all(),
        write_only=True,
    )

    year_level = serializers.PrimaryKeyRelatedField(
        read_only=True
    )  # still return year_level in response

    # Extra fields for the custom POST action
    year_level_name = serializers.CharField(write_only=True, required=False)
    class_period_names = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False
    )

    class Meta:
        model = ClassPeriod
        fields = [
            "id",
            "subject",
            "teacher",
            "term",
            "start_time",
            "end_time",
            "classroom",
            "name",
            "year_level",
            "yearlevel_id",  # include both
            "year_level_name",
            "class_period_names",
        ]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["start_time"] = instance.start_time.start_period_time.strftime(
            "%I:%M %p"
        )
        representation["end_time"] = instance.end_time.end_period_time.strftime(
            "%I:%M %p"
        )
        return representation

    def validate(self, attrs):
        teacher = attrs.get("teacher")
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")

        if teacher and start_time and end_time:
            overlapping = ClassPeriod.objects.filter(
                teacher=teacher,
                start_time__lt=end_time,
                end_time__gt=start_time,
            )

            if self.instance:
                overlapping = overlapping.exclude(id=self.instance.id)

            if overlapping.exists():
                raise serializers.ValidationError(
                    {
                        "non_field_errors": [
                            "This teacher is already assigned to another class during this time."
                        ]
                    }
                )

        return attrs

    def create(self, validated_data):
        # Handle assignment logic only if year_level_name and class_period_names are present
        year_level_name = validated_data.pop("year_level_name", None)
        class_period_names = validated_data.pop("class_period_names", None)

        if year_level_name and class_period_names:
            try:
                year_level = YearLevel.objects.get(level_name=year_level_name)
            except YearLevel.DoesNotExist:
                raise serializers.ValidationError("Invalid YearLevel name.")

            class_periods = ClassPeriod.objects.filter(name__in=class_period_names)
            if class_periods.count() != len(class_period_names):
                raise serializers.ValidationError("Some ClassPeriod names are invalid.")

            student_ids = StudentYearLevel.objects.filter(level=year_level).values_list(
                "student_id", flat=True
            )
            students = Student.objects.filter(id__in=student_ids, is_active=True)

            for student in students:
                student.classes.add(*class_periods)

            return {
                "students_updated": students.count(),
                "class_periods_assigned": [cp.name for cp in class_periods],
            }

        # If not an assignment request, create a regular ClassPeriod (fallback)
        return super().create(validated_data)


class OfficeStaffSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(max_length=100, write_only=True)
    middle_name = serializers.CharField(
        max_length=100, write_only=True, required=False, allow_blank=True
    )
    last_name = serializers.CharField(max_length=100, write_only=True)
    password = serializers.CharField(max_length=100, write_only=True, required=False)
    email = serializers.EmailField(write_only=True)
    user_profile = serializers.ImageField(
        required=False, allow_null=True, write_only=True
    )

    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.filter(is_active=True), many=True, required=False)
    teacher = serializers.PrimaryKeyRelatedField(queryset=Teacher.objects.filter(is_active=True), many=True, required=False)
    admissions = serializers.PrimaryKeyRelatedField(queryset=Admission.objects.filter(is_active=True), many=True, required=False)

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

    class Meta:
        model = OfficeStaff
        exclude = ["user"]

    def get_address(self, obj):
        address = Address.objects.all_including_inactive().filter(user=obj.student.user).first()
        return AddressSerializer(address).data if address else None

    def get_banking_detail(self, obj):
        banking = BankingDetail.objects.all_including_inactive().filter(user=obj.student.user).first()
        return BankingDetailsSerializer(banking).data if banking else None

    def validate_adhaar_no(self, value):
        # Get the current instance ID (works for both Teacher and OfficeStaff)
        instance_id = self.instance.id if self.instance else None

        # Check if any other Teacher has this Aadhaar number
        teacher_exists = (
            Teacher.objects.filter(adhaar_no=value).exclude(id=instance_id).exists()
        )

        # Check if any other OfficeStaff has this Aadhaar number
        staff_exists = (
            OfficeStaff.objects.filter(adhaar_no=value).exclude(id=instance_id).exists()
        )

        if teacher_exists or staff_exists:
            raise serializers.ValidationError(
                "This Aadhaar number is already registered."
            )
        return value

    def validate_pan_no(self, value):
        # Get the current instance ID (works for both Teacher and OfficeStaff)
        instance_id = self.instance.id if self.instance else None

        # Check if any other Teacher has this PAN number
        teacher_exists = (
            Teacher.objects.filter(pan_no=value).exclude(id=instance_id).exists()
        )

        # Check if any other OfficeStaff has this PAN number
        staff_exists = (
            OfficeStaff.objects.filter(pan_no=value).exclude(id=instance_id).exists()
        )

        if teacher_exists or staff_exists:
            raise serializers.ValidationError("This PAN number is already registered.")
        return value

    def create(self, validated_data):
        user_data = {
            "first_name": validated_data.pop("first_name"),
            "middle_name": validated_data.pop("middle_name", ""),
            "last_name": validated_data.pop("last_name"),
            "password": validated_data.pop("password", None),
            "email": validated_data.pop("email"),
            "user_profile": validated_data.pop("user_profile", None),
        }

        student_data = validated_data.pop("student", [])
        teacher_data = validated_data.pop("teacher", [])
        admissions_data = validated_data.pop("admissions", [])

        try:
            role, _ = Role.objects.get_or_create(name="office_staff")
        except MultipleObjectsReturned:
            raise serializers.ValidationError(
                "Multiple roles named 'office_staff' found."
            )

        user = User.objects.filter(email=user_data["email"]).first()

        if user:
            if not user.role.filter(name="office_staff").exists():
                user.role.add(role)
                user.save()
            else:
                raise serializers.ValidationError(
                    "User with this email already exists and is an office staff."
                )
        else:
            user = User.objects.create_user(**user_data)
            user.role.add(role)
            user.save()

        office_staff = OfficeStaff.objects.create(user=user, **validated_data)
        office_staff.student.set(student_data)
        office_staff.teacher.set(teacher_data)
        office_staff.admissions.set(admissions_data)
        return office_staff

    def update(self, instance, validated_data):
        user = instance.user
        address_data = validated_data.pop("address_input", None)
        banking_data = validated_data.pop("banking_detail_input", None)
        # --- Address and banking ---
        if address_data:
            Address.objects.update_or_create(user=user, defaults=address_data)
        if banking_data:
            BankingDetail.objects.update_or_create(user=user, defaults=banking_data)

        user.first_name = validated_data.pop("first_name", user.first_name)
        user.middle_name = validated_data.pop("middle_name", user.middle_name)
        user.last_name = validated_data.pop("last_name", user.last_name)
        user.email = validated_data.pop("email", user.email)
        if "password" in validated_data and validated_data["password"]:
            user.set_password(validated_data["password"])
        if "user_profile" in validated_data:
            user.user_profile = validated_data["user_profile"]

        user.save()

        instance.phone_no = validated_data.get("phone_no", instance.phone_no)
        instance.gender = validated_data.get("gender", instance.gender)
        instance.department = validated_data.get("department", instance.department)
        instance.adhaar_no = validated_data.get(
            "adhaar_no", instance.adhaar_no
        )  #  added as of 09Sep25
        instance.pan_no = validated_data.get(
            "pan_no", instance.pan_no
        )  #  added as of 09Sep25
        instance.joining_date = validated_data.get(
            "joining_date", instance.joining_date
        )  #  added as of 09Sep25
        instance.qualification = validated_data.get(
            "qualification", instance.qualification
        )
        instance.save()

        if "student" in validated_data:
            instance.student.set(validated_data["student"])
        if "teacher" in validated_data:
            instance.teacher.set(validated_data["teacher"])
        if "admissions" in validated_data:
            instance.admissions.set(validated_data["admissions"])

        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Banking detail
        banking = getattr(instance.user, 'bankingdetail', None) if instance.user else None
        representation['banking_data'] = BankingDetailsSerializer(banking).data if banking else None

        # Address
        last_address = instance.user.address_set.last() if instance.user else None  
        representation['address_data'] = AddressSerializer(last_address).data if last_address else None

        representation.update({
            "first_name": instance.user.first_name if instance.user else "",
            "middle_name": instance.user.middle_name if instance.user else "",
            "last_name": instance.user.last_name if instance.user else "",
            "email": instance.user.email if instance.user else "",
            "user_profile": instance.user.user_profile.url if instance.user and instance.user.user_profile else None,
            "adhaar_no": instance.adhaar_no,   #  added as of 09Sep25
            "pan_no": instance.pan_no,         #  added as of 09Sep25
            "qualification": instance.qualification,
            "joining_date":instance.joining_date,
            "phone_no": instance.phone_no,
            "gender": instance.gender,
        })

        # Remove relational fields from the output
        representation.pop("student", None)
        representation.pop("teacher", None)
        representation.pop("admissions", None)

        return representation



    # ******************DocumentTypeSerializer*************************


# import json


class DocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentType
        fields = "__all__"


class FileSerializer(serializers.ModelSerializer):
    file = serializers.SerializerMethodField()

    class Meta:
        model = File
        fields = ["id", "file"]

    def get_file(self, obj):
        request = self.context.get("request")
        if obj.file and os.path.exists(obj.file.path):
            return request.build_absolute_uri(obj.file.url) if request else obj.file.url
        else:
            return "File not available"


from rest_framework import serializers
from .models import Document, DocumentType


class DocumentSerializer(serializers.ModelSerializer):
    document_types = serializers.PrimaryKeyRelatedField(
        many=True, queryset=DocumentType.objects.all(), write_only=True
    )

    document_types_read = serializers.PrimaryKeyRelatedField(
        many=True, source="document_types", read_only=True
    )

    files = FileSerializer(many=True, read_only=True)

    class Meta:
        model = Document
        fields = "__all__"
        extra_kwargs = {
            "student": {"required": False, "allow_null": True},
            "teacher": {"required": False, "allow_null": True},
            "guardian": {"required": False, "allow_null": True},
            "office_staff": {"required": False, "allow_null": True},
        }

    def validate_identities(self, value):
        # If updating, exclude the current instance
        doc_id = self.instance.id if self.instance else None

        if Document.objects.exclude(id=doc_id).filter(identities=value).exists():
            raise serializers.ValidationError("This identity is already registered.")
        return value

    def create(self, validated_data):
        document_types = validated_data.pop("document_types", [])
        instance = super().create(validated_data)

        if document_types:
            instance.document_types.set(document_types)

        # Handle file creation separately in the view
        return instance

    def to_representation(self, instance):
        """Customize the output to show document type names instead of just IDs."""
        representation = super().to_representation(instance)
        document_types = instance.document_types.all()

        # identities_read = representation.pop("identities")

        # it shows the which type of document user have.
        representation["document_types_read"] = [
            {"name": dt.name} for dt in document_types
        ]

        student_id = representation.pop("student")
        teacher_id = representation.pop("teacher")
        office_staff_id = representation.pop("office_staff")
        guardian_id = representation.pop("guardian")

        rep = representation

        try:
            if student_id:
                student = Student.objects.all_including_inactive().get(id=student_id)
                rep["student_id"] = student.id
                rep["student_name"] = (
                    f"{student.user.first_name} {student.user.last_name}"
                )
                studentyearlevel = StudentYearLevel.objects.filter(student_id=student_id).first()
                rep["year_level"] = studentyearlevel.level.level_name if studentyearlevel and studentyearlevel.level else "N/A"
                rep["school_year"] = studentyearlevel.year.year_name if studentyearlevel and studentyearlevel.year else "N/A"
                rep["scholar_number"] = student.scholar_number

            if teacher_id:
                teacher = Teacher.objects.get(id=teacher_id)
                rep["teacher_id"] = teacher.id
                rep["teacher_name"] = (
                    f"{teacher.user.first_name} {teacher.user.last_name}"
                )

            if guardian_id:
                guardian = Guardian.objects.all_including_inactive().get(id=guardian_id)
                rep["guardian_id"] = guardian.id
                rep["guardian_name"] = (
                    f"{guardian.user.first_name} {guardian.user.last_name}"
                )

            if office_staff_id:
                office_staff = OfficeStaff.objects.get(id=office_staff_id)
                rep["office_staff_id"] = office_staff.id
                rep["office_staff_name"] = (
                    f"{office_staff.user.first_name} {office_staff.user.last_name}"
                )

        except User.DoesNotExist:
            rep["user"] = "This user doesn't exist..!"

        return rep


# --------------------exam module
class ExamPaperItemSerializer(serializers.Serializer):
    subject_id = serializers.IntegerField()
    exam_date = serializers.DateField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()


MAX_SUBJECTS_PER_TIMETABLE = 10
from collections import Counter


class ExamScheduleSerializer(serializers.Serializer):
    class_name = serializers.IntegerField()
    term = serializers.IntegerField()          # term selected directly
    exam_type = serializers.IntegerField()
    papers = ExamPaperItemSerializer(many=True)

    def validate_paper_fields(self, paper):
        subject_id = paper.get("subject_id")

        try:
            subject = Subject.objects.get(id=subject_id)
        except Subject.DoesNotExist:
            raise serializers.ValidationError(
                {"subject": f"Subject ID {subject_id} does not exist"}
            )

        exam_date = paper["exam_date"]
        start_time = paper["start_time"]
        end_time = paper["end_time"]

        if exam_date < timezone.localdate():
            raise serializers.ValidationError(
                {"exam_date": "Exam date cannot be in the past"}
            )

        if exam_date.weekday() == 6:
            raise serializers.ValidationError(
                {"exam_date": "Exams cannot be scheduled on Sunday"}
            )

        if start_time >= end_time:
            raise serializers.ValidationError(
                {"time": "Start time must be before end time"}
            )

        start_dt = datetime.combine(exam_date, start_time)
        end_dt = datetime.combine(exam_date, end_time)

        if end_dt - start_dt > timedelta(hours=3):
            raise serializers.ValidationError(
                {"time": "Exam duration cannot exceed 3 hours"}
            )

        allowed_start = dt_time(8, 0)
        allowed_end = dt_time(17, 0)

        if not (allowed_start <= start_time <= allowed_end):
            raise serializers.ValidationError(
                {"start_time": "Exam must start between 8:00 AM – 5:00 PM"}
            )

        if not (allowed_start <= end_time <= allowed_end):
            raise serializers.ValidationError(
                {"end_time": "Exam must end between 8:00 AM – 5:00 PM"}
            )

    def validate(self, data):
        class_id = data["class_name"]
        exam_type_id = data["exam_type"]
        term_id = data["term"]
        papers = data.get("papers", [])

        if not papers:
            raise serializers.ValidationError({"papers": "At least one paper is required"})

        # ---- term validation ----
        try:
            term = Term.objects.get(id=term_id)
        except Term.DoesNotExist:
            raise serializers.ValidationError({"term": "Invalid term selected"})

        # ---- class validation ----
        try:
            class_obj = YearLevel.objects.get(id=class_id)
        except YearLevel.DoesNotExist:
            raise serializers.ValidationError({"class_name": "Invalid class selected"})

        # ---- exam type validation ----
        try:
            exam_type = ExamType.objects.get(id=exam_type_id)
        except ExamType.DoesNotExist:
            raise serializers.ValidationError({"exam_type": "Invalid exam type selected"})

        max_per_date = 3 if class_obj.level_order >= 15 else 1

        # ---- duplicate subject check in payload ----
        subject_ids = [p["subject_id"] for p in papers]
        duplicates = [k for k, v in Counter(subject_ids).items() if v > 1]
        if duplicates:
            duplicate_names = list(Subject.objects.filter(id__in=duplicates).values_list("subject_name", flat=True))
            raise serializers.ValidationError(
                {"papers": f"Duplicate subjects in request: {', '.join(duplicate_names) if duplicate_names else duplicates}. Each subject can only appear once."}
            )

        # ---- check if subjects already scheduled in DB for this class, term, exam type ----
        existing_in_db = ExamSchedule.objects.filter(
            class_name_id=class_id,
            exam_type_id=exam_type_id,
            term_id=term_id,
            subject_id__in=subject_ids
        ).select_related("subject")

        if existing_in_db.exists():
            duplicate_scheduled = [s.subject.subject_name for s in existing_in_db]
            raise serializers.ValidationError(
                {"papers": f"Subject(s) already scheduled for {class_obj.level_name} in this term ({exam_type.name}): {', '.join(duplicate_scheduled)}"}
            )

        # ---- existing schedules total limit ----
        existing_papers = ExamSchedule.objects.filter(
            class_name_id=class_id,
            exam_type_id=exam_type_id,
            term_id=term_id
        )

        total_after_add = existing_papers.count() + len(papers)
        if total_after_add > MAX_SUBJECTS_PER_TIMETABLE:
            raise serializers.ValidationError(
                {
                    "papers": f"Max {MAX_SUBJECTS_PER_TIMETABLE} subjects allowed. "
                              f"Already has {existing_papers.count()}."
                }
            )

        # ---- validate individual papers ----
        for paper in papers:
            self.validate_paper_fields(paper)

        # ---- date-wise validation ----
        date_counter = Counter([str(p.exam_date) for p in existing_papers])
        for p in papers:
            date_counter[str(p["exam_date"])] += 1

        if class_obj.level_order < 15:
            for date_val, count in date_counter.items():
                if count > 1:
                    raise serializers.ValidationError(
                        {"papers": f"{class_obj.level_name} can have only 1 exam on {date_val}"}
                    )
        else:
            over_limit = [d for d, c in date_counter.items() if c > max_per_date]
            if over_limit:
                raise serializers.ValidationError(
                    {"papers": f"Too many exams on {', '.join(over_limit)} (max {max_per_date})"}
                )

        # ---- same subject on same date ----
        subject_dates = [(p["subject_id"], str(p["exam_date"])) for p in papers]
        if len(subject_dates) != len(set(subject_dates)):
            raise serializers.ValidationError(
                {"papers": "Same subject cannot be scheduled twice on same date"}
            )

        return data

    def create(self, validated_data):
        class_id = validated_data["class_name"]
        exam_type_id = validated_data["exam_type"]
        term_id = validated_data["term"]
        papers = validated_data.get("papers", [])

        with transaction.atomic():
            created = []
            for paper in papers:
                schedule = ExamSchedule.objects.create(
                    exam_date=paper["exam_date"],
                    start_time=paper["start_time"],
                    end_time=paper["end_time"],
                    exam_type_id=exam_type_id,
                    class_name_id=class_id,
                    term_id=term_id,
                    subject_id=paper["subject_id"],
                )
                created.append(schedule)

            return created

    def update(self, instance, validated_data):
        class_id = validated_data["class_name"]
        exam_type_id = validated_data["exam_type"]
        term_id = validated_data["term"]
        papers = validated_data.get("papers", [])

        try:
            level = YearLevel.objects.get(id=class_id)
        except YearLevel.DoesNotExist:
            raise serializers.ValidationError({"class_name": "Invalid class selected"})

        try:
            exam_type = ExamType.objects.get(id=exam_type_id)
        except ExamType.DoesNotExist:
            raise serializers.ValidationError({"exam_type": "Invalid exam type"})

        try:
            term = Term.objects.get(id=term_id)
        except Term.DoesNotExist:
            raise serializers.ValidationError({"term": "Invalid term selected"})

        result = []

        with transaction.atomic():
            for paper in papers:
                self.validate_paper_fields(paper)
                subject_id = paper["subject_id"]

                try:
                    schedule = ExamSchedule.objects.get(
                        class_name_id=class_id,
                        exam_type_id=exam_type_id,
                        term_id=term_id,
                        subject_id=subject_id,
                    )
                except ExamSchedule.DoesNotExist:
                    raise serializers.ValidationError(
                        f"Schedule not found for subject ID {subject_id}"
                    )

                except ExamSchedule.MultipleObjectsReturned:
                    subject = Subject.objects.filter(id=subject_id).first()
                    subject_name = subject.subject_name if subject else f"ID {subject_id}"

                    raise serializers.ValidationError(
                        f"Duplicate schedule found for subject '{subject_name}' "
                        f"in class '{level.level_name}', term '{term.term_name}', "
                        f"and exam type '{exam_type.name}'. Please clean up duplicate database records."
                    )

                schedule.exam_date = paper["exam_date"]
                schedule.start_time = paper["start_time"]
                schedule.end_time = paper["end_time"]
                schedule.save()

                subject = Subject.objects.get(id=subject_id)

                result.append(
                    {
                        "subject_name": subject.subject_name,
                        "exam_date": schedule.exam_date.isoformat(),
                        "start_time": schedule.start_time.strftime("%H:%M"),
                        "end_time": schedule.end_time.strftime("%H:%M"),
                        "day": schedule.exam_date.strftime("%A"),
                    }
                )

        return {
            "class": level.level_name,
            "term": f"Term-{term.term_number}",
            "exam_type": exam_type.name,
            "papers": result,
        }

class ExamScheduleTimeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamSchedule
        fields = ["exam_date", "start_time", "end_time"]

    def validate(self, data):
        instance = self.instance

        exam_date = data.get("exam_date", instance.exam_date)
        start_time = data.get("start_time", instance.start_time)
        end_time = data.get("end_time", instance.end_time)

        # ---- date checks ----
        if exam_date < timezone.localdate():
            raise serializers.ValidationError({
                "exam_date": "Exam date cannot be in the past"
            })

        if exam_date.weekday() == 6:
            raise serializers.ValidationError({
                "exam_date": "Exams cannot be scheduled on Sunday"
            })

        # ---- time checks ----
        if start_time >= end_time:
            raise serializers.ValidationError({
                "time": "Start time must be before end time"
            })

        start_dt = datetime.combine(exam_date, start_time)
        end_dt = datetime.combine(exam_date, end_time)

        if end_dt - start_dt > timedelta(hours=3):
            raise serializers.ValidationError({
                "time": "Exam duration cannot exceed 3 hours"
            })

        allowed_start = dt_time(8, 0)
        allowed_end = dt_time(17, 0)

        if not (allowed_start <= start_time <= allowed_end):
            raise serializers.ValidationError({
                "start_time": "Exam must start between 8:00 AM - 5:00 PM"
            })

        if not (allowed_start <= end_time <= allowed_end):
            raise serializers.ValidationError({
                "end_time": "Exam must end between 8:00 AM - 5:00 PM"
            })

        # ---- class-wise daily limit ----
        class_obj = instance.class_name
        max_allowed = 3 if class_obj.level_order >= 15 else 1

        existing_count = ExamSchedule.objects.filter(
            class_name=instance.class_name,
            exam_type=instance.exam_type,
            term=instance.term,
            exam_date=exam_date
        ).exclude(id=instance.id).count()

        if existing_count >= max_allowed:
            raise serializers.ValidationError({
                "exam_date": f"{class_obj.level_name} can have max "
                             f"{max_allowed} exam(s) on {exam_date}"
            })

        return data


class ExamTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamType
        fields = "__all__"


class ExamPaperSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.subject_name", read_only=True)
    year_level_name = serializers.CharField(
        source="year_level.level_name", read_only=True
    )
    exam_name = serializers.CharField(source="exam_type.name", read_only=True)
    teacher_name = serializers.SerializerMethodField()
    year = serializers.CharField(source="term.year.year_name", read_only=True)
    uploaded_file_url = serializers.SerializerMethodField()

    class Meta:
        model = ExamPaper
        fields = [
            "id",
            "subject_name",
            "year_level_name",
            "exam_name",
            "teacher_name",
            "total_marks",
            "paper_code",
            "uploaded_file",
            "year",
            "exam_type",
            "term",
            "subject",
            "year_level",
            "teacher",
            "uploaded_file_url",
        ]
        extra_kwargs = {
            "exam_type": {"write_only": True},
            "term": {"write_only": True},
            "subject": {"write_only": True},
            "year_level": {"write_only": True},
            "teacher": {"write_only": True},
        }

    def get_teacher_name(self, obj):
        if obj.teacher and obj.teacher.user:
            return obj.teacher.user.get_full_name()
        return None

    # def get_uploaded_file_url(self, obj):
    #     import os
    #     from django.conf import settings

    #     if obj.uploaded_file:
    #         file_path = os.path.join(settings.MEDIA_ROOT, obj.uploaded_file.name)
    #         if os.path.exists(file_path):
    #             return obj.uploaded_file.url
    #         else:
    #             return "File has been deleted or not found"
    #     return None
    def get_uploaded_file_url(self, obj):
        # Check if file exists
        if obj.uploaded_file and obj.uploaded_file.storage.exists(
            obj.uploaded_file.name
        ):
            request = self.context.get("request")
            return request.build_absolute_uri(obj.uploaded_file.url)
        return None  # ya "File has been deleted or not found"

    def validate_uploaded_file(self, value):
        # 1. File size check like 5 MB
        MAX_FILE_SIZE = 5 * 1024 * 1024
        file_size = getattr(value, "size", 0)
        if file_size > MAX_FILE_SIZE:
            raise ValidationError(
                f"File size should not exceed {MAX_FILE_SIZE / (1024*1024)} MB."
            )

        # 2. Extension check
        ALLOWED_EXTENSIONS = [".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".gif"]
        file_name = getattr(value, "name", None)
        ext = os.path.splitext(file_name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(f"Files with extension '{ext}' are not allowed.")

        # 3. MIME type check (if available)
        ALLOWED_MIME_TYPES = [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "image/jpeg",
            "image/png",
            "image/gif",
        ]
        file_type = getattr(value, "content_type", None) or getattr(
            getattr(value, "file", None), "content_type", None
        )
        if file_type and file_type not in ALLOWED_MIME_TYPES:
            raise ValidationError(f"Files of type '{file_type}' are not allowed.")
        return value

    def validate_total_marks(self, value):
        if value < 0:
            raise serializers.ValidationError("Total marks cannot be negative.")

        exam_type_id = self.initial_data.get("exam_type")
        if not exam_type_id:
            return value

        try:
            exam_type = ExamType.objects.get(id=exam_type_id)
        except ExamType.DoesNotExist:
            return value

        name = exam_type.name.upper()
        if name in ["SA1", "SA2"] and value > 100:
            raise serializers.ValidationError(
                "Total marks for SA1/SA2 cannot exceed 100."
            )
        elif name in ["FA1", "FA2", "FA3"] and value > 20:
            raise serializers.ValidationError(
                "Total marks for FA1/FA2/FA3 cannot exceed 20."
            )
        return value

    def create(self, validated_data):
        subject = validated_data["subject"]
        exam_type = validated_data["exam_type"]
        term = validated_data["term"]
        year_level = validated_data["year_level"]
        paper_code = validated_data["paper_code"]

        if ExamPaper.objects.filter(
            subject=subject, exam_type=exam_type, term=term, year_level=year_level
        ).exists():
            raise serializers.ValidationError(
                f"Exam paper already exists for subject '{subject.subject_name}', "
                f"class '{year_level.level_name}', year '{term.year.year_name}', and exam '{exam_type.name}'."
            )

        if ExamPaper.objects.filter(paper_code=paper_code).exists():
            raise serializers.ValidationError(
                {"paper_code": ["exam paper with this paper code already exists."]}
            )

        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "subject" in validated_data:
            instance.subject = validated_data["subject"]

        if "teacher" in validated_data:
            instance.teacher = validated_data["teacher"]

        if "paper_code" in validated_data:
            instance.paper_code = validated_data["paper_code"]

        if "total_marks" in validated_data:
            instance.total_marks = validated_data["total_marks"]

        if "year_level" in validated_data:
            instance.year_level = validated_data["year_level"]

        if "term" in validated_data:
            instance.term = validated_data["term"]

        if "exam_type" in validated_data:
            instance.exam_type = validated_data["exam_type"]

        # handle uploaded file
        if "uploaded_file" in validated_data:
            instance.uploaded_file = validated_data["uploaded_file"]

        instance.save()
        return instance


class StudentMarksSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(
        source="teacher.user.first_name", read_only=True
    )
    school_year = serializers.CharField(source="term.year.year_name", read_only=True)
    year_level = serializers.CharField(
        source="student.year_level.level_name", read_only=True
    )
    subject = serializers.CharField(source="subject.subject_name", read_only=True)
    exam_type = serializers.CharField(source="exam_type.name", read_only=True)
    student_name = serializers.CharField(
        source="student.user.first_name", read_only=True
    )
    marks = serializers.DecimalField(
        source="marks_obtained", max_digits=5, decimal_places=2, read_only=True
    )

    class Meta:
        model = StudentMarks
        fields = [
            "id",
            "teacher_name",
            "school_year",
            "year_level",
            "subject",
            "exam_type",
            "student_name",
            "marks",
        ]


"""---------------------------------------------RESULT---------------------------------------------------------------------"""

"""----------------------------------------ReportCardDocument-------------------------------------------------"""


class ReportCardDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportCardDocument
        fields = "__all__"


"""----------------------------------------SubjectScore----------------------------------------------------"""


class StudentMarksMiniSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(
        source="student.user.first_name", read_only=True
    )
    subject_name = serializers.CharField(source="subject.subject_name")
    exam_type = serializers.CharField(source="exam_type.name")
    marks_obtained = serializers.DecimalField(
        decimal_places=2,
        max_digits=5,
        required=False,
        allow_null=True,
        coerce_to_string=False,
    )

    class Meta:
        model = StudentMarks
        fields = ["student_name", "exam_type", "subject_name", "marks_obtained"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        marks = rep.get("marks_obtained")
        try:
            rep["marks_obtained"] = str(marks) if marks is not None else "0.00"
        except:
            rep["marks_obtained"] = "0.00"
        return rep


class SubjectScoreSerializer(serializers.ModelSerializer):
    marks_obtained = StudentMarksMiniSerializer()

    # print("marks_obtained", marks_obtained )
    class Meta:
        model = SubjectScore
        fields = ["marks_obtained"]


"""----------------------------------------NonScholasticGradeTermWise-------------------------------------------------"""


class PersonalSocialQualitySerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonalSocialQuality
        fields = "__all__"


class NonScholasticGradeTermWiseSerializer(serializers.ModelSerializer):
    ALLOWED_GRADES = ["A++", "A+", "A", "B", "C", "D"]

    def validate_non_scholastic_subject(self, subject):

        expected_department = "Non-scholastic"  # change if needed

        if (
            not subject.department
            or subject.department.department_name != expected_department
        ):
            raise serializers.ValidationError(
                f"Subject must belong to the '{expected_department}' department."
            )
        return subject

    def validate_grade(self, value):
        if value not in self.ALLOWED_GRADES:
            raise serializers.ValidationError(
                "Grade must be one of: A++, A+, A, B, C, D."
            )
        return value

    class Meta:
        model = NonScholasticGradeTermWise
        fields = ["id", "report_card", "non_scholastic_subject", "term", "grade"]


"""----------------------------------------PersonalSocialQualityTermWise-------------------------------------------------"""


class PersonalSocialGradeSerializer(serializers.ModelSerializer):

    ALLOWED_GRADES = ["A++", "A+", "A", "B", "C", "D"]

    def validate_grade(self, value):
        if value not in self.ALLOWED_GRADES:
            raise serializers.ValidationError(
                "Grade must be one of: A++, A+, A, B, C, D."
            )
        return value

    class Meta:
        model = PersonalSocialQualityTermWise
        fields = ["id", "report_card", "personal_quality", "term", "grade"]


"""----------------------------------------ReportCard-------------------------------------------------"""


class ReportCardSerializer(serializers.ModelSerializer):
    PersonalSocialQualityTermWise = PersonalSocialGradeSerializer(
        many=True, read_only=True
    )
    subjects = SubjectScoreSerializer(
        many=True, read_only=True, source="subject_scores"
    )

    class Meta:
        model = ReportCard
        fields = [
            "id",
            "student_level",
            "rank",
            "percentage",
            "grade",
            "division",
            "attendance",
            "PersonalSocialQualityTermWise",
            "subjects",
            "teacher_remark",
            "supplementary_in",
            "school_reopen_date",
            "promoted_to_class",
        ]
        read_only_fields = [
            "total_marks",
            "max_marks",
            "percentage",
            "grade",
            "division",
            "subjects",
            "attendance",
            "supplementary_in",
            "promoted_to_class",
        ]

    def get_promoted_to_class(self, obj):
        if obj.promoted_to_class:
            return str(obj.promoted_to_class.level.level_name)
        return "0"


# --------------------- Expense


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = "__all__"

class SchoolExpenseSerializer(serializers.ModelSerializer):
    payment = PaymentSerializer()  # nested write + read
    category_name = serializers.CharField(source="category.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    school_year_name = serializers.CharField(source="school_year.year_name", read_only=True)

    class Meta:
        model = SchoolExpense
        fields = [
            "id",
            "school_year", "school_year_name",
            "category", "category_name",
            "description",
            "payment",
            "created_at",
            "created_by", "created_by_name",
            "approved_by", "approved_by_name",
        ]
        read_only_fields = ["created_at", "created_by", "approved_by"]

    # nested payment create
    def create(self, validated_data):
        payment_data = validated_data.pop("payment")
        payment = Payment.objects.create(**payment_data)

        expense = SchoolExpense.objects.create(
            payment=payment,
            created_by=self.context["request"].user,
            **validated_data
        )
        return expense

    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip()
        return None

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return f"{obj.approved_by.first_name} {obj.approved_by.last_name}".strip()
        return None

    def update(self, instance, validated_data):
        payment_data = validated_data.pop("payment", None)

        # update expense normal fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # update payment nested fields
        if payment_data:
            payment = instance.payment
            for attr, value in payment_data.items():
                setattr(payment, attr, value)
            payment.save()

        return instance

class EmployeeSerializer(serializers.ModelSerializer):
    # role = serializers.CharField(source='user.role', read_only=True)
    # role = RoleSerializer(source='user.role', read_only=True)
    role = serializers.SerializerMethodField()
    name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = Employee
        # fields = "__all__"
        fields = ["id", "user", "name", "role", "base_salary"]
        read_only_fields = ["user"]

    def get_role(self, obj):
        return [role.name for role in obj.user.role.all()]

    def validate_base_salary(self, value):
        if not (1000 <= value <= 100000):
            raise serializers.ValidationError(
                "Base salary must be between 1,000 and 100,000."
            )
        return value


class EmployeeSalarySerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(
        source="user.user.get_full_name", read_only=True
    )
    paid_by_name = serializers.CharField(source="paid_by.get_full_name", read_only=True)
    school_year_name = serializers.SerializerMethodField(read_only=True)

    created_at = serializers.DateTimeField(required=False)
    # cheque_no = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    # cheque_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    fund_account_id = serializers.SerializerMethodField()
    month = serializers.ChoiceField(choices=EmployeeSalary.MONTH_CHOICES)

    status = serializers.CharField(write_only=True, required=False)
    payment_date = serializers.DateField(write_only=True, required=False)
    cheque_number = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    payment = PaymentSerializer(read_only=True)


    class Meta:
        model = EmployeeSalary
        fields = [
            "id",
            "user",
            "employee_name",
            "gross_amount",
            "deductions",
            "bonus",
            "net_amount",
            "month",
            "school_year_name",
            "payment",
            "paid_by",
            "paid_by_name",
            "remarks",
            "created_at",
            "payment_method",
            "cheque_number",
            "fund_account_id",
            "payment_status","status","payment_date",
            # "cheque_no"
        ]
        extra_kwargs = {
            "user": {"required": False},
            "month": {"required": False},
            "gross_amount": {"read_only": True},
            "net_amount": {"read_only": True},
            "paid_by": {"read_only": True},
            "school_year": {"read_only": True},
        }

    def get_payment_status(self, obj):
        return obj.payment.status if obj.payment else None

    def get_payment_method(self, obj):
        return obj.payment.payment_method if obj.payment else None

    # def get_cheque_no(self, obj):
    #     return obj.payment.cheque_number if obj.payment else None

    def get_fund_account_id(self, obj):
        return obj.payment.fund_account_id if obj.payment else None

    def validate(self, attrs):
        data = self.initial_data  # original input
        payment_method = data.get("payment_method")
        cheque_number = data.get("cheque_number")
        fund_account_id = data.get("fund_account_id")
        deductions = attrs.get("deductions", 0)
        bonus = attrs.get("bonus", 0)
        user = attrs.get("user")
        payment_date = data.get("payment_date")  # from input

        # Deduction cannot exceed gross amount
        if user:
            gross = user.base_salary
            if deductions > gross:
                raise serializers.ValidationError(
                    {"deductions": "Deductions cannot be more than gross amount."}
                )

            net_amount = gross + bonus - deductions
            if net_amount <= 0:
                raise serializers.ValidationError(
                    {"net_amount": "Net amount cannot be zero or negative."}
                )

        # Cash payment: cheque number should not be provided
        if payment_method == "Cash" and cheque_number:
            raise serializers.ValidationError(
                {
                    "cheque_number": "Cheque number should not be provided for cash payment."
                }
            )

        # Cheque payment: cheque number is required
        if payment_method == "Cheque" and not cheque_number:
            raise serializers.ValidationError(
                {"cheque_number": "Cheque number is required for cheque payment."}
            )

        # Online payment: fund_account_id required
        if payment_method == "Online" and not fund_account_id:
            raise serializers.ValidationError(
                {"fund_account_id": "Fund account ID is required for online payment."}
            )

        # Payment date cannot be in the future
        if payment_date:
            try:
                payment_date_obj = date.fromisoformat(payment_date)
                if payment_date_obj > date.today():
                    raise serializers.ValidationError(
                        {"payment_date": "Payment date cannot be in the future."}
                    )
            except ValueError:
                raise serializers.ValidationError(
                    {"payment_date": "Invalid date format."}
                )

        return attrs

    def validate_created_at(self, value):

        if isinstance(value, str) and len(value) == 10:  # YYYY-MM-DD
            value = datetime.strptime(value, "%Y-%m-%d")
        return value

    def get_school_year_name(self, obj):
        return obj.school_year.year_name if obj.school_year else None

    def validate_cheque_number(self, value):
        if not value:
            return value
        # check uniqueness in Payment model
        qs = Payment.objects.filter(cheque_number=value)
        if self.instance and self.instance.payment:
            qs = qs.exclude(pk=self.instance.payment.pk)
        if qs.exists():
            raise serializers.ValidationError("This cheque number is already used.")
        return value

    def validate_created_at(self, value):
        # Future date check
        if value.date() > date.today():
            raise serializers.ValidationError("created_at cannot be in the future.")

        return value


class IncomeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = IncomeCategory
        fields = "__all__"


class SchoolIncomeSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    creator = serializers.SerializerMethodField()
    school_year_value = serializers.SerializerMethodField()
    attachment_url = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = SchoolIncome
        fields = "__all__"
        read_only_fields = [
            "created_at",
            "creator",
            "school_year_value",
            "attachment_url",
        ]

    def get_creator(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip()
        return None

    def get_school_year_value(self, obj):
        return obj.school_year.year_name if obj.school_year else None

    def get_attachment_url(self, obj):
        request = self.context.get("request")
        if obj.attachment:
            if request:
                return request.build_absolute_uri(obj.attachment.url)
            # fallback agar request nahi mila
            return obj.attachment.url

    def get_created_at(self, obj):
        return timezone.localtime(obj.created_at).strftime("%d-%m-%Y %I:%M %p")

    def validate_attachment(self, value):
        if not value:
            return value

        # File size check (2 MB max)
        max_size = 2 * 1024 * 1024  # 2 MB
        if value.size > max_size:
            raise serializers.ValidationError("File size must be under 2MB.")

        # File extension check.
        ext = os.path.splitext(value.name)[1].lower()
        allowed_extensions = [".jpg", ".jpeg", ".png", ".webp", ".pdf"]
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f"Unsupported file type '{ext}'. Allowed types are: {', '.join(allowed_extensions)}"
            )
        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["school_year"] = self.get_school_year_value(instance)
        return data

    def validate(self, data):
        category = data.get("category")
        month = data.get("month")
        school_year = data.get("school_year")
        income_date = data.get("income_date")

        # Ensure amount is positive (skip for Monthly Fees, it gets auto-set later)
        if category and category.name != "Monthly Fees":
            if data.get("amount", 0) <= 0:
                raise serializers.ValidationError("Amount must be a positive number.")

        # Ensure income date is not in the future
        if income_date and income_date > date.today():
            raise serializers.ValidationError("Income date cannot be in the future.")

        # Ensure income date should be of current year
        if income_date and income_date < date(date.today().year, 1, 1):
            raise serializers.ValidationError("Income date should be of current year.")

        # Ensure one category per month per school_year
        if category and month and school_year:
            qs = SchoolIncome.objects.filter(
                category=category, month=month, school_year=school_year
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    f"Income for '{category.name}' already exists for {month} ({school_year})."
                )

        return data

    # def create(self, validated_data):
    #     # Auto-assign creator
    #     request = self.context.get("request")
    #     if request and hasattr(request, "user"):
    #         validated_data["created_by"] = request.user

    #     school_year = validated_data["school_year"]   # this is a SchoolYear instance
    #     month = validated_data["month"]               # pull from validated_data
    #     category = validated_data.get("category")

    #     # Auto-set amount for Monthly Fees
    #     if category and category.name == "Monthly Fees":
    #         total = (
    #             FeeRecord.objects.filter(
    #                 month=month,
    #                 school_year__year=school_year   # StudentYearLevel.year → SchoolYear
    #             ).aggregate(total=Sum("paid_amount"))["total"] or 0
    #         )
    #         validated_data["amount"] = total

    #     return super().create(validated_data)

    def update(self, instance, validated_data):
        allowed_fields = [
            "amount",
            "description",
            "income_date",
            "payment_method",
            "attachment",
            "status",
        ]

        # block updates for restricted fields (category, school_year, created_by etc.)
        for field in list(validated_data.keys()):
            if field not in allowed_fields:
                validated_data.pop(field)

        # special rule: "Monthly Fees" → amount cannot be updated
        category = instance.category
        if category and category.name == "Monthly Fees":
            validated_data.pop("amount", None)

        return super().update(instance, validated_data)


class SchoolTurnOverSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolTurnOver
        fields = [
            "id",
            "school_year",
            "carry_forward",
            "total_income",
            "total_expense",
            "financial_outcome",
            "financial_status",
            "net_turnover",
            "calculated_at",
            "is_locked",
            "verified_by",
            "verified_at",
        ]


class MasterFeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MasterFee
        fields = "__all__"


class FeeStructureSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    student_fee_count = serializers.IntegerField(read_only=True)
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = FeeStructure
        fields = [
            'id',
            'school_year',
            'master_fee',
            'fee_type',
            'tuition_sub_type',
            'fee_amount',
            'year_level',
            'display_name',
            "student_fee_count",
            "can_delete",
        ]

    def get_display_name(self, obj):
        return obj.display_name()

    def get_can_delete(self, obj):
        if hasattr(obj, 'student_fee_count'):
            return obj.student_fee_count == 0
        return obj.student_fees.count() == 0

    def validate(self, data):
        fee_type = data.get('fee_type')
        tuition_sub_type = data.get('tuition_sub_type')

        if fee_type == 'Tuition Fee' and not tuition_sub_type:
            raise serializers.ValidationError({
                "tuition_sub_type": "Sub-type is required for Tuition Fee."
            })
        if fee_type != 'Tuition Fee' and tuition_sub_type:
            raise serializers.ValidationError({
                "tuition_sub_type": "Sub-type is only allowed for Tuition Fee."
            })
        return data


class AppliedFeeDiscountSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    fee_type_name = serializers.SerializerMethodField()
    discounted_amount_percent = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField() 
    year_level = serializers.SerializerMethodField()   

    class Meta:
        model = AppliedFeeDiscount
        fields = [
            "id",
            "student",
            "year_level",
            "student_name",
            "fee_type",
            "fee_type_name",
            "discount_name",
            "discount_amount",
            "discounted_amount_percent",
            "approved_by_name",
            "approved_by",
            "approved_at",
        ]

    def get_student_name(self, obj):
        student = (
            obj.student.student
        )  
        return f"{student.user.first_name} {student.user.last_name}"
    
    def get_year_level(self, obj):
        return obj.student.level.level_name if obj.student and obj.student.level else None

    def get_fee_type_name(self, obj):
        return obj.fee_type.display_name()  

    def get_discounted_amount_percent(self, obj):
        try:
            discount = Decimal(obj.discount_amount or 0)
            original = Decimal(obj.fee_type.fee_amount or 0)
            if original == 0:
                return 0
            return float((discount / original) * Decimal("100"))
        except Exception:
            return 0

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            name = f"{obj.approved_by.first_name} {obj.approved_by.last_name}".strip()
            # print(name)
            return name if name else obj.approved_by.username
        return None


class FeePaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeePayment
        fields = "__all__"


class StudentFeeSerializer(serializers.ModelSerializer):
    student_year_id = serializers.IntegerField(write_only=True, required=False)
    fee_structure_id = serializers.IntegerField(write_only=True, required=False)
    school_year_id = serializers.IntegerField(write_only=True, required=False)
    amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2, write_only=True, required=False)
    payment_method = serializers.ChoiceField(choices=FeePayment._meta.get_field("payment_method").choices,write_only=True,required=False,)
    student_year = serializers.PrimaryKeyRelatedField(read_only=True)
    fee_structure = serializers.PrimaryKeyRelatedField(read_only=True)
    school_year = serializers.PrimaryKeyRelatedField(read_only=True)
    # original_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    original_amount = serializers.SerializerMethodField()
    paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    due_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    month_name = serializers.SerializerMethodField()
    student_name = serializers.SerializerMethodField()
    student_class = serializers.SerializerMethodField()
    school_year_name = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    fee_status = serializers.CharField(source="status", read_only=True, required=False)
    fee_type = serializers.SerializerMethodField()
    tuition_sub_type = serializers.SerializerMethodField()
    payment_method_output = serializers.SerializerMethodField()
    cheque_number = serializers.CharField(write_only=True, required=False, allow_blank=True)
    scholar_number = serializers.SerializerMethodField()

    class Meta:
        model = StudentFee
        fields = [
            "id",
            "student_year",
            "student_year_id",
            "student_name",
            "student_class",
            "month",
            "month_name",
            "school_year",
            "school_year_id",
            "school_year_name",
            "fee_structure",
            "fee_structure_id",
            "fee_type",
            "tuition_sub_type",
            "payment_method_output",
            "original_amount",
            "paid_amount",
            "due_amount",
            # "penalty_amount",
            "payment_status",
            "fee_status",
            "due_date",
            "applied_discount",
            "created_at",
            "updated_at",
            "amount_paid",
            "payment_method",
            "cheque_number",
            "receipt_number",
            "scholar_number"
        ]
        read_only_fields = [
            "student_year",
            "fee_structure",
            "school_year",
            "original_amount",
            "paid_amount",
            "due_amount",
        ]

    def get_payment_status(self, obj):
        last_payment = obj.payments.order_by("-payment_date").first()
        if last_payment:
            return last_payment.status
        return "pending"

    def get_fee_type(self, obj):
        return obj.fee_structure.display_name()  

    def get_tuition_sub_type(self, obj):
        return obj.fee_structure.tuition_sub_type

    def get_payment_method_output(self, obj):
        last_payment = obj.payments.order_by("-payment_date").first()
        return last_payment.payment_method if last_payment else None

    def get_student_class(self, obj):
        return obj.student_year.level.level_name  

    def get_month_name(self, obj):
        if obj.month and 1 <= obj.month <= 12:
            year = get_fee_due_year(obj.school_year, obj.month)
            return f"{calendar.month_name[obj.month]}{year}"
        return None  # yearly fee — no month applies

    def get_student_name(self, obj):
        student = obj.student_year.student
        return f"{student.user.first_name} {student.user.last_name}"


    def get_scholar_number(self, obj):
        if obj.student_year and obj.student_year.student:
            return obj.student_year.student.scholar_number
        return None


    def get_school_year_name(self, obj):
        return obj.school_year.year_name


    def get_original_amount(self, obj):
        discount_obj = AppliedFeeDiscount.objects.filter(
            student=obj.student_year,
            fee_type=obj.fee_structure
        ).first()

        discount_amount = Decimal(
            str(discount_obj.discount_amount if discount_obj else 0)
        ).quantize(Decimal("0.01"))

        discounted_amount = (obj.original_amount - discount_amount).quantize(Decimal("0.01"))

        return str(discounted_amount)


    def create(self, validated_data):
        request = self.context.get("request")
        payment_method = validated_data.get("payment_method") or self.context.get("payment_method")
        cheque_number = validated_data.get("cheque_number")

        # if payment_method.lower() == "cheque" and not cheque_number:
        #     raise serializers.ValidationError("Cheque number is required when payment method is cheque.")

        if not payment_method:
            raise serializers.ValidationError("Payment method is required.")

        if request and "submit_fee" in str(request.path):
            student_year = StudentYearLevel.objects.get(id=validated_data["student_year_id"])
            fee_structure = FeeStructure.objects.get(id=validated_data["fee_structure_id"])
            school_year = student_year.year
            month = validated_data.get("month")
            amount_paid = Decimal(validated_data.get("amount_paid", "0.00"))
            user = request.user

            if not fee_structure.year_level.filter(id=student_year.level.id).exists():
                raise serializers.ValidationError(
                    f"The selected fee ({fee_structure.fee_type}) does not belong to the student's class ({student_year.level.level_name})."
                )

            applied_discount_obj = AppliedFeeDiscount.objects.filter(
                student_id=student_year.student.id, fee_type=fee_structure
            ).first()

            if applied_discount_obj:
                discounted_amount = Decimal(fee_structure.fee_amount) - Decimal(applied_discount_obj.discount_amount)
                discount_applied_flag = True
            else:
                discounted_amount = Decimal(fee_structure.fee_amount)
                discount_applied_flag = False

            student_fee, created = StudentFee.objects.get_or_create(
                student_year=student_year,
                fee_structure=fee_structure,
                school_year=school_year,
                month=month,
                defaults={
                    "original_amount": discounted_amount,
                    "paid_amount": Decimal("0.00"),
                    "due_amount": discounted_amount,
                    "applied_discount": discount_applied_flag,
                    "due_date": validated_data.get("due_date"),
                },
            )

            if not created and applied_discount_obj and not student_fee.applied_discount:
                student_fee.original_amount = discounted_amount
                student_fee.due_amount = discounted_amount - student_fee.paid_amount
                student_fee.applied_discount = True
                student_fee.save()

            # Calculate due amount
            student_fee.due_amount = (
                student_fee.original_amount 
                - student_fee.paid_amount
            )

            # Validate payment
            if amount_paid > student_fee.due_amount:
                raise serializers.ValidationError(f"Amount cannot exceed due amount: {student_fee.due_amount}")

            student_fee.due_amount = max(student_fee.original_amount - student_fee.paid_amount, Decimal("0.00"))

            payment_mode = request.data.get("payment_method", "").lower()

            if payment_mode == "online":
                student_fee.status = "pending"
            else:
                student_fee.paid_amount += amount_paid
                student_fee.due_amount = student_fee.original_amount - student_fee.paid_amount
                if student_fee.due_amount <= 0:
                    student_fee.status = "paid"
                elif student_fee.paid_amount > 0:
                    student_fee.status = "partial"
                else:
                    student_fee.status = "pending"


            student_fee.save()
            return student_fee

        return super().create(validated_data)



