from django.http import HttpResponse
from django.forms import DateField, ValidationError
import requests
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Count, Prefetch
from collections import OrderedDict
from attendance.models import Attendance
from director.permission import *
from director.utils import (
    calculate_subject_summary,
    icici_generate_merchant_txn_no,
    icici_normalize_amount,
    icici_secure_hash_v1,
    icici_secure_hash_v2,
)
from rest_framework.exceptions import ValidationError
from director.permission import IsDirectororOfficeStaff, IsDirector, RoleBasedExamPermission, RoleBasedPermission
from student.pagination import CreatePagination

from .serializers import *
from rest_framework import filters
from .models import *
from rest_framework .views import APIView       # As of 07May25 at 12:30 PM
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from django.db.models import Sum
from rest_framework.decorators import action
from django.utils.dateparse import parse_date

from rest_framework.exceptions import PermissionDenied
from django.db.models.functions import Coalesce
from django.db.models import Sum, DecimalField
# views.py

from django.db.models import Count, F, ExpressionWrapper, IntegerField ,Func , Value
# from razorpay.errors import SignatureVerificationError, InvalidOperation # as of 04Oct25
from razorpay.errors import SignatureVerificationError
from decimal import Decimal, InvalidOperation 

import razorpay
from django.conf import settings
from django.shortcuts import get_object_or_404
from datetime import datetime
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import viewsets, status
import json  #  This goes at the top of the file
from django.db.models import Q
from collections import OrderedDict, defaultdict, Counter
from datetime import datetime, timedelta, time as dt_time
from django.utils.timezone import now, make_aware
from django.db.models.functions import Cast
from teacher.models import Teacher, TeacherYearLevel
from django.db.models import OuterRef, Subquery, Sum, Value, FloatField
from requests.auth import HTTPBasicAuth
import calendar
import random
import string
from django.db.models import Sum, F, Value, DecimalField
from django.db.models import Q, Sum, Value, FloatField
from django.db.models.fields import DateField  # This avoids shadowing
from decimal import Decimal, InvalidOperation # added as of 04Oct25
from razorpay.errors import SignatureVerificationError  # added as of 04Oct25
from decimal import ROUND_HALF_UP
import datetime
from rest_framework import status as drf_status
from datetime import datetime, date

from .utils import _calculate_student_totals



### Function to generate auto receipt no. called it inside initiate payment
# ---------------------------------------------------------------------------------------------------------------------------------------------         

#    Document fetch dashboard

@api_view(["GET"])
def document_fetch_dashboard(request):
    user_type = request.query_params.get('user_type')        # student, teacher, etc.
    uploaded = request.query_params.get('uploaded')          # true / false
    class_id = request.query_params.get('class')             # e.g., 1, 2 (level_id)

    data = []

    def format_entry(instance, type_label, has_doc, class_label):
        name = f"{instance.user.first_name} {instance.user.last_name}" if instance.user else "N/A"
        return {
            "user_type": type_label,
            "name": name,
            "has_uploaded_document": has_doc,
            "class": class_label
        }

    def get_class(instance, label):
        if label == "student":
            return StudentYearLevel.objects.filter(student=instance, student__is_active=True).select_related("level").first()
        elif label == "teacher":
            return TeacherYearLevel.objects.filter(teacher=instance, teacher__is_active=True).select_related("year_level").first()
        elif label == "guardian":
            student_guardian = StudentGuardian.objects.filter(guardian=instance, student__is_active=True).select_related("student").first()
            if student_guardian and student_guardian.student:
                student = student_guardian.student
                return StudentYearLevel.objects.filter(student=student, student__is_active=True).select_related("level").first()
            return None
        elif label == "office_staff":
            return None
        else:
            return None

    def process_queryset(queryset, label, doc_field):
        for instance in queryset:
            has_doc = Document.objects.filter(**{doc_field: instance}).exists()

            # Uploaded filter
            if uploaded == "true" and not has_doc:
                continue
            if uploaded == "false" and has_doc:
                continue

            class_obj = get_class(instance, label)
            if class_obj:
                level_id = class_obj.level.id if label in ["student", "guardian"] else class_obj.year_level.id
                level_name = class_obj.level.level_name if label in ["student", "guardian"] else class_obj.year_level.level_name
            else:
                level_id = None
                level_name = "N/A" if label == "office_staff" else "Unknown"

            # Class ID filter
            if class_id and str(level_id) != class_id:
                continue

            data.append(format_entry(instance, label, has_doc, level_name))

    # Main filtering logic
    if user_type == "student" or user_type is None:
        process_queryset(Student.objects.filter(is_active=True), "student", "student")

    if user_type == "teacher" or user_type is None:
        process_queryset(Teacher.objects.filter(is_active=True), "teacher", "teacher")

    if user_type == "guardian" or user_type is None:
        process_queryset(Guardian.objects.filter(is_active=True), "guardian", "guardian")

    if user_type == "office_staff" or user_type is None:
        process_queryset(OfficeStaff.objects.filter(is_active=True), "office_staff", "office_staff")

    if user_type not in ["student", "teacher", "guardian", "office_staff", None]:
        return Response({"error": "Invalid user_type"}, status=status.HTTP_400_BAD_REQUEST)

    return Response(data)




# user_type=student|teacher|guardian|office_staff

# uploaded=true|false

# class=Nursery|KG|Class 1|





#  ____________________________________________________________ class period view  ____________________________________________________________

@api_view(['GET'])
def assigned_periods(request):
    year_level_id = request.query_params.get("year_level_id")

    if not year_level_id:
        return Response({"error": "year_level_id query parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        year_level = YearLevel.objects.get(id=year_level_id)
    except YearLevel.DoesNotExist:
        return Response({"error": "YearLevel not found"}, status=status.HTTP_404_NOT_FOUND)

    class_periods = ClassPeriod.objects.filter(year_level=year_level)

    assigned_periods = []
    for period in class_periods:
        assigned_periods.append({
            "subject": str(period.subject),
            "teacher": str(period.teacher),
            "start_time": period.start_time.start_period_time.strftime('%I:%M %p'),
            "end_time": period.end_time.end_period_time.strftime('%I:%M %p'),
        })

    return Response({
        "class": year_level.level_name,
        "total_periods": class_periods.count(),
        "assigned_periods": assigned_periods
    })


#   ---------------------------------------------  Director Dashboard view   ----------------------------------------------------------

@api_view(["GET"])
def Director_Dashboard_Summary(request):
    current_date = datetime.now().date()

    # Get current SchoolYear (academic year)
    current_school_year = (
        SchoolYear.objects
        .filter(start_date__lte=current_date, end_date__gte=current_date)
        .order_by('-start_date')
        .first()
    )

    if current_school_year:
        new_admissions_count = Admission.objects.filter(school_year=current_school_year).count()
    else:
        new_admissions_count = 0

    summary = {
        "new_admissions": new_admissions_count,
        "students": Student.objects.filter(is_active=True).count(),
        "teachers": Teacher.objects.filter(is_active=True).count()
    }

    student_total = summary["students"]
    teacher_total = summary["teachers"]

    # Gender count
    student_male = Student.objects.filter(is_active=True, gender__iexact="Male").count()
    student_female = Student.objects.filter( is_active=True, gender__iexact="Female").count()

    teacher_male = Teacher.objects.filter(is_active=True, gender__iexact="Male").count()
    teacher_female = Teacher.objects.filter(is_active=True, gender__iexact="Female").count()

    def get_percentage(count, total):
        return round((count / total) * 100, 2) if total else 0

    gender_distribution = {
        "students": {
            "count": {
                "male": student_male,
                "female": student_female
            },
            "percentage": {
                "male": get_percentage(student_male, student_total),
                "female": get_percentage(student_female, student_total)
            },
        },
        "teachers": {
            "count": {
                "male": teacher_male,
                "female": teacher_female
            },
            "percentage": {
                "male": get_percentage(teacher_male, teacher_total),
                "female": get_percentage(teacher_female, teacher_total)
            },
        }
    }

    # Class-wise strength - ACTIVE students only
    class_data = (
        StudentYearLevel.objects
        .filter(student__is_active=True)
        .values("level__level_name")
        .annotate(total=Count("student", distinct=True))
    )

    class_strength = {
        entry["level__level_name"]: entry["total"]
        for entry in class_data
    }

    # Academic Year-wise strength - ACTIVE students only
    school_years = SchoolYear.objects.order_by("start_date")
    students_per_year = OrderedDict()

    for year in school_years:
        year_range = f"{year.start_date.year}-{year.end_date.year}"

        count = (
            StudentYearLevel.objects
            .filter(
                year=year,
                student__is_active=True
            )
            .values("student")
            .distinct()
            .count()
        )

        students_per_year[year_range] = count

    return Response({
        "summary": summary,
        "gender_distribution": gender_distribution,
        "class_strength": class_strength,
        "students_per_year": students_per_year
    })



# ---------------------------------------------------------   Teacher Dashboard View  ----------------------------------------------------------


@api_view(["GET"])
def teacher_dashboard(request, id):
    try:
        teacher = Teacher.objects.get(user_id=id, is_active=True)
        teacher_name = f"{teacher.user.first_name} {teacher.user.last_name}" if teacher.user else "N/A"

       
        assigned_levels = TeacherYearLevel.objects.filter(teacher=teacher).select_related("year_level")

        class_summary = []

        for assigned in assigned_levels:
            level = assigned.year_level
            level_name = level.level_name

            total_students = StudentYearLevel.objects.filter(level=level, student__is_active=True).count()

            class_period = ClassPeriod.objects.filter(
                teacher=teacher,
                classroom__isnull=False
            ).select_related("classroom").first()

            room_name = class_period.classroom.room_name if class_period and class_period.classroom else None

            class_summary.append({
                "level_name": level_name,
                "total_students": total_students,
                "room_name": room_name
            })

        return Response({
            "teacher_name": teacher_name,
            "total_assigned_classes": len(class_summary),
            "class_summary": class_summary
        })

    except Teacher.DoesNotExist:
        return Response({"error": "Teacher not found"}, status=404)


# --------------------------------------------------------- Guardian Dashboard View  ----------------------------------------------------------
@api_view(["GET"])
def guardian_dashboard(request, id=None):
    if not id:
        return Response({"error": "Guardian ID is required"}, status=400)

    try:
        guardian = Guardian.objects.get(user_id=id, is_active=True)
    except Guardian.DoesNotExist:
        return Response({"error": "Guardian not found"}, status=404)

    student_links = StudentGuardian.objects.filter(guardian=guardian, student__is_active=True)
    children_data = []

    for link in student_links:
        student = link.student
        if not student:
            continue

        # Latest class info (YearLevel + SchoolYear)
        year_level_info = StudentYearLevel.objects.filter(student=student).last()
        student_name = f"{student.user.first_name} {student.user.last_name}" if student.user else "N/A"

        children_data.append({
            "student_name": student_name,
            "class": f"{year_level_info.level.level_name} ({year_level_info.year.year_name})"
            if year_level_info and year_level_info.level and year_level_info.year else "Not Assigned"
        })

    guardian_name = f"{guardian.user.first_name} {guardian.user.last_name}" if guardian.user else "N/A"
    return Response({
        "guardian": guardian_name,
        "total_children": student_links.count(),
        "children": children_data
    })


#  ----------------------------------------------------------------- Student Dashboard View --------------------------------------------------

@api_view(["GET"])
def student_dashboard(request, id=None):
    if not id:
        return Response({"error": "Student ID is required"}, status=400)

    try:
        student = Student.objects.get(user_id=id, is_active=True)
    except Student.DoesNotExist:
        return Response({"error": "Student not found"}, status=404)

    # Get optional year_level_id from query params
    year_level_id = request.query_params.get("year_level_id")

    # Filter year level info
    year_level_info = None
    if year_level_id:
        year_level_info = StudentYearLevel.objects.filter(student=student, level_id=year_level_id).last()
    else:
        year_level_info = StudentYearLevel.objects.filter(student=student).last()

    # Guardian details
    guardian_links = StudentGuardian.objects.filter(student=student, guardian__is_active=True)
    guardians_data = []

    for link in guardian_links:
        guardian = link.guardian
        if guardian and guardian.user:
            guardians_data.append({
                "guardian_name": f"{guardian.user.first_name} {guardian.user.last_name}"
            })

    # Child info output
    children_data = []
    student_name = f"{student.user.first_name} {student.user.last_name}" if student.user else "N/A"

    if year_level_info and year_level_info.level and year_level_info.year:
        children_data.append({
            "student_id": student.id,
            "student_name": student_name,
            "class": f"{year_level_info.level.level_name} ({year_level_info.year.year_name})",
            "year_level_id": year_level_info.level.id
        })
    else:
        children_data.append({
            "student_id": student.id,
            "student_name": student_name,
            "class": "Not Assigned",
            "year_level_id": None
        })

    return Response({
        "guardian": guardians_data,
        "total_children": 1,
        "children": children_data
    })


# --------------------------------------------------------- office Staff Dashboard View  ----------------------------------------------------------
@api_view(["GET"])
def office_staff_dashboard(request):
    staff = OfficeStaff.objects.filter(is_active=True).first()
    if not staff or not staff.user:
        return Response({"error": "No office staff found"}, status=404)

    current_date = datetime.now().date()

    current_year = (
        SchoolYear.objects
        .filter(start_date__lte=current_date, end_date__gte=current_date)
        .order_by('-start_date')
        .first()
    )

    if not current_year:
        return Response({"error": "Current academic year not found"}, status=404)

    # Academic Year-wise Admissions & Students
    school_years = SchoolYear.objects.order_by("start_date")
    admissions_trend = OrderedDict()
    students_per_year = OrderedDict()

    for year in school_years:
        year_range = f"{year.start_date.year}-{year.end_date.year}"

        # New logic (based on ForeignKey)
        admissions_count = Admission.objects.filter(school_year=year, is_active=True).count()

        admissions_trend[year_range] = admissions_count

        # Students enrolled in that academic year
        students_count = StudentYearLevel.objects.filter(year=year, student__is_active=True).count()
        students_per_year[year_range] = students_count

    # Current year admissions
    new_admissions = admissions_trend.get(
        f"{current_year.start_date.year}-{current_year.end_date.year}", 0
    )

    total_admissions = sum(admissions_trend.values())

    return Response({
        # "staff_name": f"{staff.user.first_name} {staff.user.last_name}",
        "current_academic_year": f"{current_year.start_date.year}-{current_year.end_date.year}",
        "new_admissions_this_year": new_admissions,
        "admissions_per_year": admissions_trend,
        "total_admissions": total_admissions,
        "students_per_year": students_per_year
    })



#------------------------------------------------- Student Fees summary view ---------------------------------------------------

@api_view(["GET"])
def student_fee_dashboard(request):
    student_id = request.query_params.get("student_id")

    if not student_id:
        return Response(
            {"message": "student_id is required as param"},
            status=400
        )

    try:
        student = Student.objects.select_related("user").get(id=student_id, is_active=True)
    except Student.DoesNotExist:
        return Response({"message": "Student not found"}, status=404)

    student_year = (
        StudentYearLevel.objects
        .filter(student=student)
        .select_related("level", "year")
        .order_by("-id")
        .first()
    )

    if not student_year:
        return Response({"message": "Student year record not found"}, status=404)

    fees_qs = StudentFee.objects.filter(student_year=student_year)

    agg = fees_qs.aggregate(
        total_fee=Coalesce(
            Sum(
                F("original_amount"),# + F("penalty_amount"),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            Value(Decimal("0.00"), output_field=DecimalField())
        ),
        paid_fee=Coalesce(
            Sum("paid_amount", output_field=DecimalField()),
            Value(Decimal("0.00"), output_field=DecimalField())
        ),
        due_fee=Coalesce(
            Sum("due_amount", output_field=DecimalField()),
            Value(Decimal("0.00"), output_field=DecimalField())
        ),
    )

    return Response({
        "student": {
            "id": student.id,
            "name": f"{student.user.first_name} {student.user.last_name}",
            "scholar_number": student.scholar_number,
        },
        "class": student_year.level.level_name,
        "school_year": student_year.year.year_name,
        "fee_summary": {
            "total_fee": round(agg["total_fee"], 2),
            "paid_fee": round(agg["paid_fee"], 2),
            "due_fee": round(agg["due_fee"], 2),
        }
    })


# ------------------------------------------------ Director Fees summary view -----------------------------------------------------------

@api_view(["GET"])
def director_fee_summary(request):
    month = request.GET.get("month")

    fee_qs = StudentFee.objects.select_related(
        "student_year__student",
        "student_year__level"
    )

    # ---------- MONTH FILTER ----------
    if month:
        try:
            month_number = list(calendar.month_name).index(month)
            fee_qs = fee_qs.filter(month=month_number)
        except ValueError:
            pass

    # ---------- SCHOOL LEVEL SUMMARY ----------
    total_students = Student.objects.filter(is_active=True).count()

    school_agg = fee_qs.aggregate(
        total_fee=Coalesce(
            Sum(
                F("original_amount"),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            Value(Decimal("0.00"), output_field=DecimalField())
        ),
        paid_fee=Coalesce(
            Sum("paid_amount", output_field=DecimalField()),
            Value(Decimal("0.00"), output_field=DecimalField())
        ),
        due_fee=Coalesce(
            Sum("due_amount", output_field=DecimalField()),
            Value(Decimal("0.00"), output_field=DecimalField())
        ),
    )

    # ---------- CLASS WISE SUMMARY ----------
    class_data = (
        fee_qs.values(
            "student_year__level__id",
            "student_year__level__level_name"
        )
        .annotate(
            total_students=Count(
                "student_year__student",
                distinct=True
            ),
            total_fee=Coalesce(
                Sum(
                    F("original_amount"),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                ),
                Value(Decimal("0.00"), output_field=DecimalField())
            ),
            paid_fee=Coalesce(
                Sum("paid_amount", output_field=DecimalField()),
                Value(Decimal("0.00"), output_field=DecimalField())
            ),
            due_fee=Coalesce(
                Sum("due_amount", output_field=DecimalField()),
                Value(Decimal("0.00"), output_field=DecimalField())
            ),
        )
        .order_by("student_year__level__level_name")
    )

    class_summary = [
        {
            "class_id": row["student_year__level__id"],
            "class_name": row["student_year__level__level_name"],
            "total_students": row["total_students"],
            "total_fee": round(row["total_fee"], 2),
            "paid_fee": round(row["paid_fee"], 2),
            "due_fee": round(row["due_fee"], 2),
        }
        for row in class_data
    ]

    return Response({
        "school_summary": {
            "total_students": total_students,
            "total_fee": round(school_agg["total_fee"], 2),
            "paid_fee": round(school_agg["paid_fee"], 2),
            "due_fee": round(school_agg["due_fee"], 2),
        },
        "class_summary": class_summary
    })


@api_view(["GET"])
def NewAdmissionsList(request):
    current_date = datetime.now().date()

    current_school_year = (
        SchoolYear.objects.filter(
            start_date__lte=current_date,
            end_date__gte=current_date
        )
        .order_by("-start_date")
        .first()
    )

    if not current_school_year:
        return Response({
            "count": 0,
            "results": []
        })

    admissions = (
        Admission.objects.filter(
            school_year=current_school_year,
            is_active=True
        )
        .select_related(
            "student",
            "student__user",
            "guardian",
            "guardian__user",
            "year_level",
            "school_year",
        )
        .prefetch_related(
            Prefetch(
                "student__student_year_levels",
                queryset=StudentYearLevel.objects.filter(
                    year=current_school_year
                ).select_related("level"),
                to_attr="current_student_year_level"
            )
        )
        .order_by("-admission_date", "-id")
    )

    limit = request.query_params.get("limit")
    offset = request.query_params.get("offset")

    if limit is not None or offset is not None:
        paginator = CreatePagination()
        objects = paginator.paginate_queryset(admissions, request)
    else:
        objects = admissions

    serializer = AdmissionSerializer(objects, many=True)
    data = serializer.data

    for item, admission in zip(data, objects):
        current_level = admission.student.current_student_year_level

        item["year_level"] = (
            str(current_level[0].level)
            if current_level
            else None
        )

    if limit is not None or offset is not None:
        response = paginator.get_paginated_response(data)
        response.data["school_year"] = current_school_year.year_name
        return response

    return Response({
        "school_year": current_school_year.year_name,
        "count": admissions.count(),
        "results": data
    })

# --------------------------------------------- Guardian income distribution view  ----------------------------------------------------------

@api_view(["GET"])
def guardian_income_distribution(request):
    bucket_size = int(request.GET.get("bucket_size", 10000)) 
    max_income = int(request.GET.get("max_income", 200000))   

    income_bucket_expr = ExpressionWrapper(
        Func(
            F('annual_income') / Value(bucket_size),
            function='FLOOR'
        ),
        output_field=IntegerField()
    )

    data = (
        Guardian.objects
        .filter(is_active=True, annual_income__lt=max_income)
        .annotate(income_bucket=income_bucket_expr)
        .values('income_bucket')
        .annotate(count=Count('id'))
        .order_by('income_bucket')
    )

    result = []
    for row in data:
        start = row['income_bucket'] * bucket_size
        end = start + bucket_size
        result.append({
            "range": f"₹{start} - ₹{end}",
            "count": row["count"]
        })

    return Response(result)


# ------------------------------------------------- livelihood  distribution view  ----------------------------------------------------------


@api_view(["GET"])
def livelihood_distribution(request):    
    govt_count = Guardian.objects.filter(is_active=True, means_of_livelihood='Govt').count()
    non_govt_count = Guardian.objects.filter(is_active=True, means_of_livelihood='Non-Govt').count()

    return Response([
        {"category": "Government", "count": govt_count},
        {"category": "Non-Government", "count": non_govt_count}
    ])



#-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

### ----------------------------- Category Count Dashboard API ----------------- ###
### ------------------- As of 25June25 at 12:35 --------------- ###

@api_view(["GET"])
def student_category(request):
    category_counts = Student.objects.filter(is_active=True).values('category').annotate(total=Count('id'))
    total_students = Student.objects.filter(is_active=True).count()


    # Map category codes to their display names
    category_display_map = dict(Student._meta.get_field('category').choices)

    result = [
        {
            # "category_code": item["category"],  # Uncomment if needed
            "category_name": category_display_map.get(item["category"], "Unknown"),
            "count": item["total"],
            "percentage": round((item["total"] / total_students) * 100, 2) if total_students > 0 else 0.0
        }
        for item in category_counts
    ]

    return Response(result, status=status.HTTP_200_OK)

### -------------------------------------------------------------- ###

### ----------------------------- Income Distribution Dashboard API ----------------- ###
### ------------------- As of 25June25 at 12:35 --------------- ###

@api_view(["GET"])
def guardian_income_distribution(request):
    # Define updated income brackets
    brackets = {
        "Below 1 Lakh": (0, 100000),
        "1 – 3 Lakhs": (100001, 300000),
        "3 – 5 Lakhs": (300001, 500000),
        "5 – 8 Lakhs": (500001, 800000),
        "8 – 10 Lakhs": (800001, 1000000),
        "Above 10 Lakhs": (1000001, None),
    }

    total_guardians = Guardian.objects.filter(is_active=True).exclude(annual_income__isnull=True).count()

    results = []

    for label, (min_income, max_income) in brackets.items():
        if max_income is not None:
            count = Guardian.objects.filter(                
                is_active=True,
                annual_income__gte=min_income,
                annual_income__lte=max_income
            ).count()
        else:
            count = Guardian.objects.filter(
                is_active=True,
                annual_income__gte=min_income
            ).count()

        percentage = round((count / total_guardians) * 100, 2) if total_guardians > 0 else 0.0

        results.append({
            "income_range": label,
            "count": count,
            "percentage": percentage
        })

    return Response(results, status=status.HTTP_200_OK)
### -------------------------------------------------------------- ###



@api_view(["GET"])
def fee_dashboard(request):
    filter_month = request.query_params.get("month")  # month name like "June"

    qs = StudentFee.objects.all()

    # ================= OVERALL SUMMARY =================
    overall = qs.aggregate(
        total=Coalesce(
            Sum(F("original_amount"), output_field=FloatField()),
            Value(0.0)
        ),
        paid=Coalesce(Sum("paid_amount", output_field=FloatField()), Value(0.0)),
        # penalty=Coalesce(Sum("penalty_amount", output_field=FloatField()), Value(0.0)),
    )

    total = float(overall["total"])
    paid = float(overall["paid"])
    # penalty = float(overall["penalty"])
    due = max(total - paid, 0)

    overall_summary = {
        "total_amount": round(total, 2),
        "paid_amount": round(paid, 2),
        "due_amount": round(due, 2),
        # "penalty_amount": round(penalty, 2),
        "paid_percent": round((paid / total) * 100, 2) if total else 0.0,
        "due_percent": round((due / total) * 100, 2) if total else 0.0,
        "total_percent": 100.0 if total else 0.0,
    }

    # ================= MONTHLY SUMMARY =================
    if filter_month:
        try:
            month_number = list(calendar.month_name).index(filter_month)
            qs = qs.filter(month=month_number)
        except ValueError:
            pass

    monthly_qs = (
        qs.values("month")
        .annotate(
            base=Coalesce(Sum("original_amount", output_field=FloatField()), Value(0.0)),
            # penalty=Coalesce(Sum("penalty_amount", output_field=FloatField()), Value(0.0)),
            paid=Coalesce(Sum("paid_amount", output_field=FloatField()), Value(0.0)),
        )
        .order_by("month")
    )

    monthly_summary = []
    for row in monthly_qs:
        total = row["base"]
        due = max(total - row["paid"], 0)

        monthly_summary.append({
            "month": calendar.month_name[row["month"]] if row["month"] else "Unknown",
            "total_amount": round(total, 2),
            "paid_amount": round(row["paid"], 2),
            "due_amount": round(due, 2),
            # "penalty_amount": round(row["penalty"], 2),
            "paid_percent": round((row["paid"] / total) * 100, 2) if total else 0.0,
            "due_percent": round((due / total) * 100, 2) if total else 0.0,
            # "penalty_percent": round((row["penalty"] / total) * 100, 2) if total else 0.0,
            "total_percent": 100.0 if total else 0.0,
        })

    # ================= PAYMENT MODE DISTRIBUTION =================
    payment_qs = FeePayment.objects.filter(status="success").values(
        "payment_method"
    ).annotate(count=Count("id"))

    total_payments = sum(p["count"] for p in payment_qs)

    payment_mode_distribution = [
        {
            "payment_mode": p["payment_method"],
            "count": p["count"],
            "percentage": round((p["count"] / total_payments) * 100, 2) if total_payments else 0.0
        }
        for p in payment_qs
    ]

    # ================= DEFAULTER SUMMARY =================
    three_months_ago = now().date() - timedelta(days=90)

    defaulter_students = (
        StudentFee.objects.filter(
            due_amount__gt=0,
            due_date__lt=three_months_ago,
            student_year__student__is_active=True
        )
        .values("student_year__student")
        .distinct()
        .count()
    )

    total_students = Student.objects.filter(is_active=True).count()

    defaulter_summary = {
        "count": defaulter_students,
        "percent": round((defaulter_students / total_students) * 100, 2) if total_students else 0.0
    }

    # ================= RESPONSE =================
    return Response({
        "overall_summary": overall_summary,
        "monthly_summary": monthly_summary,
        "payment_mode_distribution": payment_mode_distribution,
        "defaulter_summary": defaulter_summary
    })



@api_view(["GET", "POST", "PUT", "DELETE"])
def YearLevelView(request, id=None):
    if request.method == "GET":
        if id is not None:
            try:
                YearLevels = YearLevel.objects.get(pk=id)
                serialize = YearLevelSerializer(YearLevels, many=False)
                return Response(serialize.data, status=status.HTTP_200_OK)
            except YearLevel.DoesNotExist:
                return Response(
                    data={"message": "Data Not Found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            except Exception as e:
                return Response(
                    data={"message": f"something went wrong {e}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        else:
            YearLevels = YearLevel.objects.all()
            serialized = YearLevelSerializer(YearLevels, many=True)
            return Response(serialized.data, status=status.HTTP_200_OK)

    elif request.method == "POST":
        data = request.data
        serialize = YearLevelSerializer(data=data)
        if serialize.is_valid():
            serialize.save()
            return Response(
                {"message": "Data Saved Successfully"}, status=status.HTTP_201_CREATED
            )
        return Response(
            {"message": "Insert Valid Data"}, status=status.HTTP_400_BAD_REQUEST
        )

    elif request.method == "PUT":
        if id is None:
            return Response(
                {"message": "Id is Required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            data = YearLevel.objects.get(pk=id)
            serialize = YearLevelSerializer(
                instance=data, data=request.data, partial=True
            )
            if serialize.is_valid():
                serialize.save()
                return Response(
                    {"message": "Data Updated Successfully"},
                    status=status.HTTP_202_ACCEPTED,
                )
            return Response(
                {"message": "Insert Valid Data"}, status=status.HTTP_400_BAD_REQUEST
            )
        except YearLevel.DoesNotExist:
            return Response(
                {"message": "Data Not Found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"message": "something went wrong"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    elif request.method == "DELETE":
        if id is None:
            return Response(
                {"message": "Id is Required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            data = YearLevel.objects.get(pk=id)
            data.delete()
            return Response(
                {"message": "Data Deleted Successfully"},
                status=status.HTTP_204_NO_CONTENT,
            )
        except YearLevel.DoesNotExist:
            return Response(
                {"message": "Data Not Found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"message": "something went wrong"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@api_view(["GET", "POST", "PUT", "DELETE"])
def SchoolYearView(request, pk=None):

    if request.method == "GET":
        if pk is not None:
            try:
                store = SchoolYear.objects.get(id=pk)
                serialize_rData = SchoolYearSerializer(store, many=False)
                return Response(serialize_rData.data, status=status.HTTP_200_OK)

            except SchoolYear.DoesNotExist:
                return Response(
                    {"Message": "Data Not Found"}, status=status.HTTP_404_NOT_FOUND
                )

        else:
            store = SchoolYear.objects.all()
            print("\n\n", store, "\n\n")
            serializerData = SchoolYearSerializer(store, many=True)
            return Response(serializerData.data, status=status.HTTP_200_OK)

    elif request.method == "POST":
        json_data = request.data
        serializerData = SchoolYearSerializer(data=json_data)

        if serializerData.is_valid():
            serializerData.save()
            return Response(
                {"Message": "School Year Added Successfully"},
                status=status.HTTP_201_CREATED,
            )

        return Response({"Message": "Invalid Data"}, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "PUT":
        try:
            Store = SchoolYear.objects.get(id=pk)
            Updated_SchoolYear = SchoolYearSerializer(instance=Store, data=request.data)

            if Updated_SchoolYear.is_valid():
                Updated_SchoolYear.save()
                return Response(
                    {"message": "Update School Year Successfully"},
                    status=status.HTTP_201_CREATED,
                )

            return Response(
                {"message": "Invalid Data"}, status=status.HTTP_400_BAD_REQUEST
            )

        except SchoolYear.DoesNotExist:
            return Response(
                {"Message": "Data Not Found"}, status=status.HTTP_404_NOT_FOUND
            )

    elif request.method == "DELETE":
        try:
            store = SchoolYear.objects.get(id=pk)
            store.delete()
            return Response(
                {"Message": "School year Delete Successfuly"},
                status=status.HTTP_204_NO_CONTENT,
            )

        except SchoolYear.DoesNotExist:
            return Response(
                {"Message": "Data Not Found"}, status=status.HTTP_404_NOT_FOUND
            )


@api_view(["GET", "POST", "PUT", "DELETE"])
def DepartmentView(request, pk=None):
    if request.method == "GET":
        if pk is not None:
            try:
                department = Department.objects.get(id=pk)
                serializer = DepartmentSerializer(department, many=False)
                return Response(serializer.data, status=status.HTTP_200_OK)

            except Department.DoesNotExist:
                return Response(
                    {"Message": "Data Not Found"}, status=status.HTTP_404_NOT_FOUND
                )

            except Exception as e:
                return Response(
                    {"Message": "Something went wrong"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        else:
            departments = Department.objects.all()
            serializer = DepartmentSerializer(departments, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == "POST":
        json_data = request.data

        if json_data.get("department_name", None) is None:
            return Response(
                {"Message": "Invalid Data"}, status=status.HTTP_400_BAD_REQUEST
            )

        json_data["department_name"] = json_data["department_name"].lower()

        serializer = DepartmentSerializer(data=json_data)

        if serializer.is_valid():

            if Department.objects.filter(
                department_name=json_data["department_name"]
            ).exists():
                return Response(
                    {"Message": "Department Already Exist"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serializer.save()
            return Response(
                {"Message": "Department Added Successfully"},
                status=status.HTTP_201_CREATED,
            )

        return Response({"Message": "Invalid Data"}, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "PUT":

        if request.data.get("department_name", None) is None:
            return Response(
                {"Message": "Invalid Data"}, status=status.HTTP_400_BAD_REQUEST
            )

        request.data["department_name"] = request.data["department_name"].lower()

        try:
            department = Department.objects.get(id=pk)
            serializer = DepartmentSerializer(instance=department, data=request.data)

            if serializer.is_valid():
                if Department.objects.filter(
                    department_name=request.data["department_name"].lower()
                ).exists():
                    return Response(
                        {"Message": "Department Already Exist"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                serializer.save()

                return Response(
                    {"Message": "Department updated Successfully"},
                    status=status.HTTP_201_CREATED,
                )

        except Department.DoesNotExist:
            return Response(
                {"Message": "Data Not Found"}, status=status.HTTP_404_NOT_FOUND
            )

        except Exception as e:
            return Response(
                {"Message": "Something went wrong"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    elif request.method == "DELETE":

        try:
            store = Department.objects.get(id=pk)
            store.delete()
            return Response(
                {"Message": "Department Delete Successfuly"},
                status=status.HTTP_204_NO_CONTENT,
            )

        except Department.DoesNotExist:
            return Response(
                {"Message": "Data Not Found"}, status=status.HTTP_404_NOT_FOUND
            )

        except Exception as e:
            return Response(
                {"Message": "Something went wrong"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@api_view(["GET", "POST", "PUT", "DELETE"])
def ClassRoomView(request, pk=None):

    def is_room_exists(room_type_id, room_name, exclude_id=None):
      
        queryset = ClassRoom.objects.filter(
            room_type_id=room_type_id,
            room_name__iexact=room_name.strip()
        )
        if exclude_id:
            queryset = queryset.exclude(id=exclude_id)
        return queryset.exists()

  
    if request.method == "GET":
        if pk:
            try:
                classroom = ClassRoom.objects.get(id=pk)
                serialize = ClassRoomSerializer(classroom)
                return Response(serialize.data, status=status.HTTP_200_OK)
            except ClassRoom.DoesNotExist:
                return Response({"Message": "Data not found"}, status=status.HTTP_404_NOT_FOUND)
        classrooms = ClassRoom.objects.all()
        serialize = ClassRoomSerializer(classrooms, many=True)
        return Response(serialize.data, status=status.HTTP_200_OK)


    elif request.method == "POST":
        room_type_id = request.data.get("room_type")
        room_name = request.data.get("room_name", "").strip()

        if not room_type_id or not room_name:
            return Response({"Message": "Invalid Data"}, status=status.HTTP_400_BAD_REQUEST)

        if is_room_exists(room_type_id, room_name):
            return Response(
                {"Message": "This room already exists for this type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serialize = ClassRoomSerializer(data=request.data)
        if serialize.is_valid():
            serialize.save()
            return Response({"Message": "Data Saved Successfully"}, status=status.HTTP_200_OK)
        return Response({"Message": "Insert Valid Data", "Errors": serialize.errors},
                        status=status.HTTP_400_BAD_REQUEST)


    elif request.method == "PUT":
        try:
            classroom = ClassRoom.objects.get(id=pk)
        except ClassRoom.DoesNotExist:
            return Response({"Message": "Data not found"}, status=status.HTTP_404_NOT_FOUND)

        room_type_id = request.data.get("room_type")
        room_name = request.data.get("room_name", "").strip()

        if not room_type_id or not room_name:
            return Response({"Message": "Invalid Data"}, status=status.HTTP_400_BAD_REQUEST)

        if is_room_exists(room_type_id, room_name, exclude_id=pk):
            return Response(
                {"Message": "This room already exists for this type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serialize = ClassRoomSerializer(instance=classroom, data=request.data)
        if serialize.is_valid():
            serialize.save()
            return Response({"Message": "Data Updated Successfully"}, status=status.HTTP_200_OK)
        return Response({"Message": "Insert Valid Data", "Errors": serialize.errors},
                        status=status.HTTP_400_BAD_REQUEST)

 
    elif request.method == "DELETE":
        try:
            classroom = ClassRoom.objects.get(id=pk)
            classroom.delete()
            return Response({"Message": "Data Deleted"}, status=status.HTTP_204_NO_CONTENT)
        except ClassRoom.DoesNotExist:
            return Response({"Message": "Data not found"}, status=status.HTTP_404_NOT_FOUND)




@api_view(["GET", "POST", "PUT", "DELETE"])
def ClassRoomTypeView(request, pk=None):

    if request.method == "GET":
        if pk is not None:
            try:
                classroom_type = ClassRoomType.objects.get(id=pk)
                serialize = ClassRoomTypeSerializer(classroom_type, many=False)
                return Response(serialize.data, status.HTTP_200_OK)

            except ClassRoomType.DoesNotExist:
                return Response(
                    {"Message": "Data not found"}, status.HTTP_404_NOT_FOUND
                )
        else:
            classroom_types = ClassRoomType.objects.all()
            serialized = ClassRoomTypeSerializer(classroom_types, many=True)
            return Response(serialized.data, status.HTTP_200_OK)

    elif request.method == "POST":
        data = request.data
        data["name"] = data["name"].lower()
        serialize = ClassRoomTypeSerializer(data=data)
        if serialize.is_valid():

            if ClassRoomType.objects.filter(name=data["name"]).exists():

                return Response(
                    {"Message": "Classroom Type Already Exist"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serialize.save()
            return Response({"Message": "Data Saved Successfully"}, status.HTTP_200_OK)
        return Response({"Message": "Insert Valid Data"}, status.HTTP_201_CREATED)

    elif request.method == "PUT":
        try:
            data = ClassRoomType.objects.get(id=pk)

            if request.data.get("name", None) is None:
                return Response(
                    {"Message": "Invalid Data"}, status.HTTP_400_BAD_REQUEST
                )

            request.data["name"] = request.data["name"].lower()

            serialize = ClassRoomTypeSerializer(instance=data, data=request.data)
            if serialize.is_valid():

                if ClassRoomType.objects.filter(
                    name=request.data["name"].lower()
                ).exists():
                    return Response(
                        {"Message": "Classroom Type Already Exist"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                serialize.save()
                return Response(
                    {"Message": "Data Updated Successfully"}, status.HTTP_200_OK
                )
            return Response(
                {"Message": "Insert Valid Data"}, status.HTTP_400_BAD_REQUEST
            )

        except ClassRoomType.DoesNotExist:
            return Response({"Message": "Data not found"}, status.HTTP_404_NOT_FOUND)

 
    elif request.method == "DELETE":
        try:
            data = ClassRoomType.objects.get(id=pk)
            data.delete()
            return Response({"Message": "Data Deleted"}, status.HTTP_204_NO_CONTENT)

        except ClassRoomType.DoesNotExist:
            return Response({"Message": "Data not found"}, status.HTTP_404_NOT_FOUND)


#

### --- Added this as of 06June25 at 12:00 PM

def get_or_create_role(role_name: str):
    role_name = role_name.strip().lower()
    role, created = Role.objects.get_or_create(
        name__iexact=role_name,
        defaults={"name": role_name}
    )
    return role

@api_view(["GET", "POST", "PUT", "DELETE"])
def RoleView(request, pk=None):
    if request.method == "GET":
        if pk:
            try:
                role = Role.objects.get(pk=pk)
                serializer = RoleSerializer(role)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Role.DoesNotExist:
                return Response({"message": "Role not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            roles = Role.objects.all()
            serializer = RoleSerializer(roles, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == "POST":
        role_name = request.data.get("name", "").strip().lower()

        if not role_name:
            return Response({"message": "Role name is required"}, status=status.HTTP_400_BAD_REQUEST)

        existing_role = Role.objects.filter(name__iexact=role_name).first()
        if existing_role:
            return Response({"message": "Role already exists"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = RoleSerializer(data={"name": role_name})
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "New Role added Successfully"}, status=status.HTTP_201_CREATED)

        return Response({"message": "Invalid Data"}, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "PUT":
        if not pk:
            return Response({"message": "Role ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            role = Role.objects.get(pk=pk)
        except Role.DoesNotExist:
            return Response({"message": "Role ID not Found"}, status=status.HTTP_404_NOT_FOUND)

        new_name = request.data.get("name", "").strip().lower()

        if not new_name:
            return Response({"message": "Invalid Data"}, status=status.HTTP_400_BAD_REQUEST)

        if Role.objects.exclude(pk=pk).filter(name__iexact=new_name).exists():
            return Response({"message": "Role with this name already exists"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = RoleSerializer(instance=role, data={"name": new_name})
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Role updated Successfully"}, status=status.HTTP_200_OK)

        return Response({"message": "Invalid Data"}, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        if not pk:
            return Response({"message": "Role ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            role = Role.objects.get(pk=pk)
            role.delete()
            return Response({"message": "Role deleted Successfully"}, status=status.HTTP_204_NO_CONTENT)
        except Role.DoesNotExist:
            return Response({"message": "Role not Found"}, status=status.HTTP_404_NOT_FOUND)


# ==============Subject================
class subjectView(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = subjectSerializer

    def get_queryset(self):
        qs = super().get_queryset()

        year_id = self.request.query_params.get("year_level")
        if year_id:
            qs = qs.filter(year_levels__id=year_id)

        core_subject = self.request.query_params.get("core_subject")
        if core_subject is not None:
            qs = qs.exclude(department__department_name="Non-scholastic")

        department_name = self.request.query_params.get('department')
        if department_name:
            qs = qs.filter(department__department_name__iexact=department_name)

        return qs


# ==============Country================
class CountryView(viewsets.ModelViewSet):
    queryset = Country.objects.all()
    serializer_class = CountrySerializer


# ===============State===================
class StateView(viewsets.ModelViewSet):
    queryset = State.objects.all()
    serializer_class = StateSerializer


# ================City===============
class CityView(viewsets.ModelViewSet):
    queryset = City.objects.all()
    serializer_class = CitySerializer


# ===========Address==========

class AddressView(viewsets.ModelViewSet):
    queryset = Address.objects.filter(is_active=True)
    serializer_class = AddressSerializer
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ===========Period============


class PeriodView(viewsets.ModelViewSet):
    queryset = Period.objects.all()
    serializer_class = PeriodSerializer


class DirectorView(viewsets.ModelViewSet):
    queryset = Director.objects.all()
    serializer_class = DirectorProfileSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve','update', 'partial_update']:
            return [AllowAny()]  # Public access
        return [IsAuthenticated()]  # JWT required for others


    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user_instance = instance.user
        if user_instance.role.exclude(name="director").exists():
            try:
                role = Role.objects.get(name="director")
                user_instance.role.remove(role)
            except Role.DoesNotExist:
                pass
            self.perform_destroy(instance)
        else:
            instance.delete()
            user_instance.delete()
        return Response(
            {"success": "Successfully deleted"}, status=status.HTTP_204_NO_CONTENT
        )
        
        
    # ******************JWt********************
    @action(detail=False, methods=['get', 'put', 'patch'], url_path='director_my_profile', permission_classes=[IsAuthenticated])
    def director_my_profile(self, request):
        user = request.user

        try:
            director = Director.objects.get(user=user)
        except Director.DoesNotExist:
            return Response({"error": "No director profile found for this user."}, status=status.HTTP_404_NOT_FOUND)

        if request.method in ['PUT', 'PATCH']:
            partial = request.method == 'PATCH'
            serializer = self.get_serializer(director, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response({"success": "Director profile updated successfully", "data": serializer.data}, status=status.HTTP_200_OK)

        serializer = self.get_serializer(director)
        return Response(serializer.data, status=status.HTTP_200_OK)    


class BankNameView(viewsets.ModelViewSet):
    queryset = BankName.objects.all()
    serializer_class = BankNameSerializer

class BankingDetailView(viewsets.ModelViewSet):
    queryset = BankingDetail.objects.filter(is_active=True)
    serializer_class = BankingDetailsSerializer

class TermView(viewsets.ModelViewSet):
    queryset =Term.objects.all()
    serializer_class = TermSerializer


import pandas as pd
from django.db import transaction
    
class AdmissionView(viewsets.ModelViewSet):
    queryset = Admission.objects.all()
    serializer_class = AdmissionSerializer

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # filterset_class = AdmissionFilter

    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "student__user__email",
        "guardian__user__first_name",
        "guardian__user__last_name",
        "tc_letter",
        "enrollment_no",
        "previous_school_name",
    ]

    ordering_fields = [
        "admission_date",
        "year_level__level_name",
        "student__user__first_name",
        "previous_percentage",
    ]
    # parser_classes=[MultiPartParser,FormParser]
    # pagination_class = CreatePagination
    

    # rte
    @action(detail=False, methods=["get"], url_path="rte-students")
    def rte_students(self, request):
        queryset = self.queryset.filter(is_rte=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


    # bulk admission
    @action(detail=False, methods=["post"], url_path="bulk-admission")
    def bulk_admission(self, request):

        school_year = request.query_params.get("school_year")

        if not school_year:
            return Response({"error": "school_year is required"}, status=400)

        try:
            DEFAULT_SCHOOL_YEAR = SchoolYear.objects.get(year_name=school_year)
        except SchoolYear.DoesNotExist:
            return Response({"error": "Invalid school year"}, status=400)


        # ---------- DEFAULTS ----------
        DEFAULT_COUNTRY = Country.objects.get(name="India")
        DEFAULT_STATE = State.objects.first()
        DEFAULT_CITY = City.objects.first()
        # DEFAULT_SCHOOL_YEAR = SchoolYear.objects.get(year_name="2026-2027")

        CATEGORY_MAP = {
            "SC": "SC",        # SC/ST combined
            "ST": "ST",
            "OBC": "OBC",
            "UR": "GEN",
            "GENERAL": "GEN",
            "General": "GEN",
            "GEN": "GEN",
        }

        # ---------- FILE CHECK ----------
        file = request.FILES.get("file")
        if not file:
            return Response(
                {"error": "Excel file is required"},
                status=400
            )

        sheets = pd.read_excel(file, sheet_name=None)

        errors = []
        created = 0

        for sheet_name, df in sheets.items():
            for index, row in df.iterrows():
                try:
                    with transaction.atomic():

                        # ---------- NAME ----------
                        full_name = str(row.get("STUDENT NAME", "")).strip()
                        if not full_name:
                            raise ValueError("Student name missing")

                        first, last = (full_name.split(" ", 1) + [""])[:2]

                        # ---------- EMAIL ----------
                        raw_email = row.get("e_mail ID")
                        if not raw_email or pd.isna(raw_email) or str(raw_email).strip() == "-":
                            email = f"{first.lower()}.{uuid.uuid4().hex[:6]}@school.local"
                        else:
                            email = str(raw_email).strip().lower()

                        if User.objects.filter(email__iexact=email).exists():
                            raise ValueError(f"Email: {email} already exists for {full_name}")

                        # ---------- CATEGORY ----------
                        raw_category = str(row.get("cast", "")).strip().upper()
                        category = CATEGORY_MAP.get(raw_category, "GEN")

                        # ---------- SCHOLAR CHECK ----------
                        scholar_no = row.get("scholar")

                        if scholar_no and not pd.isna(scholar_no):
                            # fixes Excel values like 123.0
                            if isinstance(scholar_no, float) and scholar_no.is_integer():
                                scholar_no = str(int(scholar_no))
                            else:
                                scholar_no = str(scholar_no).strip()
                        else:
                            scholar_no = None


                        if scholar_no and Student.objects.filter(scholar_number=scholar_no).exists():
                            raise ValueError(f"Scholar number: {scholar_no} already exists for {full_name}")

                        # ---------- YEAR LEVEL ----------
                        try:
                            year_level = YearLevel.objects.get(level_order=row.get("CLASS"))
                        except YearLevel.DoesNotExist:
                            raise ValueError(f"Invalid CLASS: {row.get('CLASS')}")

                        # ---------- ADMISSION DUPLICATE ----------
                        if scholar_no and Admission.objects.filter(
                            student__scholar_number=scholar_no,
                            school_year=DEFAULT_SCHOOL_YEAR
                        ).exists():
                            raise ValueError("Admission already exists for this academic year")

                        # ---------- USER ----------
                        user = User.objects.create(
                            first_name=first,
                            last_name=last,
                            email=email
                        )
                        user.set_password("Student@123")
                        user.save()

                        student_role, _ = Role.objects.get_or_create(name="student")
                        user.role.add(student_role)

                        # ---------- CONTACT ----------
                        father_mobile = row.get("Father's Mobile No")
                        mother_mobile = row.get("Mother's Mobile No")

                        if not father_mobile or pd.isna(father_mobile) or str(father_mobile).strip() == "-":
                            contact_number = (
                                str(mother_mobile).strip()
                                if mother_mobile and not pd.isna(mother_mobile) and str(mother_mobile).strip() != "-"
                                else None
                            )
                        else:
                            contact_number = str(father_mobile).strip()

                        # ---------- STUDENT ----------
                        student = Student.objects.create(
                            user=user,
                            father_name=row.get("father_name"),
                            mother_name=row.get("mother_name"),
                            date_of_birth = row.get("date_of_birth") if isinstance(row.get("date_of_birth"), (date, datetime)) else None,
                            gender=row.get("gender"),
                            blood_group=row.get("blood_group"),
                            category=category,
                            roll_number=row.get("roll_number"),
                            contact_number=contact_number,
                            scholar_number=scholar_no,
                            aadhaar_number=row.get("aadhar"),
                            FMID_number=row.get("family_id"),
                            apaar_number=row.get("APPAR ID"),
                            PEN_number=row.get("PEN"),
                        )

                        # ---------- ADDRESS ----------
                        Address.objects.create(
                            user=user,
                            address_line=row.get("address"),
                            country=DEFAULT_COUNTRY,
                            state=DEFAULT_STATE,
                            city=DEFAULT_CITY
                        )

                        # ---------- BANK ----------
                        bank_account = row.get("bank_account")
                        if bank_account and str(bank_account).isdigit():
                            bank_name_obj = None
                            if row.get("bank_name"):
                                bank_name_obj, _ = BankName.objects.get_or_create(
                                    name=str(row.get("bank_name")).strip()
                                )

                            BankingDetail.objects.create(
                                user=user,
                                account_no=int(bank_account),
                                ifsc_code=row.get("bank_ifsc") or "",
                                holder_name=user.get_full_name(),
                                bank_name=bank_name_obj
                            )

                        # ---------- ADMISSION ----------
                        Admission.objects.create(
                            student=student,
                            year_level=year_level,
                            school_year=DEFAULT_SCHOOL_YEAR,
                            enrollment_no=row.get("enrollment no") or "",
                            admission_date = row.get("date_of_join") if isinstance(row.get("date_of_join"), (date, datetime)) else None,
                            rte_number=row.get("rte_number") or "",
                            emergency_contact_no=row.get("Emergency Contact No"),
                            class_section=row.get("SECTION"),
                            obtain_marks=0,
                            total_marks=0,
                        )

                        # ---------- STUDENT YEAR ----------

                        HOUSE_MAP = {
                            "RED": "RED",
                            "GREEN": "GREEN",
                            "YELLOW": "YELLOW",
                            # "BLUE": "BLUE",
                        }

                        raw_house = row.get("House")

                        house = None
                        if raw_house and not pd.isna(raw_house):
                            raw_house = str(raw_house).strip().upper()
                            if raw_house != "-":
                                house = HOUSE_MAP.get(raw_house)

                        StudentYearLevel.objects.create(
                            student=student,
                            level=year_level,
                            year=DEFAULT_SCHOOL_YEAR,
                            house=house,
                        )

                        # ---------- GUARDIAN ----------
                        annual_income = row.get("annual_income")
                        if annual_income and not pd.isna(annual_income) and str(annual_income).strip() != "-":
                            guardian = Guardian.objects.create(annual_income=annual_income)
                            guardian_type_obj, _ = GuardianType.objects.get_or_create(name="Parent")

                            StudentGuardian.objects.create(
                                student=student,
                                guardian=guardian,
                                guardian_type=guardian_type_obj
                            )

                        # ---------- DOCUMENTS ----------
                        DOCUMENT_FIELD_MAP = {
                            "Apaar ID": row.get("APPAR ID"),
                            "Cast Certificate": row.get("cast_certificate"),
                            "Aadhaar Number": row.get("aadhar"),
                            "SSSM ID": row.get("sssm_id"),
                            "Family ID": row.get("family_id"),
                            "PEN Number": row.get("PEN"),
                        }

                        for doc_name, identity_value in DOCUMENT_FIELD_MAP.items():
                            if not identity_value or pd.isna(identity_value) or str(identity_value).strip() == "-":
                                continue

                            doc_type, _ = DocumentType.objects.get_or_create(name=doc_name)
                            document = Document.objects.create(
                                student=student,
                                identities=str(identity_value).strip()
                            )
                            document.document_types.add(doc_type)

                        created += 1

                except Exception as e:
                    errors.append({
                        "sheet": sheet_name,
                        "row": index + 2,
                        "reason": str(e)
                    })

        status_code = 207 if errors else 201
        return Response({
            "status": "Bulk admission completed",
            "created": created,
            "errors": errors
        }, status=status_code)

    
    
    
# ***************OfficeStaffView**************

 
class OfficeStaffView(viewsets.ModelViewSet):
    queryset=OfficeStaff.objects.all()
    serializer_class = OfficeStaffSerializer  
    
    
    def get_permissions(self):
        # Public access to list and retrieve
        if self.action in ['list', 'retrieve', 'update', 'partial_update']:
            return [AllowAny()]
        return [
            # IsAuthenticated()
                ]


    @action(detail=False, methods=['get','put', 'patch'], url_path='OfficeStaff_my_profile', permission_classes=[IsAuthenticated])
    def OfficeStaff_my_profile(self, request):
        user = request.user

        try:
            staff = OfficeStaff.objects.get(user=user)
        except OfficeStaff.DoesNotExist:
            return Response({"error": "No office staff profile found for this user."}, status=status.HTTP_404_NOT_FOUND)

        if request.method in ['PUT', 'PATCH']:
            partial = request.method == 'PATCH'
            serializer = self.get_serializer(staff, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response({"success": "Office staff profile updated successfully", "data": serializer.data}, status=status.HTTP_200_OK)

        serializer = self.get_serializer(staff)
        return Response(serializer.data, status=status.HTTP_200_OK)  


    
#  *************************** DOCUMENT************************************

class DocumentTypeView(viewsets.ModelViewSet):
    queryset = DocumentType.objects.all()
    serializer_class = DocumentTypeSerializer 
    
class FileView(viewsets.ModelViewSet):
    queryset = File.objects.all()
    serializer_class = FileSerializer 


class DocumentView(viewsets.ModelViewSet):
    queryset = Document.objects.prefetch_related('files', 'document_types')
    serializer_class = DocumentSerializer
    pagination_class = CreatePagination

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        # Validate files
        files = request.FILES.getlist('files')
        has_files = bool(files)

        # Get and validate document types
        doc_types = request.data.getlist('document_types', []) or [request.data.get('document_types')]
        doc_types = [dt for dt in doc_types if dt and str(dt).isdigit()]
        if not doc_types:
            return Response({"error": "Valid document types required"}, status=status.HTTP_400_BAD_REQUEST)

        # Handle identities - accept both single value and array
        identities = request.data.getlist('identities', []) or [request.data.get('identities')]
        identities = [i for i in identities if i]  # Remove empty values
        identities_str = ", ".join(identities) if identities else None

        # Prepare data with null handling
        data = {
            'document_types': doc_types,
            'identities': identities_str,  # Store all identities as comma-separated string
            **{f: int(request.data[f]) if request.data.get(f) and str(request.data[f]).isdigit() else None 
               for f in ['student', 'teacher', 'guardian', 'office_staff']}
        }

        # Find existing document
        existing = self._find_existing_document(data)

        # Create or update document
         # --- CASE 1: Update existing document ---
        if existing:
            msg_parts = []

            # Update identity if changed
            if identities_str and identities_str != existing.identities:
                existing.identities = identities_str
                existing.save(update_fields=['identities'])
                msg_parts.append("Identity updated")

            # Replace files if provided
            if has_files:
                existing.files.all().delete()
                for file in files:
                    File.objects.create(document=existing, file=file)
                msg_parts.append("Files replaced")

            # If no files or identity changes → show message
            if not msg_parts:
                return Response({
                    "status": "no_change",
                    "message": "No updates were made — identity and files are same as before.",
                    "document": self.get_serializer(existing, context={'request': request}).data
                }, status=status.HTTP_200_OK)

            return Response({
                "status": "updated",
                "message": " and ".join(msg_parts) + " successfully.",
                "document": self.get_serializer(existing, context={'request': request}).data
            }, status=status.HTTP_200_OK)

        # --- CASE 2: No existing doc → create new one ---
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        doc = serializer.save()

        for file in files:
            File.objects.create(document=doc, file=file)

        return Response({
            "status": "created",
            "document": self.get_serializer(doc, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)

    def _find_existing_document(self, data):
        """Find existing document for same user + document type"""
        filter_params = {
            f: data.get(f)
            for f in ['student', 'teacher', 'guardian', 'office_staff']
            if data.get(f) is not None
        }

        existing_docs = Document.objects.filter(**filter_params).prefetch_related('document_types')

        for doc in existing_docs:
            existing_types = set(doc.document_types.values_list('id', flat=True))
            incoming_types = set(map(int, data['document_types']))
            if existing_types & incoming_types:  # intersection found
                return doc

        return None


class TransferCertificateDocumentView(viewsets.ModelViewSet):
    """
    API specifically for Transfer Certificates, including those for deactivated students.
    """
    # Fetch all documents (including deactivated) where the document type contains "transfer" or "tc"
    queryset = Document.objects.all_including_inactive().filter(
        models.Q(document_types__name__icontains='transfer') |
        models.Q(document_types__name__iexact='tc')
    ).prefetch_related('files', 'document_types').distinct()
    serializer_class = DocumentSerializer
    pagination_class = CreatePagination
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['student__id', 'is_active']
    search_fields = ['student__user__first_name', 'student__user__last_name', 'student__scholar_number', 'identities']


class InactiveDocumentView(viewsets.ReadOnlyModelViewSet):
    """
    API specifically for all OTHER documents belonging to deactivated students/staff.
    This excludes Transfer Certificates, which have their own view.
    """
    queryset = Document.objects.all_including_inactive().filter(is_active=False).exclude(
        models.Q(document_types__name__icontains='transfer') |
        models.Q(document_types__name__iexact='tc')
    ).prefetch_related('files', 'document_types').distinct()
    
    serializer_class = DocumentSerializer
    pagination_class = CreatePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['student__id']
    search_fields = ['student__user__first_name', 'student__user__last_name', 'student__scholar_number', 'identities']


# **************Assignment ClassPeriod for Student behalf of YearLevel(standard)****************   
    
# As of 05May25 at 01:00 PM

class ClassPeriodView(viewsets.ModelViewSet):
    queryset = ClassPeriod.objects.all()
    serializer_class = ClassPeriodSerializer
    
    @action(detail=False, methods=["post"], url_path="assign-to-yearlevel")
    def assign_to_yearlevel(self, request):
        serializer = ClassPeriodSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            return Response({
                "message": "ClassPeriods assigned successfully.",
                "details": result
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)    


from twilio.rest import Client 

def send_whatsapp_message(message_text):
    account_sid = 'AC75f0880296f2c1377b2ca30442bbd3e1'
    auth_token = '01dfff8731923c8e91e47b469f533fd5'
    twilio_whatsapp_number = 'whatsapp:+14155238886'
    
    phone_numbers = [
       '+918109145639',
        # '+918847418400',
        '+918102637122',
        '+919981993064'
    ]

    client = Client(account_sid, auth_token)

    sent_messages = []
    print('\n\n\n',sent_messages)
    for number in phone_numbers:
        try:
            message = client.messages.create(
                from_=twilio_whatsapp_number,
                body=message_text,
                to=f'whatsapp:{number}'
            )
            sent_messages.append({
                "to": number,
                "sid": message.sid,
                "status": "sent"
            })
        except Exception as e:
            sent_messages.append({
                "to": number,
                "error": str(e),
                "status": "failed"
            })

    return sent_messages

### --------------------- Income Distribution Dashboard API (Guardian name and student name and id added) --------------------------- ###
### ------------------- As of 03 JUly at 12:35 --------------- ###   By daniyal

@api_view(["GET"])
def guardian_income_distribution_with_student(request):
    # Define updated income brackets
    brackets = {
        "Below 1 Lakh": (0, 100000),
        "1 – 3 Lakhs": (100001, 300000),
        "3 – 5 Lakhs": (300001, 500000),
        "5 – 8 Lakhs": (500001, 800000),
        "8 – 10 Lakhs": (800001, 1000000),
        "Above 10 Lakhs": (1000001, None),
    }

    total_guardians = Guardian.objects.exclude(annual_income__isnull=True).count()
    results = []
    #---------- Count and guardian filter as it is
    for label, (min_income, max_income) in brackets.items():
        if max_income is not None:
            qs = Guardian.objects.filter(
                annual_income__gte=min_income,
                annual_income__lte=max_income
            )
        else:
            qs = Guardian.objects.filter(
                annual_income__gte=min_income,
            )  
        count = qs.count() 
        guardian_names = [f"{g.user.first_name} {g.user.last_name}" for g in qs]  

        student_data = [f" id:{s.studentguardian.get().student.id} {s.studentguardian.get().student.user.first_name} {s.studentguardian.get().student.user.last_name}" for s in qs]

        percentage = round((count / total_guardians) * 100, 2) if total_guardians > 0 else 0.0

        results.append({
            "income_range": label,
            "guardians":guardian_names,
            "count": count,
            "percentage": percentage,
            "student info": student_data
        })
        
    return Response(results, status=status.HTTP_200_OK)
### -------------------------------------------------------------- ###    


### --------------------- Deactivation of the users [NO access to them and data still stored] --------------------------- ###
### ------------------- As of 24 JUly at 12:00 --------------- ###   By daniyal
# from rest_framework.decorators import permission_classes
# from django.db import transaction
from authentication.models import UserStatusLog
from authentication.serializers import UserSerializer
from django.core.exceptions import ObjectDoesNotExist

@api_view(["POST"])
@permission_classes([RoleBasedUserManagementPermission])
def deactivate_user(request):
    deactivate_user.api_section = "deactivate_user"

    raw_user_id = request.data.get("user_id")
    user_ids = raw_user_id if isinstance(raw_user_id, list) else [raw_user_id]

    responses = []
    for user_id in user_ids:
        try:
            with transaction.atomic():
                user = User.objects.all_including_inactive().get(id=user_id)
                if not user.is_active:
                    responses.append({"error": "User already deactivated", "user_id": user_id})
                    continue

                user.is_active = False
                user.deactivation_reason = request.data.get('reason', '')
                user.deactivation_date = timezone.now()
                user.reactivation_date = None
                user.save()

                # Handle Teacher  (classPeriod [clear {M2M}], address, docs)
                teacher = getattr(user, 'teacher', None)
                if teacher is not None:
                    teacher = user.teacher
                    teacher.is_active = False
                    teacher.save()

                    # Clear TeacherYearLevel connections
                    teacher.year_levels.clear()
                    # Remove teacher from ClassPeriod assignments
                    class_periods = ClassPeriod.objects.filter(teacher=teacher)
                    for cp in class_periods:
                        cp.teacher = None  # Set to None to remove assignment
                        cp.save()
                    # Deactivate related Addresses
                    addresses = Address.objects.filter(user=user)
                    for address in addresses:
                        address.is_active = False
                        address.save()
                    # Clear related Documents
                    documents = Document.objects.filter(teacher=teacher)
                    for document in documents:
                        document.is_active = False
                        document.save()

                # Handle OfficeStaff  ([student,teacher,admission {clear M2M}, address, docs])
                office_staff = getattr(user, 'office_staff', None)
                if office_staff is None:
                    # Attempt to fetch OfficeStaff directly to confirm relation
                    try:
                        office_staff = OfficeStaff.objects.get(user=user)
                    except OfficeStaff.DoesNotExist:
                        office_staff = None

                if office_staff is not None:
                    try:
                        office_staff.is_active = False
                        office_staff.save()
                        # Clear ManyToMany relationships
                        office_staff.student.clear()
                        office_staff.teacher.clear()
                        office_staff.admissions.clear()
                        # Deactivate related Addresses
                        addresses = Address.objects.filter(user=user)
                        for address in addresses:
                            address.is_active = False
                            address.save()
                        # Clear related Documents
                        documents = Document.objects.filter(office_staff=office_staff)
                        for document in documents:
                            document.is_active = False
                            document.save()
                    except Exception as e:
                        responses.append({"error": f"Failed to deactivate OfficeStaff: {str(e)}", "user_id": user_id})
                        continue

                # Handle Director (if needed)
                director = getattr(user, 'director', None)
                if director is not None:
                    director = user.director
                    director.is_active = False
                    director.save()
                    addresses = Address.objects.filter(user=user)
                    for address in addresses:
                        address.is_active = False
                        address.save()

                # log termination
                UserStatusLog.objects.create(user=user, status='TERMINATED', reason=user.deactivation_reason)
                serializer = UserSerializer(user)
                responses.append({
                    "message": f"User {user.id} has been successfully terminated.",
                    "user_id": user.id,
                    "data": serializer.data})

        except User.DoesNotExist:
            responses.append({"error": "User not found", "user_id": user_id})

    if not isinstance(raw_user_id, list) and len(responses) == 1:
        return Response(responses[0])
    return Response(responses)


### -------------------------------------------------------------- ###

# *************** Reactivation of the User *******************************************************

@api_view(["POST"])
@permission_classes([RoleBasedUserManagementPermission])
def reactivate_user(request):
    reactivate_user.api_section = "reactivate_user"

    raw_user_id = request.data.get("user_id")
    user_ids = raw_user_id if isinstance(raw_user_id, list) else [raw_user_id]

    responses = []
    for user_id in user_ids:
        try:
            with transaction.atomic():
                user = User.objects.all_including_inactive().get(id=user_id)
                if user.is_active:
                    responses.append({"error": "User already active", "user_id": user_id})
                    continue

                user.is_active = True
                user.deactivation_reason = None
                user.reactivation_date = timezone.now()
                user.save()

                # Handle Teacher  (classPeriod [create {M2M}], teacheryearlevel, address, docs)
                try:
                    teacher = Teacher.objects.all_including_inactive().get(user=user)
                except Teacher.DoesNotExist:
                    teacher = None

                if teacher is not None:
                    teacher.is_active = True
                    teacher.save()

                    # Assign teacher from ClassPeriod assignments
                    class_period_ids = request.data.get("class_period_ids", [])
                    if class_period_ids:
                        valid_class_periods = ClassPeriod.objects.filter(id__in=class_period_ids)
                        if valid_class_periods.exists():
                            for class_period in valid_class_periods:
                                class_period.teacher = teacher
                                class_period.save()
                        else:
                            responses.append({"error": "No valid or active ClassPeriod IDs provided", "user_id": user_id})
                            continue

                    # Teacher year level reassigning
                    year_level_id = request.data.get("year_level_id", [])
                    if year_level_id:
                        valid_year_levels = YearLevel.objects.filter(id=year_level_id)
                        if valid_year_levels.exists():
                            teacher.year_levels.set(valid_year_levels)
                        else:
                            responses.append({"error": "No valid or active YearLevel IDs provided", "user_id": user_id})
                            continue

                    # retrieve related Addresses
                    addresses = Address.objects.all_including_inactive().filter(user=user)
                    for address in addresses:
                        address.is_active = True
                        address.save()
                    # retrieve related Documents
                    documents = Document.objects.all_including_inactive().filter(teacher=teacher)
                    for document in documents:
                        document.is_active = True
                        document.save()

                # Handle OfficeStaff  ([student,teacher,admission {clear M2M}, address, docs])
                try:
                    office_staff = OfficeStaff.objects.all_including_inactive().get(user=user)
                except OfficeStaff.DoesNotExist:
                    office_staff = None

                if office_staff is not None:
                    office_staff.is_active = True
                    office_staff.save()

                    # Student connection
                    student_ids = request.data.get("student_ids", [])
                    if student_ids:
                        valid_students = Student.objects.filter(id__in=student_ids, is_active=True)
                        if valid_students.exists():
                            office_staff.student.set(valid_students)
                        else:
                            responses.append({"error": "No valid or active Student IDs provided", "user_id": user_id})
                            continue

                    # Teacher connection
                    teacher_ids = request.data.get("teacher_ids", [])
                    if teacher_ids:
                        valid_teachers = Teacher.objects.filter(id__in=teacher_ids, is_active=True)
                        if valid_teachers.exists():
                            office_staff.teacher.set(valid_teachers)
                        else:
                            responses.append({"error": "No valid or active Teacher IDs provided", "user_id": user_id})
                            continue

                    # retrieve related Documents
                    documents = Document.objects.all_including_inactive().filter(office_staff=office_staff)
                    for document in documents:
                        document.is_active = True
                        document.save()

                # Handle Director (if needed)
                try:
                    director = Director.objects.all_including_inactive().get(user=user)
                except Director.DoesNotExist:
                    director = None

                if director is not None:
                    director.is_active = True
                    director.save()
                    addresses = Address.objects.all_including_inactive().filter(user=user)
                    for address in addresses:
                        address.is_active = True
                        address.save()

                # log activation
                UserStatusLog.objects.create(user=user, status='ACTIVATED', reason=user.deactivation_reason)
                serializer = UserSerializer(user)
                responses.append({
                    "message": f"User {user.id} has been successfully reactivated.",
                    "user_id": user.id,
                    "data": serializer.data})

        except User.DoesNotExist:
            responses.append({"error": "User not found", "user_id": user_id})

    if not isinstance(raw_user_id, list) and len(responses) == 1:
        return Response(responses[0])
    return Response(responses)
### -------------------------------------------------------------- ###
# *************** List of the Deactivated *******************************************************

@api_view(["GET"])
def list_inactive_users(request):
    users = User.objects.all_including_inactive().filter(is_active=False)
    serializer = UserSerializer(users, many=True)

    data = serializer.data

    for item, user in zip(data, users):
        role = user.role.first()
        item["role"] = {
            "id": role.id,
            "name": role.name
        } if role else None

    return Response(data)

#--------------------- Exam Module 

from django.apps import apps
from .utils import * 

class DownloadFileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        model_name = request.query_params.get("model")
        object_id = request.query_params.get("id")
        file_field_name = request.query_params.get("field", "uploaded_file")
        print(user,model_name,object_id,file_field_name)
        if not model_name or not object_id:
            return Response({"error": "model and id are required."}, status=400)

        try:
            model = apps.get_model(app_label="director", model_name=model_name)
        except LookupError:
            return Response({"error": f"Model '{model_name}' not found."}, status=404)

        instance = get_object_or_404(model, pk=object_id)

        user_roles = [role.name.lower() for role in user.role.all()]

        is_director = "director" in user_roles
        is_office = "office_staff" in user_roles
        is_teacher = "teacher" in user_roles
        is_student = "student" in user_roles
        is_guardian = "guardian" in user_roles

        student_related_id = getattr(instance, "student_id", None) or getattr(instance, "student", None)

        if is_student:
            if not StudentYearLevel.objects.filter(user=user, id=student_related_id).exists():
                return Response({"error": "Access denied: not your file."}, status=403)

        elif is_guardian:
            if not StudentGuardian.objects.filter(guardian=user, student_id=student_related_id).exists():
                return Response({"error": "Access denied: not your ward's file."}, status=403)

        elif is_teacher:
            assigned_classes = TeacherYearLevel.objects.filter(teacher=user).values_list("year_level_id", flat=True)
            student_obj = StudentYearLevel.objects.filter(id=student_related_id).first()
            if not student_obj or student_obj.year_level_id not in assigned_classes:
                return Response({"error": "Access denied: not your class student."}, status=403)

        elif not (is_director or is_office):
            return Response({"error": "Access denied: unauthorized role."}, status=403)

        file_field = getattr(instance, file_field_name, None)
        if not file_field:
            return Response({"error": f"Field '{file_field_name}' not found on model '{model_name}'."}, status=404)

        if not file_field.name:
            return Response({"error": f"{model_name} file not found."}, status=404)

        file_path = file_field.path
        print("File name:", file_field.name)
        print("File path:", file_field.path)
        print("File exists:", os.path.exists(file_field.path))


        if not os.path.exists(file_path):
            return Response({"error": f"{model_name} file not found."}, status=404)
        

        return get_file_response(file_field, file_label=f"{model_name} file")



class ExamTypeView(viewsets.ModelViewSet):
    queryset = ExamType.objects.all()
    serializer_class = ExamTypeSerializer
    permission_classes = [IsAuthenticated, RoleBasedExamPermission]
    api_section = 'exam_type'

    # @action(detail=False, methods=["get"], url_path="get_examtype")
    # def get_examtypes(self, request):
    #     exam_types = self.get_queryset()
    #     serializer = self.get_serializer(exam_types, many=True)
    #     return Response(serializer.data)

    # @action(detail=False, methods=["post"], url_path="create_examtype")
    # def create_examtype(self, request):
    #     name = request.data.get("name")
    #     if not name:
    #         return Response({"error": "Name is required."}, status=400)

    #     exam_type, created = ExamType.objects.get_or_create(name=name)
    #     serializer = self.get_serializer(exam_type)
    #     message = "Exam type created successfully." if created else "Exam type already exists."
    #     return Response({"message": message, "data": serializer.data}, status=201 if created else 200)

    # @action(detail=False, methods=["put"], url_path="update_examtype")
    # def update_examtype(self, request):
    #     try:
    #         exam_type = ExamType.objects.get(id=request.data.get("id"))
    #     except ExamType.DoesNotExist:
    #         return Response({"error": "ExamType not found"}, status=404)

    #     serializer = self.get_serializer(exam_type, data=request.data, partial=True)
    #     if serializer.is_valid():
    #         serializer.save()
    #         return Response({"message": "Exam type updated successfully", "data": serializer.data})
    #     return Response(serializer.errors, status=400)

    # @action(detail=False, methods=["delete"], url_path="delete_examtype")
    # def delete_examtype(self, request):
    #     try:
    #         exam_type = ExamType.objects.get(id=request.data.get("id"))
    #         exam_type.delete()
    #         return Response({"message": "ExamType deleted successfully."})
    #     except ExamType.DoesNotExist:
    #         return Response({"error": "ExamType not found"}, status=404)



class ExamPaperView(viewsets.ModelViewSet):
    queryset = ExamPaper.objects.all()
    serializer_class = ExamPaperSerializer
    permission_classes = [IsAuthenticated, RoleBasedExamPermission]
    api_section = 'exam_paper'

    @action(detail=False, methods=["get"], url_path="get_exampaper")
    def get_exampapers(self, request):
        user = request.user
        role_names = [role.name.lower() for role in user.role.all()]

        if "director" in role_names or "office staff" in role_names:
            queryset = ExamPaper.objects.select_related('exam_type', 'term', 'subject', 'year_level', 'teacher')
        
        elif "teacher" in role_names:
            teacher = Teacher.objects.filter(user=user).first()
            queryset = ExamPaper.objects.filter(teacher=teacher).select_related('exam_type', 'term', 'subject', 'year_level', 'teacher')
        
        else:
            return Response({"error": "You do not have permission to view exam papers."}, status=403)
        # Filters from query params
        subject_id = request.query_params.get("subject")
        teacher_id = request.query_params.get("teacher")
        school_year = request.query_params.get("school_year")
        paper_code = request.query_params.get("paper_code")
        exam_type_id = request.query_params.get("exam_type")
        class_id = request.query_params.get("class")

        if subject_id:
            queryset = queryset.filter(subject__subject_name=subject_id)
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)
        if school_year:
            queryset = queryset.filter(term__year__year_name=school_year)
        if paper_code:
            queryset = queryset.filter(paper_code__icontains=paper_code)
        if exam_type_id:
            queryset = queryset.filter(exam_type__name=exam_type_id)
        if class_id:
            queryset = queryset.filter(year_level__level_name=class_id)
        if not queryset.exists():
            return Response([])

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


    @action(detail=False, methods=["post"], url_path="create_exampaper")
    def create_paper(self, request):
        user = request.user
        role_names = [role.name.lower() for role in user.role.all()]

        if "director" in role_names:
            pass  
        
        elif "teacher" in role_names:
            teacher = Teacher.objects.filter(user=user).first()
            if not teacher:
                return Response({"error": "Teacher not found."}, status=400)

            assigned_class_ids = TeacherYearLevel.objects.filter(
                teacher=teacher
            ).values_list('year_level_id', flat=True)

            class_name = request.data.get("year_level")  

            if class_name is None:
                return Response({"error": "year_level is required."}, status=400)

            try:
                class_name = int(class_name)
            except ValueError:
                return Response({"error": "Invalid year_level value."}, status=400)

            if class_name not in assigned_class_ids:
                return Response("You can only create papers for your assigned classes.", status=403)
        
        else:
            return Response("You do not have permission to create exam papers.", status=403)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Exam paper created successfully",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["put"], url_path="update_exampaper")
    def update_paper(self, request):
        paper_code = request.data.get("paper_code")
        if not paper_code:
            return Response({"error": "paper_code is required for update."}, status=400)

        try:
            paper = ExamPaper.objects.get(paper_code=paper_code)
        except ExamPaper.DoesNotExist:
            return Response({"error": "ExamPaper not found"}, status=404)

        serializer = self.get_serializer(paper, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Exam paper updated successfully", 
                "data": serializer.data
            })
        return Response(serializer.errors, status=400)

    @action(detail=False, methods=["delete"], url_path="delete_exampaper")
    def delete_paper(self, request):
        paper_ids = request.data.get("paper_ids")
        if not paper_ids:
            return Response({"error": "paper_ids list is required."}, status=400)

        deleted = 0
        for pid in paper_ids:
            try:
                paper = ExamPaper.objects.get(id=pid)
                paper.delete()
            except ExamPaper.DoesNotExist:
                continue

        return Response({"message": "Successfully deleted paper(s)."})

from teacher.models import *
from django.db.models import Q
class ExamScheduleView(viewsets.ModelViewSet):
    queryset = ExamSchedule.objects.all()
    serializer_class = ExamScheduleSerializer
    permission_classes = [IsAuthenticated, RoleBasedExamPermission]
    api_section = 'exam_schedule'


    @staticmethod
    def format_exam_schedule(queryset):
        grouped_data = {}

        for obj in queryset:
            key = f"{obj.class_name.id}_{obj.term.id}_{obj.exam_type.id}"

            if key not in grouped_data:
                grouped_data[key] = {
                    "id": obj.id,
                    "class": obj.class_name.level_name,
                    "term": f"{obj.term.year.year_name} - Term {obj.term.term_number}",
                    "exam_type": obj.exam_type.name,
                    "papers": []
                }

            grouped_data[key]["papers"].append({
                "subject_name": obj.subject.subject_name.lower(),
                "exam_date": obj.exam_date,
                "start_time": obj.start_time,
                "end_time": obj.end_time,
                "day": obj.exam_date.strftime('%A')
            })

        return list(grouped_data.values())
    
    


    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated], url_path="get_timetable")
    def get_timetable(self, request):
        user = request.user
        role_names = [role.name.lower() for role in user.role.all()]

        if "director" in role_names or "office staff" in role_names:
            queryset = ExamSchedule.objects.select_related("class_name", "term", "term__year", "exam_type", "subject").all()

        elif "teacher" in role_names:
            teacher = Teacher.objects.filter(user=user).first()
            if not teacher:
                return Response({"error": "Teacher not found"}, status=400)
            assigned_class_ids = TeacherYearLevel.objects.filter(
                teacher=teacher
            ).values_list("year_level_id", flat=True)
            if not assigned_class_ids:
                return Response(
                    {"error": "No classes assigned to this teacher"},
                    status=400
                )

            queryset = ExamSchedule.objects.select_related(
                "class_name", "term", "term__year", "exam_type", "subject"
            ).filter(class_name_id__in=assigned_class_ids)


        elif "student" in role_names:
            student = Student.objects.filter(user=user, is_active=True).first()
            student_class = StudentYearLevel.objects.filter(student=student).last()
            if not student_class:
                return Response({"error": "Student class not found"}, status=400)
            queryset = ExamSchedule.objects.select_related("class_name", "term", "term__year", "exam_type", "subject").filter(class_name=student_class.level)

        else:
            return Response({"error": "Access Denied"}, status=403)

        # Apply filters from query params
        class_name = request.query_params.get("class_name")
        term = request.query_params.get("term")
        subject = request.query_params.get("subject")
        exam_type = request.query_params.get("exam_type")
        schedule_id = request.query_params.get("id")
        exam_date = request.query_params.get("exam_date")  

        if schedule_id:
            try:
                base = queryset.get(id=schedule_id)
            except ExamSchedule.DoesNotExist:
                return Response([])

            queryset = queryset.filter(
                class_name=base.class_name,
                term=base.term,
                exam_type=base.exam_type
            )

        if exam_date:
            queryset = queryset.filter(exam_date=exam_date)  


        if class_name:
            queryset = queryset.filter(class_name__level_name__iexact=class_name)
        if term:
            queryset = queryset.filter(term_id=term)
        # if subject:
        #     queryset = queryset.filter(subject__name__iexact=subject)
        if subject:
            queryset = queryset.filter(subject__subject_name__iexact=subject)

        if exam_type:
            queryset = queryset.filter(exam_type__name__iexact=exam_type)

        if not queryset.exists():
            return Response([])

        return Response(self.format_exam_schedule(queryset))



    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated], url_path="create_timetable")
    def create_timetable(self, request):
        user = request.user
        role_names = [role.name.lower() for role in user.role.all()]

        if any(role in role_names for role in ["director", "teacher", "office staff"]):
            serializer = ExamScheduleSerializer(data=request.data)
            if serializer.is_valid():
                schedules = serializer.save()
                return Response({"message": f"exam schedule created successfully."}, status=201)
            return Response(serializer.errors, status=400)

        return Response({"error": "You do not have permission to create timetable."}, status=403)


    @action(detail=False, methods=["patch"], permission_classes=[IsAuthenticated], url_path="update_timetable")
    def update_timetable(self, request):
        user = request.user
        roles = [r.name.lower() for r in user.role.all()]

        if not any(r in roles for r in ["director", "teacher"]):
            return Response({"error": "Permission denied"}, status=403)

        schedule_id = request.query_params.get("id")
        if not schedule_id:
            return Response({"error": "Schedule id is required"}, status=400)

        try:
            base_schedule = ExamSchedule.objects.get(id=schedule_id)
        except ExamSchedule.DoesNotExist:
            return Response({"error": "Schedule not found"}, status=404)

        papers = request.data.get("papers", [])
        if not papers:
            return Response({"error": "papers are required"}, status=400)

        # Check for duplicate subject names in request payload
        raw_names = [p.get("subject_name", "").strip() for p in papers if p.get("subject_name")]
        dup_names = [name for name, count in Counter(s.lower() for s in raw_names).items() if count > 1]
        if dup_names:
            return Response(
                {"error": f"Duplicate subject(s) in update request: {', '.join(dup_names)}. Each subject can only appear once in timetable update."},
                status=400
            )

        class_obj = base_schedule.class_name
        term = base_schedule.term
        exam_type = base_schedule.exam_type

        updated, errors = [], []

        for paper in papers:
            subject_name = paper.get("subject_name", "").strip()

            subject = Subject.objects.filter(
                subject_name__iexact=subject_name
            ).first()

            if not subject:
                errors.append({"subject_name": subject_name, "error": f"Subject '{subject_name}' not found"})
                continue

            try:
                schedule = ExamSchedule.objects.get(
                    class_name=class_obj,
                    term=term,
                    exam_type=exam_type,
                    subject=subject
                )
            except ExamSchedule.DoesNotExist:
                errors.append({"subject_name": subject_name, "error": f"Schedule not found for subject '{subject_name}'"})
                continue
            except ExamSchedule.MultipleObjectsReturned:
                errors.append({
                    "subject_name": subject_name,
                    "error": f"Multiple schedule records found for subject '{subject_name}' in class '{class_obj.level_name}', {term.year.year_name} - Term {term.term_number}, exam type '{exam_type.name}'. Please clean up duplicate database records."
                })
                continue

            payload = {}
            if paper.get("exam_date"):
                payload["exam_date"] = paper["exam_date"]
            if paper.get("start_time"):
                payload["start_time"] = paper["start_time"]
            if paper.get("end_time"):
                payload["end_time"] = paper["end_time"]

            serializer = ExamScheduleTimeUpdateSerializer(
                schedule,
                data=payload,
                partial=True
            )

            if serializer.is_valid():
                obj = serializer.save()
                updated.append({
                    "subject_name": subject.subject_name,
                    "exam_date": obj.exam_date,
                    "start_time": obj.start_time,
                    "end_time": obj.end_time,
                    "day": obj.exam_date.strftime("%A")
                })
            else:
                errors.append({
                    "subject_name": subject_name,
                    "error": serializer.errors
                })

        if errors and not updated:
            status_code = 400
        elif errors:
            status_code = 207
        else:
            status_code = 200

        return Response({"updated": updated, "errors": errors}, status=status_code)


class StudentMarksView(viewsets.ModelViewSet):
    queryset = StudentMarks.objects.all()
    serializer_class = StudentMarksSerializer
    permission_classes = [IsAuthenticated,RoleBasedExamPermission] 
    api_section = "student_marks"  

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated], url_path="get_marks")
    def get_marks(self, request):
        user = request.user
        role_names = [role.name.lower() for role in user.role.all()]

        if "director" in role_names:
            marks_qs = StudentMarks.objects.select_related(
                "student__student__user",
                "subject",
                "teacher__user",
                "exam_type",
                "term__year",
                "student__level"
            )
        elif "teacher" in role_names:
            try:
                teacher = Teacher.objects.get(user=user)
            except Teacher.DoesNotExist:
                return Response({"error": "Teacher not found."})

            assigned_class_ids = TeacherYearLevel.objects.filter(
                teacher=teacher
            ).values_list("year_level_id", flat=True)

            student_ids = StudentYearLevel.objects.filter(
                level_id__in=assigned_class_ids,
                student__is_active=True
            ).values_list("id", flat=True)

            marks_qs = StudentMarks.objects.select_related(
                "student__student__user",
                "subject",
                "teacher__user",
                "exam_type",
                "term__year",
                "student__level"
            ).filter(
                student_id__in=student_ids,
                teacher=teacher
            )
        else:
            return Response({"error": "You do not have permission to view marks."})

        # ----------- Filter
        school_year_filter = request.query_params.get("school_year")
        year_level_filter = request.query_params.get("year_level")
        exam_type_filter = request.query_params.get("exam_type")
        student_id = request.query_params.get("student_id")  
        teacher_id = request.query_params.get("teacher_id")

        if student_id:
            marks_qs = marks_qs.filter(student_id=student_id)

        if school_year_filter:
            marks_qs = marks_qs.filter(term__year__year_name=school_year_filter)
        if year_level_filter:
            marks_qs = marks_qs.filter(student__level__level_name=year_level_filter)
        if exam_type_filter:
            marks_qs = marks_qs.filter(exam_type__name=exam_type_filter)
        if teacher_id:
            try:
                teacher = Teacher.objects.get(id=teacher_id)
            except Teacher.DoesNotExist:
                return Response({"error": "Teacher not found."}, status=404)

            assigned_classes = TeacherYearLevel.objects.filter(
                teacher=teacher
            ).select_related("year_level")

            classes_list = [
                {"id": ac.year_level.id, "level_name": ac.year_level.level_name} for ac in assigned_classes
            ]

            return Response({"assigned_classes": classes_list})

        if not marks_qs.exists():
            return Response({"message": "No data found."})

        grouped_data = {}
        for mark in marks_qs:
            teacher_name = mark.teacher.user.get_full_name().lower()
            subject_name = mark.subject.subject_name.lower()
            exam_type = mark.exam_type.name
            school_year = mark.term.year.year_name
            year_level = mark.student.level.level_name
            key = (teacher_name, subject_name, exam_type, school_year, year_level)

            grouped_data.setdefault(key, []).append({
                "name": mark.student.student.user.get_full_name().lower(),
                "marks": mark.marks_obtained
            })

        final_response = {}
        for (teacher_name, subject_name, exam_type, school_year, year_level), student_marks in grouped_data.items():
            group_key = (school_year, exam_type, year_level)
            final_response.setdefault(group_key, []).append({
                "teacher_name": teacher_name,
                "subject": subject_name,
                "student_marks": student_marks
            })

        formatted_output = {}
        for (school_year, exam_type, year_level), data in final_response.items():
            marks_filtered = marks_qs.filter(
                term__year__year_name=school_year,
                exam_type__name=exam_type,
                student__level__level_name=year_level
            )
            first_mark = marks_filtered.first()
            report_id = first_mark.id if first_mark else None
            report_key = f"id : {report_id}" if report_id else f"{school_year}_{exam_type}_{year_level}".replace(" ", "_").lower()

            formatted_output[report_key] = {
                "school_year": school_year,
                "exam_type": exam_type,
                "year_level": year_level,
                "data": data
            }

        return Response(formatted_output)



    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated], url_path='create_marks')
    @transaction.atomic
    def create_marks(self, request):
        user = request.user
        role_names = [role.name.lower() for role in user.role.all()]

        is_director = "director" in role_names
        is_teacher = "teacher" in role_names

        if not (is_director or is_teacher):
            return Response({"error": "You do not have permission to perform this action."})

        if is_teacher:
            try:
                teacher = Teacher.objects.get(user=user)
            except Teacher.DoesNotExist:
                return Response({"error": "Teacher not found."})
            assigned_class_ids = TeacherYearLevel.objects.filter(
                teacher=teacher
            ).values_list("year_level_id", flat=True)
        else:
            teacher = None
            assigned_class_ids = []

        data = request.data
        school_year_id = data.get("school_year_id")
        exam_type_id = data.get("exam_type_id")
        year_level_id = data.get("year_level_id")

        # print("school_year_id:", school_year_id)
        # print("exam_type_id:", exam_type_id)
        # print("year_level_id:", year_level_id)

        if not school_year_id or not exam_type_id or not year_level_id:
            return Response({
                "error": "Missing required fields: school_year_id, exam_type_id, or year_level_id"
            }, status=400)

        try:
            school_year_obj = SchoolYear.objects.get(id=school_year_id)
            exam_type_obj = ExamType.objects.get(id=exam_type_id)
            year_level_obj = YearLevel.objects.get(id=year_level_id)
        except SchoolYear.DoesNotExist:
            return Response({"error": "Invalid school_year"})
        except ExamType.DoesNotExist:
            return Response({"error": "Invalid exam_type"})
        except YearLevel.DoesNotExist:
            return Response({"error": "Invalid year_level"})

        term_obj = Term.objects.filter(year=school_year_obj).first()
        if not term_obj:
            return Response({"error": "No term found for given school_year"})

        any_error = False
        errors = []     
        success = []   
        for group in data.get("data", []):
            teacher_id = group.get("teacher_id")
            subject_id = group.get("subject_id")

            try:
                teacher_obj = Teacher.objects.get(id=teacher_id)
                subject_obj = Subject.objects.get(id=subject_id)
            except (Teacher.DoesNotExist, Subject.DoesNotExist):
                any_error = True
                errors.append(f"Invalid teacher ({teacher_id}) or subject ({subject_id})")
                continue

            if is_teacher:
                if teacher.id != teacher_obj.id:
                    errors.append(f"Teacher mismatch: you are not allowed to submit for teacher ID {teacher_obj.id}")
                    any_error = True
                    continue
                if year_level_obj.id not in assigned_class_ids:
                    errors.append(f"Teacher not assigned to year_level ID {year_level_obj.id}")
                    any_error = True
                    continue

            for student_data in group.get("student_marks", []):
                student_id = student_data.get("student_id")
                marks = student_data.get("marks")

                try:
                    student_yl = StudentYearLevel.objects.get(id=student_id, level=year_level_obj)
                    student_name = student_yl.student.user.get_full_name()
                except StudentYearLevel.DoesNotExist:
                    errors.append(f"Student ID {student_id} not found in year_level {year_level_id}")
                    any_error = True
                    continue

                # ----- MARKS VALIDATION -----
                if marks is None:
                    errors.append(f"Marks missing for {student_name}")
                    any_error = True
                    continue

                if marks < 0:
                    errors.append(f"Marks cannot be negative for {student_name}")
                    any_error = True
                    continue

                # Check exam type max marks
                if exam_type_obj.name.lower().startswith("fa") and marks > 20:
                    errors.append(f"FA marks cannot exceed 20 for {student_name} in subject {subject_obj.subject_name}")
                    any_error = True
                    continue

                if exam_type_obj.name.lower().startswith("sa") and marks > 100:
                    errors.append(f"SA marks cannot exceed 100 for {student_name} in subject {subject_obj.subject_name}")
                    any_error = True
                    continue

                try:
                    obj, created = StudentMarks.objects.get_or_create(
                        student=student_yl,
                        subject=subject_obj,
                        exam_type=exam_type_obj,
                        term=term_obj,
                        defaults={
                            "marks_obtained": marks,
                            "teacher": teacher_obj
                        }
                    )

                    # print("Created:", created)
                    # print("Student:", student_id, "Subject:", subject_obj.subject_name, "Exists:", not created)

                    if created:
                        success.append(student_id)
                    else:
                        errors.append(f"Marks already exist for {student_name} in subject {subject_obj.subject_name}")
                        any_error = True
                except Exception as e:
                    errors.append(f"Unexpected error for student {student_id}: {str(e)}")
                    any_error = True

        # print("Full request data:", data)
        # print("Errors encountered:", errors)

        if any_error:
            return Response({
                "message": "Some marks could not be inserted. Either already exist or invalid data.",
                "errors": errors
            }, status=400)

        return Response({
            "message": "Marks inserted successfully.",
            "inserted_student_ids": success
        }, status=201)




    @action(detail=False, methods=['put'], permission_classes=[IsAuthenticated], url_path='update_marks')
    def update_marks(self, request):
        user = request.user
        role_names = [role.name.lower() for role in user.role.all()]

        is_director = "director" in role_names
        is_teacher = "teacher" in role_names

        if not (is_director or is_teacher):
            return Response({"error": "You do not have permission to perform this action."}, status=403)

        data = request.data.get("data", [])
        school_year_id = request.data.get("school_year_id")
        exam_type_id = request.data.get("exam_type_id")
        year_level_id = request.data.get("year_level_id")

        errors = []
        updated_ids = []

        try:
            school_year = SchoolYear.objects.get(id=school_year_id)
            exam_type = ExamType.objects.get(id=exam_type_id)
            term = Term.objects.filter(year=school_year).first()

            if not term:
                return Response({"error": f"No term found for school year {school_year_id}"})

        except Exception as e:
            return Response({"error": str(e)}, status=400)

        for item in data:
            subject_id = item.get("subject_id")

            try:
                subject = Subject.objects.get(id=subject_id)
            except Subject.DoesNotExist:
                errors.append(f"Subject not found with id {subject_id}")
                continue

            for student_data in item.get("student_marks", []):
                student_id = student_data.get("student_id")
                marks = student_data.get("marks")

                try:
                    student = StudentYearLevel.objects.get(
                        id=student_id,
                        level_id=year_level_id
                    )
                    student_name = student.student.user.get_full_name()

                    # ---------- VALIDATION (FIRST) ----------
                    if marks is None:
                        errors.append(f"Marks missing for {student_name}")
                        continue

                    if marks < 0:
                        errors.append(f"Marks cannot be negative for {student_name}")
                        continue

                    if exam_type.name.lower().startswith("fa") and marks > 20:
                        errors.append(f"FA marks cannot exceed 20 for {student_name}")
                        continue

                    if exam_type.name.lower().startswith("sa") and marks > 100:
                        errors.append(f"SA marks cannot exceed 100 for {student_name}")
                        continue

                    # ---------- FETCH MARKS ----------
                    student_mark = StudentMarks.objects.filter(
                        student=student,
                        subject=subject,
                        exam_type=exam_type,
                        term=term
                    ).first()

                    if not student_mark:
                        errors.append(
                            f"Marks not found for {student_name}, subject {subject.subject_name}"
                        )
                        continue

                    #----A CHECK FOR TEACHER UPDATION RIGHTS...
                    # if is_teacher and student_mark.teacher != teacher:
                    #     errors.append(
                    #         f"You cannot update marks assigned to another teacher for {student_name}"
                    #     )
                    #     continue

                    # ---------- SAVE (AFTER VALIDATION) ----------
                    student_mark.marks_obtained = marks
                    student_mark.save()

                    updated_ids.append(student_id)

                except StudentYearLevel.DoesNotExist:
                    errors.append(
                        f"StudentYearLevel not found for ID {student_id}"
                    )
                except Exception as e:
                    errors.append(
                        f"Error updating {student_id}: {str(e)}"
                    )

        if errors:
            return Response({
                "message": "Some marks could not be updated.",
                "errors": errors
            }, status=400)

        return Response({
            "message": "Marks updated successfully.",
            "updated": updated_ids
        },status=200)


"""-------------------------------------------RESULT---------------------------------------------------"""
from rest_framework.exceptions import PermissionDenied
from collections import defaultdict

class PersonalSocialQualityView(viewsets.ModelViewSet):
    queryset = PersonalSocialQuality.objects.all()
    serializer_class = PersonalSocialQualitySerializer
    permission_classes = [IsAuthenticated,IsDirectororOfficeStaff]

class PersonalSocialGradeViewSet(viewsets.ModelViewSet):
    queryset = PersonalSocialQualityTermWise.objects.all()
    serializer_class = PersonalSocialGradeSerializer
    permission_classes = [IsAuthenticated]

    # def _save_grade(self, request):
    #     serializer = self.get_serializer(data=request.data)
    #     serializer.is_valid(raise_exception=True)
    #     serializer.save()
    #     return Response(serializer.data)

    def _save_grade(self, request):
        is_bulk = isinstance(request.data, list)

        serializer = self.get_serializer(
            data=request.data,
            many=is_bulk
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def _can_teacher_access_report_card(self, teacher, report_card_id):
        if not teacher.year_levels.exists():
            raise PermissionDenied("You are not assigned to any classes.")
        return ReportCard.objects.filter(
            id=report_card_id,
            student_level__level__in=teacher.year_levels.all()
        ).exists()

    def get_queryset(self):
        user = self.request.user
        roles = [role.name for role in user.role.all()]
        student_id = self.request.query_params.get("student_id")
        report_card_id = self.request.query_params.get("report_card_id")

        qs = PersonalSocialQualityTermWise.objects.all()

        if "office_staff" in roles or "director" in roles:
            if student_id:
                qs = qs.filter(report_card__student_level__student__id=student_id)
            if report_card_id:
                qs = qs.filter(report_card__id=report_card_id)
            return qs

        elif "teacher" in roles:
            teacher = getattr(user, "teacher", None)
            if not teacher:
                return PersonalSocialQualityTermWise.objects.none()

            if not teacher.year_levels.exists():
                raise PermissionDenied("You are not assigned to any classes.")

            qs = qs.filter(
                report_card__student_level__level__in=teacher.year_levels.all()
            )

            if student_id:
                qs = qs.filter(report_card__student_level__student__id=student_id)

            if report_card_id:
                qs = qs.filter(report_card__id=report_card_id)

            return qs

        return PersonalSocialQualityTermWise.objects.none()

    def create(self, request, *args, **kwargs):
        user = request.user
        roles = [role.name for role in user.role.all()]

        if "office_staff" in roles or "director" in roles:
            return self._save_grade(request)

        elif "teacher" in roles:
            teacher = getattr(user, "teacher", None)
            report_card_id = request.data.get("report_card")

            if not teacher:
                return Response({"error": "Teacher profile not found."}, status=400)
            if not report_card_id:
                return Response({"error": "report_card ID is required"}, status=400)

            if self._can_teacher_access_report_card(teacher, report_card_id):
                return self._save_grade(request)
            else:
                return Response(
                    {"error": "You're not authorized to add grades for this report card."},
                    status=403
                )

        return Response({"error": "Not allowed for your role."}, status=403)

    def update(self, request, *args, **kwargs):
        user = request.user
        roles = [role.name for role in user.role.all()]
        instance = self.get_object()

        if "office_staff" in roles or "director" in roles:
            return super().update(request, *args, **kwargs)

        elif "teacher" in roles:
            teacher = getattr(user, "teacher", None)
            if not teacher:
                return Response({"error": "Teacher profile not found."}, status=400)

            report_card = instance.report_card
            if report_card.student_level.level in teacher.year_levels.all():
                return super().update(request, *args, **kwargs)
            else:
                return Response(
                    {"error": "Not authorized to update this grade."}, status=403
                )

        return Response({"error": "Not allowed for your role."}, status=403)

    def destroy(self, request, *args, **kwargs):
        user = request.user
        roles = [role.name for role in user.role.all()]
        instance = self.get_object()

        if "office_staff" in roles or "director" in roles:
            return super().destroy(request, *args, **kwargs)

        elif "teacher" in roles:
            teacher = getattr(user, "teacher", None)
            if not teacher:
                return Response({"error": "Teacher profile not found."}, status=400)

            report_card = instance.report_card
            if report_card.student_level.level in teacher.year_levels.all():
                return super().destroy(request, *args, **kwargs)
            else:
                return Response(
                    {"error": "Not authorized to delete this grade."}, status=403
                )

        return Response({"error": "Not allowed for your role."}, status=403)

class NonScholasticGradeViewSet(viewsets.ModelViewSet):
    queryset = NonScholasticGradeTermWise.objects.all()
    serializer_class = NonScholasticGradeTermWiseSerializer
    permission_classes = [IsAuthenticated]

    # def _save_grade(self, request):
    #     serializer = self.get_serializer(data=request.data)
    #     serializer.is_valid(raise_exception=True)
    #     serializer.save()
    #     return Response(serializer.data)

    def _save_grade(self, request):
        is_bulk = isinstance(request.data, list)

        serializer = self.get_serializer(
            data=request.data,
            many=is_bulk
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def _can_teacher_access_report_card(self, teacher, report_card_id):
        return ReportCard.objects.filter(
            id=report_card_id,
            student_level__level__in=teacher.year_levels.all()
        ).exists()
    
    def get_queryset(self):
        user = self.request.user
        roles = [role.name for role in user.role.all()]
        # print("role:",roles)
        student_id = self.request.query_params.get("student_id")
        report_card_id = self.request.query_params.get("report_card_id")

        if "office_staff" in roles or "director" in roles:
            qs = NonScholasticGradeTermWise.objects.all()
            if student_id:
                qs = qs.filter(report_card__student_level__student__id=student_id)
            if report_card_id:
                qs = qs.filter(report_card__id=report_card_id)
            return qs

        elif "teacher" in roles:
            teacher = getattr(user, "teacher", None)
            if not teacher:
                return PersonalSocialQualityTermWise.objects.none()

            if not teacher.year_levels.exists():
                raise PermissionDenied("You are not assigned to any classes.")

            qs = qs.filter(
                report_card__student_level__level__in=teacher.year_levels.all()
            )

            if student_id:
                qs = qs.filter(report_card__student_level__student__id=student_id)
            if report_card_id:
                qs = qs.filter(report_card__id=report_card_id)

            return qs


        return NonScholasticGradeTermWise.objects.none()

    def create(self, request, *args, **kwargs):
        user = request.user
        roles = [role.name for role in user.role.all()]

        if "office_staff" in roles or "director" in roles:
            return self._save_grade(request)

        elif "teacher" in roles:
            teacher = getattr(user, "teacher", None)
            report_card_id = request.data.get("report_card")

            if not teacher:
                return Response({"error": "Teacher profile not found."}, status=400)
            if not report_card_id:
                return Response({"error": "report_card ID is required"}, status=400)

            if self._can_teacher_access_report_card(teacher, report_card_id):
                return self._save_grade(request)
            else:
                return Response({"error": "You're not authorized to add grades for this report card."}, status=403)

        return Response({"error": "Not allowed for your role."}, status=403)

    def update(self, request, *args, **kwargs):
        user = request.user
        roles =[role.name for role in user.role.all()]

        instance = self.get_object()

        if "office_staff" in roles or "director" in roles:
            return super().update(request, *args, **kwargs)

        elif "teacher" in roles:
            teacher = user.teacher
            if not teacher:
                return Response({"error": "Teacher profile not found."}, status=400)

            report_card = instance.report_card
            if report_card.student_level.level in teacher.year_levels.all():
                return super().update(request, *args, **kwargs)
            else:
                return Response({"error": "Not authorized to update this grade."}, status=403)

        return Response({"error": "Not allowed for your role."}, status=403)

    def destroy(self, request, *args, **kwargs):
        user = request.user
        roles = [role.name for role in user.role.all()]

        instance = self.get_object()

        if "office_staff" in roles or "director" in roles:
            return super().destroy(request, *args, **kwargs)

        elif "teacher" in roles:
            teacher = user.teacher
            if not teacher:
                return Response({"error": "Teacher profile not found."}, status=400)

            report_card = instance.report_card
            if report_card.student_level.level in teacher.year_levels.all():
                return super().destroy(request, *args, **kwargs)
            else:
                return Response({"error": "Not authorized to delete this grade."}, status=403)

        return Response({"error": "Not allowed for your role."}, status=403)
    
    @action(detail=False, methods=["get"], url_path="non_schl_subject")
    def get_non_scholastic_subject(self, request):
        subjects = Subject.objects.filter(department__department_name__iexact="Non-Scholastic")
        serializer = subjectSerializer(subjects, many=True)
        return Response(serializer.data)
    
from director.permission import RoleBasedPermission

class ReportCardViewSet(viewsets.ModelViewSet):
    # queryset = ReportCard.objects.all()
    serializer_class = ReportCardSerializer
    permission_classes = [IsAuthenticated, RoleBasedPermission]
    # pagination_class = CreatePagination

    def get_user_roles(self):
        user = self.request.user
        return [role.name for role in user.role.all()]

    def get_queryset(self):
        qs = ReportCard.objects.all()  # ALWAYS start with a real queryset

        user = self.request.user
        roles = self.get_user_roles()

        student_id = self.request.query_params.get('student_id')
        standard_filter = self.request.query_params.get('standard')
        division_filter = self.request.query_params.get('division')

        if student_id:
            return qs.filter(student_level__student__id=student_id)

        if standard_filter:
            return qs.filter(student_level__level__level_name=standard_filter)

        if division_filter:
            return qs.filter(division=division_filter)

        # director & office staff → see all
        if 'director' in roles or 'office staff' in roles:
            return qs

        # teacher
        if 'teacher' in roles:
            try:
                teacher = user.teacher
                return qs.filter(student_level__level__in=teacher.year_levels.all())
            except Teacher.DoesNotExist:
                return qs.none()

        # guardian
        if 'guardian' in roles:
            student_ids = StudentGuardian.objects.filter(
                guardian__user=user
            ).values_list('student_id', flat=True)
            return qs.filter(student_level__student__id__in=student_ids)

        # student
        if 'student' in roles:
            return qs.filter(student_level__student__user=user)

        return qs.none()   # <-- never return None


    def get_attendance_string(self, report_card):
        student_level = report_card.student_level
        attendance_qs = Attendance.objects.filter(student=student_level.student)
        present = attendance_qs.filter(status='P').count()
        total = 225
        attendance= f"{present}/{total}" 
        return attendance

    def get_promoted_class(self, report_card):
        # division = report_card.division
        sup = report_card.supplementary_in
        failed_subjects = [s.strip() for s in ( sup or "").split(",") if s.strip()]
        
        if failed_subjects:
            return None
        
        # if division=="Fail":
        #     return None
            
        current_level = report_card.student_level.level
        current_year = report_card.student_level.year
        student = report_card.student_level.student

        # Try getting the next level
        next_level = YearLevel.objects.filter(level_order=current_level.level_order + 1).first()
        if not next_level:

            return None  # Already in the highest class
        
        next_year = SchoolYear.objects.filter(start_date__gt=current_year.start_date).order_by('start_date').first()
        if not current_year or not current_year.start_date:
            return None

        
        # Get or create the corresponding StudentYearLevel for next class in same year
        promoted_to, _ = StudentYearLevel.objects.get_or_create(
            student=student,
            level=next_level,
            year=next_year # or next academic year if needed
        )
        return promoted_to 

    def get_document(self, report_card):
        documents_data = []

        for doc_rel in report_card.documents.select_related("documents").all():
            document = doc_rel.documents
            if document:
                doc_types = list(document.document_types.values_list("name", flat=True))
                documents_data.append({
                    "identities": document.identities,
                    "document_types": doc_types
                })

        return documents_data

    def get_non_scholastic_data(self,report_card):
        return [
            {
                "subject": item.non_scholastic_subject.subject_name,
                "term": f"Term {item.term.term_number}",
                "grade": item.grade
            }
            for item in report_card.non_scholastic_grades.select_related("term", "non_scholastic_subject")
        ]
        
    def get_subject_score(self, report_card):
        from collections import defaultdict

        # Step 1: Get the StudentYearLevel linked to the report card
        student_level = report_card.student_level  # THIS is a StudentYearLevel instance

        # Step 2: Fetch all marks linked to that student_level
        marks_qs = StudentMarks.objects.select_related(
            "exam_type", "subject", "term", "student"
        ).filter(student=student_level)  # must pass StudentYearLevel instance

        if not marks_qs.exists():
            return []

        # Step 3: Group marks by exam type and subject
        temp = defaultdict(dict)
        for mark in marks_qs:
            exam_type = mark.exam_type.name.lower()
            subject = mark.subject.subject_name
            temp[exam_type][subject] = float(mark.marks_obtained or 0)

        # Step 4: Compute totals + grades
        examwise_summary = []
        for exam_type, subjects in temp.items():
            subject_count = len(subjects)
            is_fa = exam_type.startswith("fa")  # FA1/FA2 -> 20 marks per subject(before it was 10)
            max_per_subject = 20 if is_fa else 100
            total_obtained = sum(subjects.values())
            total_possible = subject_count * max_per_subject
            percentage = round((total_obtained / total_possible) * 100, 2) if total_possible else 0

            #  Add grading logic
            if percentage >= 90:
                grade = "A+"
            elif percentage >= 75:
                grade = "A"
            elif percentage >= 60:
                grade = "B"
            elif percentage >= 50:
                grade = "C"
            elif percentage >= 40:
                grade = "D"
            else:
                grade = "F"

            examwise_summary.append({
                "exam_type": exam_type.upper(),
                "subjects": subjects,
                "total_obtained": total_obtained,
                "total_possible": total_possible,
                "percentage": percentage,
                "grade": grade
            })

        return examwise_summary


    def sync_subject_scores(self, report_card):
        terms = Term.objects.filter(year=report_card.student_level.year)

        student_marks = StudentMarks.objects.filter(
            student=report_card.student_level,
            term__in=terms
        )
        for mark in student_marks:
            SubjectScore.objects.get_or_create(report_card=report_card, marks_obtained=mark)
    
    def save_documents(self, report_card):
        student = report_card.student_level.student
        student_docs = Document.objects.filter(
            student=student,
            document_types__isnull=False
        ).distinct()

        for doc in student_docs:
            # Only link if not already linked
            if not ReportCardDocument.objects.filter(report_card=report_card, documents=doc).exists():
                ReportCardDocument.objects.create(report_card=report_card, documents=doc)

    def save_subject_scores(self, report_card, subjects_data):
        for subject_data in subjects_data:
            subject_name = subject_data.get("subject")
            if not subject_name:
                continue
            subject = Subject.objects.get(subject_name=subject_name)
            for exam_key in ["fa1", "fa2", "fa3", "sa1", "sa2", "sa3"]:
                marks = subject_data.get(exam_key)
                if marks is not None:
                    exam_type = ExamType.objects.get(name__iexact=exam_key.upper())
                    term = Term.objects.filter(year=report_card.student_level.year.year_name).first()
                    student_marks = StudentMarks.objects.create(
                        exam_type=exam_type,
                        subject=subject,
                        term=term,
                        student=report_card.student_level.student,
                        teacher=Teacher.objects.first(),
                        marks_obtained=marks
                    )
                    SubjectScore.objects.create(
                        report_card=report_card,
                        marks_obtained=student_marks
                    )
                    # print("RC ID", report_card.id)  

    def save_non_scholastic(self, report_card, grades):
        for subject_name, values in grades.items():
            subject = Subject.objects.get(subject_name=subject_name)
            for term_key, grade in values.items():
                term = Term.objects.get(name__iexact=term_key)
                NonScholasticGradeTermWise.objects.create(
                    report_card=report_card,
                    non_scholastic_subject=subject,
                    term=term,
                    grade=grade
                )

    def save_personal_social(self, report_card, data):
        all_qualities = PersonalSocialQuality.objects.all()
        for term_key, quality_dict in data.items():
            term_number = 1 if term_key == "Term 1" else 2
            term = Term.objects.get(term_number=term_number, year=report_card.student_level.year)
            for quality in all_qualities:
                grade = quality_dict.get(quality.quality_name)
                if grade:
                    NonScholasticGradeTermWise.objects.create(
                        report_card=report_card,
                        personal_quality=quality,
                        term=term,
                        grade=grade
                    )



    def create(self, request, *args, **kwargs):
        roles = self.get_user_roles()
        if 'director' not in roles:
            if 'teacher' in roles:
                teacher = getattr(request.user, 'teacher', None)
                student_level_id = request.data.get("student_level")
                if teacher and student_level_id:
                    try:
                        student_level = StudentYearLevel.objects.get(id=student_level_id)
                        if student_level.level not in teacher.year_levels.all():
                            return Response({"error": "Permission denied."}, status=403)
                    except StudentYearLevel.DoesNotExist:
                        return Response({"error": "Invalid student_level ID."}, status=400)
                else:
                    return Response({"error": "Permission denied."}, status=403)
            else:
                return Response({"error": "Permission denied."}, status=403)
            
        data = request.data.copy()
        student_level = StudentYearLevel.objects.get(id=data.get("student_level"))
        student = student_level.student
        academic_year = student_level.year
        student_level = StudentYearLevel.objects.get(student=student, year=academic_year)

        existing = ReportCard.objects.filter(student_level=student_level).first()
        if existing:
            return Response(
                {"error": "Report card for this student and academic year already exists."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # STEP 1: Create report_card first with temporary placeholder values
        report_card = ReportCard.objects.create(
            student_level=student_level,
            total_marks=0,
            max_marks=0,
            percentage=0.0,
            grade="F",
            division="Fail",
            rank=data.get("rank"),
            attendance=None,
            supplementary_in = [],
            teacher_remark=data.get("teacher_remark"),
            promoted_to_class= None,#self.get_promoted_class(ReportCard),  
            school_reopen_date=parse_date(data.get("school_reopen_date"))
        )

        # STEP 2: Save related data (required for subject score calc)
        self.save_documents(report_card)
        self.save_subject_scores(report_card, data.get("subjects", []))
        self.save_non_scholastic(report_card, data.get("non_scholastic", {}))
        self.save_personal_social(report_card, data.get("personal_social", {}))

        # STEP 3: Sync marks to SubjectScore and recalculate
        self.sync_subject_scores(report_card)
        subjects = self.get_subject_score(report_card)
        subject_avg = calculate_subject_summary(subjects)

        total_obtained = subject_avg["total_marks"]
        total_possible = subject_avg["max_marks"]
        percentage = subject_avg["percentage"]
        grade = subject_avg["grade"]
        supplementary_in = ", ".join(subject_avg["supplementary_in"]) if subject_avg["supplementary_in"] else ""

        if percentage >= 60:
            division = "First"
        elif percentage >= 50:
            division = "Second"
        elif percentage >= 40:
            division = "Third"
        else:
            division = "Fail"

        # STEP 4: Save final calculated fields
        report_card.attendance = self.get_attendance_string(report_card)
        report_card.total_marks = total_obtained
        report_card.max_marks = total_possible
        report_card.percentage = percentage
        report_card.grade = grade
        report_card.division = division
        report_card.supplementary_in = supplementary_in
        report_card.promoted_to_class = self.get_promoted_class(report_card)
        
        report_card.save()

        return Response(self.build_report_card_response(report_card), status=status.HTTP_201_CREATED)
    
    def build_report_card_response(self, report_card):
        student = report_card.student_level.student
        user = student.user

        self.save_documents(report_card) 
        self.sync_subject_scores(report_card)
        subjects = self.get_subject_score(report_card)

        subject_avg = calculate_subject_summary(subjects)

        total_obtained = subject_avg["total_marks"]
        total_possible = subject_avg["max_marks"]
        percentage = subject_avg["percentage"]
        grade = subject_avg["grade"]
        supplementary_in = subject_avg["supplementary_in"]

        if percentage >= 60:
            division = "First"
        elif percentage >= 50:
            division = "Second"
        elif percentage >= 40:
            division = "Third"
        else:
            division = "Fail"


        documents_list = []

        for doc_link in report_card.documents.select_related("documents").all():
            doc = doc_link.documents
            if not doc:
                continue

            identities = doc.identities

            if not identities:
                continue

            # If already a list
            if isinstance(identities, list):
                identities_list = identities

            # If string → try JSON
            elif isinstance(identities, str):
                identities = identities.strip()

                if identities.startswith("[") or identities.startswith("{"):
                    try:
                        identities_list = json.loads(identities)
                        if not isinstance(identities_list, list):
                            identities_list = [identities_list]
                    except json.JSONDecodeError:
                        identities_list = [identities]
                else:
                    # plain string like Aadhaar / PAN
                    identities_list = [identities]

            else:
                identities_list = [str(identities)]

            for doc_type in doc.document_types.all():
                documents_list.append({
                    doc_type.name: identities_list[0] if identities_list else None
                })


        non_scholastic = {}
        for ns_grade in report_card.non_scholastic_grades.select_related("non_scholastic_subject", "term"):
            subject = ns_grade.non_scholastic_subject.subject_name
            term = f"Term {ns_grade.term.term_number}"
            if subject not in non_scholastic:
                non_scholastic[subject] = {}
            non_scholastic[subject][term] = ns_grade.grade

        personal_social = [
            {
                "quality": psq.personal_quality.quality_name,
                "term": f"Term {psq.term.term_number}",
                "grade": psq.grade
            }
            for psq in report_card.personal_qualities.select_related("personal_quality", "term")
        ]

        full_name = " ".join(filter(None, [user.first_name, user.middle_name, user.last_name]))

        return {
            "id": report_card.id,
            "student": student.id,
            "student_year_id": report_card.student_level.id,
            "student_name": full_name,
            "father_name": student.father_name,
            "mother_name": student.mother_name,
            "date_of_birth": student.date_of_birth,
            "contact_number": student.contact_number,
            "scholar_number": student.scholar_number,
            "standard": report_card.student_level.level.level_name,
            "academic_year": report_card.student_level.year.year_name,
            "total_marks": total_obtained,
            "max_marks": total_possible,
            "percentage": percentage,
            "grade": grade,
            "division": division,
            "rank": report_card.rank,
            "attendance": self.get_attendance_string(report_card),
            "teacher_remark": report_card.teacher_remark,
            "supplementary_in": supplementary_in,
            "promoted_to_class": (report_card.promoted_to_class.level.level_name 
                if report_card.promoted_to_class and report_card.promoted_to_class.level 
                else None),
            "school_reopen_date": report_card.school_reopen_date,
            "documents": documents_list,
            "subjects": self.get_subject_score(report_card),
            "subject_avg": subject_avg["subject_avg"],
            "non_scholastic": self.get_non_scholastic_data(report_card),
            "personal_social": personal_social,

        } 

    def retrieve(self, request, *args, **kwargs):
        report_card = self.get_object()
        data = self.build_report_card_response(report_card)
        return Response(data)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        return Response([self.build_report_card_response(rc) for rc in queryset])

    def update(self, request, *args, **kwargs):
        roles = self.get_user_roles()
        if 'director' not in roles:
            if 'teacher' in roles:
                teacher = getattr(request.user, 'teacher', None)
                instance = self.get_object()
                if not teacher or instance.student_level.level not in teacher.year_levels.all():
                    return Response({"error": "Permission denied."}, status=403)
            else:
                return Response({"error": "Permission denied."}, status=403)
            
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        data = request.data

        instance.total_marks = data.get("total_marks", instance.total_marks)
        instance.max_marks = data.get("max_marks", instance.max_marks)
        instance.percentage = data.get("percentage", instance.percentage)
        instance.grade = data.get("grade", instance.grade)
        instance.division = data.get("division", instance.division)
        instance.rank = data.get("rank", instance.rank)
        instance.attendance = data.get("attendance", instance.attendance)
        instance.teacher_remark = data.get("teacher_remark", instance.teacher_remark)
        instance.supplementary_in = data.get("supplementary_in", instance.supplementary_in)
        instance.school_reopen_date = data.get("school_reopen_date", instance.school_reopen_date)

        promoted_id = data.get("promoted_to_class")
        if promoted_id:
            instance.promoted_to_class_id = promoted_id

        instance.save()

        teacher = getattr(request.user, "teacher", None)
        if not teacher:
            teacher = Teacher.objects.filter(is_active=True).first()

        subjects_data = data.get("subjects", [])

        for sub in subjects_data:
            subject_name = sub.get("subject")
            exam_type = sub.get("exam_type")
            marks = sub.get("marks")

            if not (subject_name and exam_type):
                continue

            subject_obj = Subject.objects.filter(
                subject_name=subject_name
            ).exclude(
                department__department_name="Non-scholastic"
            ).first()

            if not subject_obj:
                continue

            exam_type_obj = ExamType.objects.get(name__iexact=exam_type)

            term_obj = Term.objects.filter(
                year=instance.student_level.year
            ).first()

            if not term_obj:
                continue

            StudentMarks.objects.update_or_create(
                student=instance.student_level,
                subject=subject_obj,
                exam_type=exam_type_obj,
                defaults={
                    "marks_obtained": marks,
                    "term": term_obj,
                    "teacher": teacher
                }
            )


        SubjectScore.objects.filter(report_card=instance).delete()
        marks_qs = StudentMarks.objects.filter(
            student=instance.student_level,
            term__year=instance.student_level.year
        )

        for mark in marks_qs:
            SubjectScore.objects.get_or_create(
                report_card=instance,
                marks_obtained=mark
            )

        documents_data = data.get("documents", {})
        if documents_data:
            # Clear existing linked documents
            instance.documents.all().delete()

            #  Fetch all documents related to the same student
            student_docs = Document.objects.filter(student=instance.student_level.student)

            #  Link all of them to the report card
            for doc in student_docs:
                ReportCardDocument.objects.create(
                    report_card=instance,
                    documents=doc
                )


        non_scholastic_data = data.get("non_scholastic", {})
        if non_scholastic_data:
            instance.non_scholastic_grades.all().delete()

            for subject_name, terms in non_scholastic_data.items():
                # fetch NON-scholastic subject safely
                subject_obj = Subject.objects.filter(
                    subject_name=subject_name,
                    department__department_name="Non-scholastic"
                ).first()

                if not subject_obj:
                    continue  # skip invalid subjects silently

                for term_name, grade in terms.items():
                    term_number = int(term_name.replace("Term", "").strip())
                    term_obj = Term.objects.get(term_number=term_number)

                    NonScholasticGradeTermWise.objects.create(
                        report_card=instance,
                        non_scholastic_subject=subject_obj,
                        term=term_obj,
                        grade=grade
                    )

        personal_data = data.get("personal_social", [])
        if personal_data:
            instance.personal_qualities.all().delete()
            for item in personal_data:
                quality = item.get("quality")
                term = item.get("term")
                grade = item.get("grade")
                try:
                    quality_obj = PersonalSocialQuality.objects.get(quality_name=quality)
                    term_obj = Term.objects.get(term_number=term)
                    PersonalSocialQualityTermWise.objects.create(
                        report_card=instance,
                        personal_quality=quality_obj,
                        term=term_obj,
                        grade=grade
                    )
                except Exception as e:
                    print("PSQ Update Error:", e)

        return self.retrieve(request, *args, **kwargs)



# ---------------------Expense 

class PaymentView(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

class ExpenseCategoryView(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsAuthenticated, ExpensePermission]

def get_current_school_year():
    today = date.today()
    return SchoolYear.objects.filter(
        start_date__lte=today,
        end_date__gte=today
    ).first()

    
class SchoolExpenseView(viewsets.ModelViewSet):
    queryset = SchoolExpense.objects.select_related("payment", "category", "school_year")
    serializer_class = SchoolExpenseSerializer
    permission_classes = [IsAuthenticated, ExpensePermission]

    def create(self, request, *args, **kwargs):
        data = request.data.copy()

        # ---------------------------------------------------------
        # 1. SALARY CATEGORY CHECK
        # ---------------------------------------------------------

        #payload for salary expense
        '''
        {
            "school_year": 1,
            "category": 2,
            "month": "December"
        }
        '''

        salary_category = ExpenseCategory.objects.filter(name__iexact="salary").first()
        selected_category = ExpenseCategory.objects.get(id=data.get("category"))

        if selected_category == salary_category:

            # Disallow manual amount / payment input
            if "payment" in data or "amount" in data:
                return Response({
                    "error": "You cannot provide amount or payment for Salary category. It is auto-calculated."
                }, status=400)

            # -----------------------------------------------------
            # choose month
            # -----------------------------------------------------
            requested_month = data.get("month")

            MONTHS = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]

            if not requested_month or requested_month not in MONTHS:
                return Response({
                    "error": "Invalid or missing month. Allowed: " + ", ".join(MONTHS)
                }, status=400)

            current_month = requested_month
            school_year = data.get("school_year")

            # Fetch employee salaries
            salaries = EmployeeSalary.objects.filter(
                month=current_month,
                school_year=school_year
            )

            # -----------------------------------------------------
            # Salary totals
            # -----------------------------------------------------
            total_salary = salaries.aggregate(total=models.Sum("net_amount"))["total"] or 0

            cash_paid = salaries.filter(payment__payment_method="Cash").aggregate(
                t=models.Sum("net_amount")
            )["t"] or 0

            cheque_paid = salaries.filter(payment__payment_method="Cheque").aggregate(
                t=models.Sum("net_amount")
            )["t"] or 0

            online_paid = salaries.filter(payment__payment_method="Online").aggregate(
                t=models.Sum("net_amount")
            )["t"] or 0

            summary_text = (
                f"Salary Expense for {current_month}\n\n"
                f"Total Salary: ₹{total_salary}\n"
                f"Cash Paid: ₹{cash_paid}\n"
                f"Cheque Paid: ₹{cheque_paid}\n"
                f"Online Paid: ₹{online_paid}"
            )


            # -----------------------------------------------------
            # Create salary expense (NO PAYMENT OBJECT)
            # -----------------------------------------------------
            expense = SchoolExpense.objects.create(
                category=salary_category,
                school_year_id=school_year,
                description=summary_text,
                created_by=request.user,
                approved_by=request.user,
                payment=None,            #  no Payment model used
            )

            return Response({
                "message": "Salary expense created automatically",
                "month": current_month,
                "expense_id": expense.id,
                "expense": SchoolExpenseSerializer(expense).data
            }, status=201)


        # ---------------------------------------------------------
        # 2. NORMAL EXPENSE CREATION 
        # ---------------------------------------------------------
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        payment_method = serializer.validated_data["payment"]["payment_method"]
        payment_data = serializer.validated_data["payment"]

        #cheque_number if cheque is selected
        if payment_method.lower() == "cheque":
            cheque_number = payment_data.get("cheque_number")

            if not cheque_number:
                return Response(
                    {"error": "cheque_number is required for cheque payments."},
                    status=400
                )

        # Save payment
        payment = Payment.objects.create(**payment_data)

        # Create expense
        expense = SchoolExpense.objects.create(
            category=serializer.validated_data["category"],
            school_year=serializer.validated_data["school_year"],
            description=serializer.validated_data.get("description"),
            created_by=request.user,
            payment=payment,
        )

        # OG LOGIC REBUILT PROPERLY
        if payment_method.lower() == "cash":
            payment.status = "Success"
            expense.approved_by = request.user
            payment.save()
            expense.save()
            return Response({
                "message": "Expense approved successfully (Cash)",
                "expense": SchoolExpenseSerializer(expense).data
            })

        elif payment_method.lower() == "cheque":
            payment.status = "Pending"
            payment.save()
            return Response({
                "message": "Cheque expense created, pending approval",
                "expense": SchoolExpenseSerializer(expense).data
            })

        elif payment_method.lower() == "online":
            payment.status = "Success"
            expense.approved_by = request.user
            payment.save()
            expense.save()
            return Response({
                "message": "Expense approved successfully (Online)",
                "expense": SchoolExpenseSerializer(expense).data
            })

        return Response({"error": "Invalid payment method"}, status=400)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        data = request.data.copy()

        # Detect SALARY category expense
        if instance.category.name.lower() == "salary":

            # which month? from PATCH body OR fallback from description
            month = data.get("month")

            if not month:
                # fallback: extract month from description
                first_line = instance.description.split("\n")[0]  # "Salary Expense for December"
                month = first_line.replace("Salary Expense for ", "").strip()

            # Fetch updated salary records
            salaries = EmployeeSalary.objects.filter(
                month=month,
                school_year=instance.school_year
            )

            if not salaries.exists():
                return Response({
                    "error": f"No employee salary records found for {month}."
                }, status=400)

            total_salary = salaries.aggregate(total=models.Sum("net_amount"))["total"] or 0
            cash_paid = salaries.filter(payment__payment_method="Cash").aggregate(t=models.Sum("net_amount"))["t"] or 0
            cheque_paid = salaries.filter(payment__payment_method="Cheque").aggregate(t=models.Sum("net_amount"))["t"] or 0
            online_paid = salaries.filter(payment__payment_method="Online").aggregate(t=models.Sum("net_amount"))["t"] or 0

            instance.description = (
                f"Salary Expense for {month}\n\n"
                f"Total Salary: ₹{total_salary}\n"
                f"Cash Paid: ₹{cash_paid}\n"
                f"Cheque Paid: ₹{cheque_paid}\n"
                f"Online Paid: ₹{online_paid}"
            )
            instance.save()

            return Response({
                "message": "Salary expense refreshed with latest records.",
                "expense": SchoolExpenseSerializer(instance).data
            })
        
        # ---------------------------------------------------------
        # 2. CHEQUE EXPENSE → APPROVE IF STILL PENDING
        # ---------------------------------------------------------
        if instance.payment and instance.payment.payment_method.lower() == "cheque":
            cheque_number = request.data.get("cheque_number")
            if cheque_number:
                instance.payment.cheque_number = cheque_number

            if instance.payment.status != "Success":
                instance.payment.status = "Success"
                instance.approved_by = request.user
                instance.save()

            instance.payment.save()

        # ---------------------------------------------------------
        # 3. ONLY DESCRIPTION CAN BE UPDATED
        # ---------------------------------------------------------
        description = request.data.get("description")
        if description is not None:
            instance.description = description
            instance.save()

            return Response(SchoolExpenseSerializer(instance).data)


        return Response({"error": "Only description can be updated."}, status=400)

class EmployeeView(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated,EmployeePermission]

    @action(detail=False, methods=["get"], url_path="get_emp")
    def get_emp(self, request):
        role = request.query_params.get("role")
        emp_id = request.query_params.get("id")   
        name = request.query_params.get("name")
        queryset = self.get_queryset()
        filters = Q()  


        if emp_id:
            try:
                employee = Employee.objects.get(pk=emp_id)
            except Employee.DoesNotExist:
                return Response({"error": "Employee not found"}, status=404)

            serializer = EmployeeSerializer(employee)
            return Response(serializer.data)

        if role:
            role_lower = role.lower()
            if role_lower == "teacher":
                all_teachers = User.objects.filter(role__name__iexact="teacher")
                employees_users = Employee.objects.values_list('user', flat=True)
                users_to_return = all_teachers.exclude(id__in=employees_users)

            elif role_lower == "office staff":
                all_staff = User.objects.filter(role__name__iexact="office staff")
                employees_users = Employee.objects.values_list('user', flat=True)
                users_to_return = all_staff.exclude(id__in=employees_users)

            else:
                users_to_return = User.objects.none()
                
            serializer = UserSerializer(users_to_return, many=True)
            return Response(serializer.data)

        if name:
            filters &= (
                Q(user__first_name__icontains=name) |
                Q(user__middle_name__icontains=name) |
                Q(user__last_name__icontains=name)
            )
        queryset = queryset.filter(filters).distinct()

        # queryset = self.get_queryset()
        serializer = self.get_serializer(queryset.distinct(), many=True)
        return Response(serializer.data)


    @action(detail=False, methods=["post"], url_path="create_emp")
    def create_emp(self, request):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        
        user_id = request.data.get("user")
        if not user_id:
            return Response({"error": "Employee is required."}, status=400)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "Invalid employee id."}, status=400)

        roles = [r.name.lower() for r in user.role.all()]
        if not any(r in ["teacher", "office staff"] for r in roles):
            return Response(
                {"error": "Only Teacher or Office Staff can be assigned as employee."},
                status=400
            )

        if Employee.objects.filter(user=user).exists():
            return Response(f"Salary is already created for {user.first_name} {user.last_name}".strip(), status=400)

        employee = Employee.objects.create(
            user=user,
            base_salary=serializer.validated_data["base_salary"],
        )

        serializer = self.get_serializer(employee)
        return Response({"message": "Employee created successfully.", "data": serializer.data}, status=201)


    # @action(detail=False, methods=["put"], url_path="update_emp")
    def update_emp(self, request):
        user_id = request.data.get("user")
        # joining_date = request.data.get("joining_date")

        # if not user_id or not joining_date:
        #     return Response({"error": "user and joining_date are required."}, status=400)
        if not user_id :
            return Response({"error": "user are required."}, status=400)

        try:
            # employee = Employee.objects.get(user_id=user_id, joining_date=joining_date)
            employee = Employee.objects.get(user_id=user_id)

        except Employee.DoesNotExist:
            return Response({"error": "Employee not found with this user and joining_date"}, status=404)

        serializer = self.get_serializer(employee, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Employee updated successfully", "data": serializer.data})
        return Response(serializer.errors, status=400)


    # @action(detail=False, methods=["delete"], url_path="delete_emp")
    # def delete_emp(self, request):
    #     try:
    #         employee = Employee.objects.get(id=request.data.get("id"))
    #         employee.delete()
    #         return Response({"message": "Employee deleted successfully."})
    #     except Employee.DoesNotExist:
    #         return Response({"error": "Employee not found"}, status=404)


    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(
            {"message": "Employee deleted successfully"},
            status=status.HTTP_200_OK
        )

class EmployeeSalaryView(viewsets.ModelViewSet):
    queryset = EmployeeSalary.objects.all()
    serializer_class = EmployeeSalarySerializer
    permission_classes = [IsAuthenticated, ExpensePermission]
    api_section = "employee_salary"

    def get_queryset(self):
        user = self.request.user
        queryset = EmployeeSalary.objects.all()

        roles = [r.name.lower() for r in user.role.all()]
        if hasattr(user, "employee") and "director" not in roles:
            queryset = queryset.filter(user=user.employee)
        # if hasattr(user, "employee"):
        #     queryset = queryset.filter(user=user.employee)

        school_year_id = self.request.query_params.get("school_year")
        month = self.request.query_params.get("month")
        employee_id = self.request.query_params.get("user")
        status = self.request.query_params.get("status")

        if school_year_id:
            queryset = queryset.filter(school_year_id=school_year_id)
        if month:
            queryset = queryset.filter(month=month)
        if employee_id:
            queryset = queryset.filter(user_id=employee_id)
        if status:
            queryset = queryset.filter(payment__status=status)

        return queryset


    def create(self, request, *args, **kwargs):
        employees_ids = request.data.get("employees", [])
        months = request.data.get("months", [])
        deductions = request.data.get("deductions", 0)
        bonus = request.data.get("bonus", 0)
        payment_method = request.data.get("payment_method")
        remarks = request.data.get("remarks", "")
        cheque_number = request.data.get("cheque_number")
        created_at = request.data.get("created_at")
        fund_account_id = request.data.get("fund_account_id")

        if not employees_ids or not months or not payment_method:
            return Response({"error": "employees, months, and payment_method are required"}, status=400)
        
        if payment_method == "Cheque" and not cheque_number:
            return Response({"error": "Cheque number is required for cheque payment."}, status=400)

        if payment_method == "Cash" and cheque_number:
            return Response({"error": "Cheque number should not be provided for cash payment."}, status=400)

        # if payment_method == "Online" and not fund_account_id:
        #     return Response({"error": "Fund account ID is required for online payment."}, status=400)


        if payment_method == "Cheque" and cheque_number:
            if Payment.objects.filter(cheque_number=cheque_number).exists():
                return Response({"error": "This cheque number is already used."}, status=400)


        created_at_obj = datetime.strptime(created_at, "%Y-%m-%d")
        if created_at_obj.date() > date.today():
            return Response({"error": "created_at cannot be in the future."}, status=400)

        # Ensure employees is always defined
        employees = Employee.objects.filter(id__in=employees_ids)
        if not employees.exists():
            return Response({"error": "No employees found with the given IDs."}, status=400)

        today = date.today()
        current_year = SchoolYear.objects.filter(start_date__lte=today, end_date__gte=today).first()

        if not current_year:
            return Response({"error": "No active SchoolYear found for today."}, status=400)

        created_salaries = []
        total_amount = 0
        messages = []

        for employee in employees:
            employee_email = employee.user.email  # Correct variable

            # Fetch teacher/staff for phone number
            teacher = Teacher.objects.filter(user__email=employee_email).first()
            staff = OfficeStaff.objects.filter(user__email=employee_email).first()
            phone_no = teacher.phone_no if teacher else (staff.phone_no if staff else None)

            # Bank account
            try:
                bank_account = BankingDetail.objects.get(user__email=employee_email, is_active=True)
                account_no = bank_account.account_no
                ifsc_code = bank_account.ifsc_code
                print("print statement : ",bank_account,account_no,ifsc_code)
            except BankingDetail.DoesNotExist:
                account_no = None
                ifsc_code = None

            for month in months:
                if EmployeeSalary.objects.filter(user=employee, month=month, school_year=current_year).exists():
                    messages.append(f"Salary already exists for {employee.user.get_full_name()} - {month}")
                    continue

                # gross = employee.base_salary
                # net_amount = gross + bonus - deductions
                # total_amount += net_amount

                gross = employee.base_salary
                net_amount = gross + bonus - deductions

                # Skip if net_amount is 0 or negative
                if net_amount <= 0:
                    messages.append(f"Cannot create salary for {employee.user.get_full_name()} {month}: deductions {deductions} exceed or equal base salary {gross}.")
                    continue

                total_amount += net_amount


                payment_status = "Success" if payment_method == "Cash" else "Pending"
                payment = Payment.objects.create(
                    amount=net_amount,
                    payment_method=payment_method,
                    status=payment_status,
                    payment_date=timezone.now(),
                    cheque_number=cheque_number if payment_method == "Cheque" else None
                )

                #  Add RazorpayX
                if payment_method == "Online":
                    auth = HTTPBasicAuth(settings.RAZORPAYX_KEY_ID, settings.RAZORPAYX_KEY_SECRET)

                    #create contact
                    response = requests.post(
                        "https://api.razorpay.com/v1/contacts",
                        auth=auth,
                        json={
                            "name": employee.user.get_full_name(),
                            "email": employee.user.email,
                            "contact": phone_no,
                            "type": "employee",
                            "reference_id": f"EMP-{employee.id}"
                        }
                    )
                    contact = response.json()
                    if "id" not in contact:
                        messages.append(f"Failed to create Razorpay contact for {employee.user.get_full_name()}: {contact.get('error', contact)}")
                        continue
                    contact_id = contact["id"]


                    #create fund account
                    response_fund = requests.post(
                        "https://api.razorpay.com/v1/fund_accounts",
                        auth=auth,
                        json={
                            "contact_id": contact_id,
                            "account_type": "bank_account",
                            "bank_account": {
                                "name": employee.user.get_full_name(),
                                "ifsc": ifsc_code,
                                "account_number": account_no
                            }
                        }
                    )
                    fund = response_fund.json()
                    if "id" not in fund:
                        messages.append(f"Failed to create fund account for {employee.user.get_full_name()}: {fund.get('error', fund)}")
                        continue
                    fund_id = fund["id"]

                    #safe narration for RazorpayX
                    import re
                    narration_text = f"Salary {month} {employee.user.get_full_name()}"
                    narration_text = re.sub(r"[^A-Za-z0-9\s]", "", narration_text)  # Only letters, numbers, space
                    narration_text = narration_text[:30]  

                    mode = "RTGS" if net_amount >= 200000 else "IMPS"

                    #initiate payout
                    response_payout = requests.post(
                        "https://api.razorpay.com/v1/payouts",
                        auth=auth,
                        json={
                            "account_number": settings.RAZORPAYX_ACCOUNT_NUMBER,
                            "fund_account_id": fund_id,
                            "amount": int(net_amount * 100),
                            "currency": "INR",
                            # "mode": "RTGS",
                            "mode": mode,
                            "queue_if_low_balance": True,
                            "purpose": "salary",
                            "narration": narration_text
                        }
                    )
                    payout = response_payout.json()
                    print(" RazorpayX Payout Response:", payout)

                    if getattr(settings, "TEST_MODE", False) and payment_method == "Online":
                        payment.status = "Success"  
                    else:
                        status_map = {
                            "processing": "Pending",
                            "queued": "Pending",
                            "pending": "Pending",
                            "processed": "Success",
                            "failed": "Failed",
                            "reversed": "Failed"
                        }
                        payment.status = status_map.get(payout.get("status", "").lower(), "Pending")

                    payment.contact_id = contact.get("id")
                    payment.fund_account_id = fund.get("id")
                    payment.payout_id = payout.get("id")
                    payment.save()

                salary = EmployeeSalary.objects.create(
                    user=employee,
                    school_year=current_year,
                    month=month,
                    gross_amount=gross,
                    bonus=bonus,
                    deductions=deductions,
                    net_amount=net_amount,
                    created_at=created_at,
                    payment=payment,
                    paid_by=request.user if payment_method.lower() == "cash" else None,
                    remarks=remarks
                )
                created_salaries.append(salary)

        return Response({
            "message": " | ".join(messages) if messages else "Salaries created successfully",
            "total_amount": total_amount,
            "salaries": EmployeeSalarySerializer(created_salaries, many=True).data
        })

    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        request_user = request.user
        roles = [role.name.lower() for role in request_user.role.all()]

        # EMPLOYEE SALARY fields allowed
        salary_allowed = ["remarks"]

        # PAYMENT fields allowed
        payment_allowed = ["payment_date", "status", "cheque_number"]

        # Block fields that should never update
        restricted_fields = [
            "employees", "months", "deductions", "bonus",
            "payment_method", "fund_account_id"
        ]
        for field in restricted_fields:
            if field in serializer.validated_data:
                return Response(
                    {"error": f"{field} cannot be updated once created."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # ----- UPDATE EMPLOYEE SALARY FIELDS -----
        for field in salary_allowed:
            if field in serializer.validated_data:
                setattr(instance, field, serializer.validated_data[field])

        # ----- UPDATE PAYMENT FIELDS -----
        payment = instance.payment
        if payment:

            # Payment Status (Director Only)
            if "status" in serializer.validated_data:
                if "director" not in roles:
                    return Response(
                        {"error": "Only Director can update salary status."},
                        status=status.HTTP_403_FORBIDDEN
                    )
                payment.status = serializer.validated_data["status"]
                instance.paid_by = request_user

            # Payment Date
            if "payment_date" in serializer.validated_data:
                payment_date = serializer.validated_data["payment_date"]

                payment.payment_date = timezone.make_aware(
                    datetime.combine(payment_date, datetime.min.time())
                )

            # Cheque Number
            if "cheque_number" in serializer.validated_data:
                payment.cheque_number = serializer.validated_data["cheque_number"]

            payment.save()

        instance.save()

        return Response({
            "message": "Salary updated successfully",
            "data": self.get_serializer(instance).data
        })
     
class IncomeCategoryView(viewsets.ModelViewSet):
    queryset = IncomeCategory.objects.all()
    serializer_class = IncomeCategorySerializer
    permission_classes = [IsAuthenticated,IsDirectororOfficeStaff]

class SchoolIncomeViewSet(viewsets.ModelViewSet):
    queryset = SchoolIncome.objects.all()
    serializer_class = SchoolIncomeSerializer
    permission_classes = [IsAuthenticated,IsDirectororOfficeStaff]
    
    def get_queryset(self):
        qs = super().get_queryset()
        request = self.request
        today = date.today()
        # the current school year
        current_school_year = SchoolYear.objects.filter(
            Q(start_date__lte=today), Q(end_date__gte=today)
        ).first()

        # skip filters on single-object actions
        if self.action in ["retrieve", "update", "partial_update", "destroy"]:
            return qs   

        # Get school_year param
        school_year_id = request.query_params.get("school_year")

        if school_year_id:
            qs = qs.filter(school_year_id=school_year_id) 
        elif current_school_year:
            qs = qs.filter(school_year=current_school_year)
            
        # apply optional filters
        category_id = request.query_params.get("category")
        if category_id:
            qs = qs.filter(category_id=category_id)

        month = request.query_params.get("month")
        if month:
            qs = qs.filter(month=month)

       
        return qs

class SchoolTurnOverViewSet(viewsets.ModelViewSet):
    queryset = SchoolTurnOver.objects.all()
    serializer_class = SchoolTurnOverSerializer
    permission_classes = [IsAuthenticated,IsDirectororOfficeStaff]  # keep your custom perms if needed

    def get_queryset(self):
        queryset = SchoolTurnOver.objects.all()

        school_year = self.request.query_params.get("school_year")
        verified_by = self.request.query_params.get("verified_by")
        is_locked = self.request.query_params.get("is_locked")

        if school_year:
            queryset = queryset.filter(school_year__id=school_year)
        if verified_by:
            queryset = queryset.filter(verified_by__id=verified_by)
        if is_locked is not None:
            queryset = queryset.filter(is_locked=is_locked.lower() == "true")

        return queryset

    def update(self, request, *args, **kwargs):
        if request.method == "PUT":
            return Response(
                {"detail": "PUT is not allowed. Use PATCH instead."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )
        return super().update(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        instance = serializer.save()

        # fetch previous year carry_forward
        prev_year = SchoolYear.objects.filter(id=instance.school_year.id - 1).first()
        if prev_year:
            try:
                prev_turnover = SchoolTurnOver.objects.get(school_year=prev_year)
                instance.carry_forward = {str(prev_year.year_name): float(prev_turnover.net_turnover or 0)}
                instance.save(update_fields=["carry_forward"])
            except SchoolTurnOver.DoesNotExist:
                pass
        
        self.update_totals(instance)

        # optional: auto-lock if needed
        if instance.is_locked:
            self._handle_verification(instance, self.request.user)

    def perform_update(self, serializer):
        instance_before = self.get_object()  # current DB state before save
        was_locked = instance_before.is_locked

        instance = serializer.save()
        self.update_totals(instance)

        # if it was unlocked and now locked -> verify + carry
        if instance.is_locked and not was_locked:
            self._handle_verification(instance, self.request.user)

    def perform_destroy(self, instance):
        if instance.is_locked:
            raise ValidationError("This turnover is locked and cannot be deleted.")
        super().perform_destroy(instance)

    # def update_totals(self, instance):
    #     income_sum = (
    #         SchoolIncome.objects.filter(
    #             school_year=instance.school_year, status="confirmed"
    #         ).aggregate(total=Sum("amount"))["total"]
    #         or 0
    #     )

    #     expense_sum = (
    #         SchoolExpense.objects.filter(
    #             school_year=instance.school_year, status="approved"
    #         ).aggregate(total=Sum("amount"))["total"]
    #         or 0
    #     )

    #     instance.total_income = income_sum
    #     instance.total_expense = expense_sum

    #     # calculate yearly profit
    #     yearly_profit = income_sum - expense_sum

    #     # add carry_forward safely as Decimal
    #     cf_total = sum(Decimal(str(v)) for v in instance.carry_forward.values()) if instance.carry_forward else Decimal(0)

    #     instance.net_turnover = yearly_profit + cf_total

    #     instance.save(update_fields=["total_income", "total_expense", "net_turnover"])
    def update_totals(self, instance):
        # calculate totals.
        income_sum = (
            SchoolIncome.objects.filter(
                school_year=instance.school_year, status="confirmed"
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

        expense_sum = (
            SchoolExpense.objects.filter(
                school_year=instance.school_year, status="approved"
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

        instance.total_income = income_sum
        instance.total_expense = expense_sum

        # existing logic: yearly profit
        yearly_profit = income_sum - expense_sum

        # add carry_forward safely as Decimal
        cf_total = sum(Decimal(str(v)) for v in instance.carry_forward.values()) if instance.carry_forward else Decimal(0)

        # net turnover = yearly profit + carry_forward
        instance.net_turnover = yearly_profit + cf_total

        # ---- new logic: financial outcome & status ----
        instance.financial_outcome = yearly_profit  # same as income - expense
        if instance.financial_outcome > 0:
            instance.financial_status = "Profit"
        elif instance.financial_outcome < 0:
            instance.financial_status = "Loss"
        else:
            instance.financial_status = "Break-even"
        # ------------------------------------------------

        # save all fields together
        instance.save(update_fields=[
            "total_income", "total_expense", "net_turnover",
            "financial_outcome", "financial_status"
        ])
   
    def _handle_verification(self, instance, user):
        if not instance.is_locked:
            instance.is_locked = True

        if user and getattr(user, "is_authenticated", False):
            instance.verified_by = user

        if not instance.verified_at:
            instance.verified_at = timezone.now()

        instance.save(update_fields=["verified_by", "verified_at", "is_locked"])



class MasterFeeViewSet(viewsets.ModelViewSet):
    queryset = MasterFee.objects.all()
    serializer_class = MasterFeeSerializer
    permission_classes = [IsAuthenticated]


class FeeStructureViewSet(viewsets.ModelViewSet):
    queryset = FeeStructure.objects.all()
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # queryset = super().get_queryset()
        queryset = FeeStructure.objects.annotate(
            student_fee_count=Count("student_fees")
        )
        year_level_id = self.request.query_params.get("year_level_id")
        if year_level_id:
            queryset = queryset.filter(year_level__id=year_level_id)

        school_year_id = self.request.query_params.get("school_year_id")
        if school_year_id:
            queryset = queryset.filter(school_year__id=school_year_id)
        
        return queryset

    def perform_destroy(self, instance):
        if instance.student_fees.exists():
            raise ValidationError(
                {"detail": "This fee structure has been used in student fees and cannot be deleted."}
            )
        instance.delete()


class FeePaymentView(viewsets.ModelViewSet):
    queryset = FeePayment.objects.all()
    serializer_class = FeePaymentSerializer
    permission_classes = [IsAuthenticated]
    
    #original_txn_no=icici_txn_id (in models)

    @action(detail=False, methods=["post"], url_path="icici/refund")
    def icici_refund(self, request):
        data = request.data

        payment_id = data.get("payment_id")
        original_txn_no = data.get("original_txn_no")
        merchant_txn_no = data.get("merchant_txn_no")
        amount = data.get("amount")
        aggregator_id = data.get("aggregator_id") or getattr(settings, "ICICI_AGGREGATOR_ID", None)

        # Optional: derive txn no from payment_id
        if payment_id and not original_txn_no:
            payment = get_object_or_404(FeePayment, pk=payment_id)
            original_txn_no = payment.icici_txn_id

        if not original_txn_no:
            return Response(
                {"error": "original_txn_no is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fetch ALL successful payments for this ICICI txn
        payments = FeePayment.objects.filter(
            icici_txn_id=original_txn_no,
            status="success",
        )

        if not payments.exists():
            return Response(
                {"error": "No successful payments found for this transaction"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Auto-generate refund merchant txn no
        if not merchant_txn_no:
            seed = f"refund-{original_txn_no}-{int(timezone.now().timestamp())}"
            merchant_txn_no = icici_generate_merchant_txn_no(seed, prefix="RFD")

        # Total refund amount = sum of linked payments (FULL refund)
        total_amount = sum(p.amount for p in payments)
        amount_str = icici_normalize_amount(total_amount)

        payload = {
            "merchantId": settings.ICICI_MERCHANT_ID,
            "merchantTxnNo": merchant_txn_no,
            "originalTxnNo": original_txn_no,
            "transactionType": "REFUND",
            "amount": amount_str,
        }

        if aggregator_id:
            payload["aggregatorID"] = aggregator_id

        payload["secureHash"] = icici_secure_hash_v1(payload, settings.ICICI_SECRET_KEY)

        try:
            response = requests.post(
                settings.ICICI_COMMAND_URL,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
        except Exception as exc:
            return Response(
                {"error": "ICICI command request failed", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        try:
            response_data = response.json()
        except ValueError:
            return Response(
                {
                    "error": "ICICI returned non-JSON response",
                    "status_code": response.status_code,
                    "raw_response": response.text[:500],
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        response_code = str(response_data.get("responseCode", ""))
        success_codes = {"000", "0000", "R1000"}

        if response_code not in success_codes:
            return Response(
                {
                    "error": "ICICI refund failed",
                    "icici_response": response_data,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ICICI refund SUCCESS → update DB
        for payment in payments:
            payment.status = "refunded"
            payment.icici_status_code = response_code
            note = (payment.notes or "").strip()
            payment.notes = f"{note} | ICICI refund {merchant_txn_no}".strip(" |")
            payment.save()

            # Adjust fee amounts safely (row-level)
            fee = payment.student_fee
            fee.paid_amount = max(
                fee.paid_amount - payment.amount,
                Decimal("0.00"),
            )
            fee.due_amount = max(
                fee.original_amount + fee.penalty_amount - fee.paid_amount,
                Decimal("0.00"),
            )

            if fee.paid_amount == 0:
                fee.status = "pending"
            elif fee.due_amount == 0:
                fee.status = "paid"
            else:
                fee.status = "partial"

            fee.save()

        return Response(
            {
                "request": payload,
                "icici_response": response_data,
                "refunded_payment_ids": list(payments.values_list("id", flat=True)),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="icici/status")
    def icici_status(self, request):
        data = request.data
        payment_id = data.get("payment_id")
        original_txn_no = data.get("original_txn_no")
        merchant_txn_no = data.get("merchant_txn_no")
        addl_param1 = data.get("addlParam1")
        aggregator_id = data.get("aggregator_id") or getattr(settings, "ICICI_AGGREGATOR_ID", None)

        payment = None
        if payment_id:
            payment = get_object_or_404(FeePayment, pk=payment_id)
            if not original_txn_no:
                original_txn_no = payment.icici_txn_id or payment.icici_merchant_txn_no

        if not original_txn_no:
            return Response(
                {"error": "original_txn_no is required (or provide payment_id with icici_txn_id)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not merchant_txn_no:
            merchant_txn_no = original_txn_no

        payload = {
            "merchantId": settings.ICICI_MERCHANT_ID,
            "merchantTxnNo": merchant_txn_no,
            "originalTxnNo": original_txn_no,
            "transactionType": "STATUS",
        }
        if aggregator_id:
            payload["aggregatorID"] = aggregator_id
        if addl_param1:
            payload["addlParam1"] = addl_param1

        payload["secureHash"] = icici_secure_hash_v1(payload, settings.ICICI_SECRET_KEY)

        try:
            response = requests.post(
                settings.ICICI_COMMAND_URL,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
        except Exception as exc:
            return Response({"error": "ICICI command request failed", "detail": str(exc)}, status=502)

        try:
            response_data = response.json()
        except ValueError:
            return Response(
                {
                    "error": "ICICI returned non-JSON response",
                    "status_code": response.status_code,
                    "raw_response": response.text[:500],
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        resp_hash = response_data.get("secureHash")
        if resp_hash:
            calc_hash = icici_secure_hash_v1(response_data, settings.ICICI_SECRET_KEY)
            if resp_hash.lower() != calc_hash.lower():
                return Response(
                    {"error": "ICICI secureHash mismatch", "icici_response": response_data},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        response_code = str(response_data.get("responseCode", ""))
        success_codes = {"000", "0000", "R1000"}
        txn_status = response_data.get("txnStatus")
        txn_resp_code = str(response_data.get("txnResponseCode", ""))

        if payment and payment.status == "pending":
            if txn_status == "SUC" and txn_resp_code in {"000", "0000"}:
                payment.status = "success"
                payment.icici_status_code = response_code or payment.icici_status_code
                payment.icici_txn_id = response_data.get("txnID") or payment.icici_txn_id
                payment.icici_payment_id = response_data.get("paymentID") or payment.icici_payment_id
                payment_time = None
                payment_time_raw = response_data.get("paymentDateTime") or response_data.get("txnDate")
                if payment_time_raw:
                    for fmt in ("%Y%m%d%H%M%S", "%Y%m%d%H%M"):
                        try:
                            payment_time = timezone.make_aware(datetime.strptime(payment_time_raw, fmt))
                            break
                        except ValueError:
                            continue
                payment.payment_date = payment_time or timezone.now()
                payment.save()

                fee = payment.student_fee
                fee.paid_amount += payment.amount
                fee.due_amount = max(
                    fee.original_amount + fee.penalty_amount - fee.paid_amount,
                    Decimal("0.00"),
                )
                fee.payment_method_output = "online"
                fee.status = "paid" if fee.due_amount == 0 else "partial"
                fee.save()
            elif txn_status in {"REJ", "ERR"} and response_code not in success_codes:
                payment.status = "failed"
                payment.icici_status_code = response_code or txn_resp_code or payment.icici_status_code
                payment.save()

        return Response(
            {
                "request": payload,
                "icici_response": response_data,
            },
            status=status.HTTP_200_OK if response_code in success_codes else status.HTTP_400_BAD_REQUEST,
        )


import uuid
class StudentFeeView(viewsets.ModelViewSet):
    queryset = StudentFee.objects.all()
    serializer_class = StudentFeeSerializer
    permission_classes = [IsAuthenticated]
    # pagination_class = CreatePagination


    def generate_receipt_number(self):
        today = timezone.now().strftime('%Y%m%d')
        last_receipt = StudentFee.objects.filter(receipt_number__startswith=f'REC-{today}').aggregate(Max('receipt_number'))

        if last_receipt['receipt_number__max']:
            parts = last_receipt['receipt_number__max'].split('-')
            last_number = int(parts[-2])
            new_number = last_number + 1
        else:
            new_number = 1

        unique_suffix = uuid.uuid4().hex[:4].upper()
        return f'REC-{today}-{new_number:05d}-{unique_suffix}'

    
    @action(detail=False, methods=["get"], url_path="student_unpaid_fees")
    def student_unpaid_fees(self, request):
        queryset = StudentFee.objects.filter(
            status__in=["pending", "partial"],
            student_year__student__is_active=True
        ).select_related(
            "student_year__student", "student_year__level", "school_year", "fee_structure"
        ).prefetch_related("payments")

        grouped = {}
        for fee in queryset:
            student = fee.student_year.student
            student_id = student.id
            month_name = calendar.month_name[fee.month] if fee.month else "Unknown"
            school_year_name = fee.school_year.year_name if fee.school_year else "Unknown"
            year_level = fee.student_year.level.level_name

            if student_id not in grouped:
                grouped[student_id] = {
                    "student": {
                        "id": student_id,
                        "name": f"{student.user.first_name} {student.user.last_name}",
                        "scholar_number": student.scholar_number 
                    },
                    "month": month_name,
                    "school_year": school_year_name,
                    "year_level_fees_grouped": [],
                    "total_amount": Decimal("0.00"),
                    "paid_amount": Decimal("0.00"),
                    "due_amount": Decimal("0.00"),
                }

            yl_group = next((yl for yl in grouped[student_id]["year_level_fees_grouped"] if yl["year_level"] == year_level), None)
            if not yl_group:
                yl_group = {"year_level": year_level, "fees": []}
                grouped[student_id]["year_level_fees_grouped"].append(yl_group)

            yl_group["fees"].append({
                "id": fee.id,
                "fee_type": fee.fee_structure.display_name(),
                "amount": str(fee.original_amount)
            })

            grouped[student_id]["total_amount"] += fee.original_amount
            grouped[student_id]["paid_amount"] += fee.paid_amount
            grouped[student_id]["due_amount"] += fee.due_amount

        for student_data in grouped.values():
            student_data["total_amount"] = str(student_data["total_amount"])
            student_data["paid_amount"] = str(student_data["paid_amount"])
            student_data["due_amount"] = str(student_data["due_amount"])

        return Response({"unpaid_fees": list(grouped.values())})

    @action(detail=False, methods=["get"], url_path="overdue_fees")
    def overdue_fees(self, request):
        student_year_id = request.query_params.get("student_year_id")
        month_filter = request.query_params.get("month")  # optional filter
        school_year_id = request.query_params.get("school_year_id")
        class_id = request.query_params.get("class_id")  # filter by class/level
        student_name_query = request.query_params.get("student_name")  # filter by student name
        
        today = timezone.now().date()
        current_month = today.month

        syl_qs = StudentYearLevel.objects.select_related('student', 'student__user', 'level').filter(student__is_active=True)
        if student_year_id:
            syl_qs = syl_qs.filter(id=student_year_id)
        if school_year_id:
            syl_qs = syl_qs.filter(year_id=school_year_id)
        if class_id:
            syl_qs = syl_qs.filter(level_id=class_id)
        if student_name_query:
            syl_qs = syl_qs.filter(
                Q(student__user__first_name__icontains=student_name_query) |
                Q(student__user__last_name__icontains=student_name_query)
            )

        all_syls = list(syl_qs)
        all_syl_ids = [syl.id for syl in all_syls]

        # Pre-fetch StudentFees
        all_paid_fees = StudentFee.objects.filter(student_year_id__in=all_syl_ids)
        paid_fees_by_syl_fee_month = defaultdict(Decimal)
        for pf in all_paid_fees:
            key = (pf.student_year_id, pf.fee_structure_id, pf.month)
            paid_fees_by_syl_fee_month[key] += pf.paid_amount

        # Pre-fetch Discounts
        all_discounts = AppliedFeeDiscount.objects.filter(student_id__in=all_syl_ids)
        discounts_by_syl_fee = defaultdict(Decimal)
        for d in all_discounts:
            key = (d.student_id, d.fee_type_id)
            discounts_by_syl_fee[key] += d.discount_amount

        # Pre-fetch FeeStructures
        all_fee_structures = FeeStructure.objects.prefetch_related('year_level').all()
        fees_by_year_level = defaultdict(list)
        for fee in all_fee_structures:
            for yl in fee.year_level.all():
                fees_by_year_level[yl.id].append(fee)

        ACADEMIC_MONTHS = [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6]
        valid_months = ACADEMIC_MONTHS

        MONTHLY_FEE_TYPES = {"tuition fee"}

        # Pre-fetch Admissions for stream matching
        all_student_ids = [syl.student_id for syl in all_syls]
        all_admissions = Admission.objects.filter(student_id__in=all_student_ids)
        admissions_by_student = {adm.student_id: adm for adm in all_admissions}

        VALID_STREAMS = {
            "commerce": "Comm/Arts",
            "comm": "Comm/Arts",
            "arts": "Comm/Arts",
            "pcm": "PCM/PCB",
            "pcb": "PCM/PCB",
        }

        response_data = []

        for syl in all_syls:
            student = syl.student
            if student and student.user:
                student_name = f"{student.user.first_name} {student.user.last_name}"
            else:
                student_name = "N/A"
                
            scholar_number = getattr(student, 'scholar_number', 'N/A')
            class_name = syl.level.level_name if syl.level else 'N/A'

            admission = admissions_by_student.get(student.id)
            student_stream = None
            if admission and admission.class_section:
                normalized_section = admission.class_section.strip().lower()
                if normalized_section in VALID_STREAMS:
                    student_stream = VALID_STREAMS[normalized_section]
            
            year_level_fees = fees_by_year_level.get(syl.level_id, [])
            
            for fee in year_level_fees:
                # Filter out tuition fees that don't match the student's stream, if they have one
                if fee.fee_type.lower() == 'tuition fee' and fee.tuition_sub_type and fee.tuition_sub_type != 'General':
                    if student_stream and fee.tuition_sub_type != student_stream:
                        continue

                is_monthly = fee.fee_type.lower() in MONTHLY_FEE_TYPES
                
                discount_total = discounts_by_syl_fee.get((syl.id, fee.id), Decimal('0.00'))
                base_amount = max(Decimal(fee.fee_amount) - discount_total, Decimal('0.00'))
                
                if is_monthly:
                    for month_number in valid_months:
                        if month_filter and str(month_number) != str(month_filter):
                            continue
                            
                        total_paid = paid_fees_by_syl_fee_month.get((syl.id, fee.id, month_number), Decimal('0.00'))
                        real_due = max(base_amount - total_paid, Decimal('0.00'))
                        
                        if real_due > 0:
                            status_str = "Partial" if total_paid > 0 else "Pending"
                            response_data.append({
                                "fee_id": fee.id,
                                "fee_type": fee.display_name(),
                                "original_amount": str(base_amount),
                                "paid_amount": str(total_paid),
                                "due_amount": str(real_due),
                                "status": status_str,
                                "due_date": today.strftime("%Y-%m-%d"),
                                "student_name": student_name,
                                "scholar_number": scholar_number,
                                "class_name": class_name,
                                "month": calendar.month_name[month_number],
                                "school_year": syl.year.year_name,
                            })
                else:
                    if month_filter: 
                        continue
                        
                    total_paid = paid_fees_by_syl_fee_month.get((syl.id, fee.id, None), Decimal('0.00'))
                    real_due = max(base_amount - total_paid, Decimal('0.00'))
                    
                    if real_due > 0:
                        status_str = "Partial" if total_paid > 0 else "Pending"
                        response_data.append({
                            "fee_id": fee.id,
                            "fee_type": fee.display_name(),
                            "original_amount": str(base_amount),
                            "paid_amount": str(total_paid),
                            "due_amount": str(real_due),
                            "status": status_str,
                            "due_date": today.strftime("%Y-%m-%d"),
                            "student_name": student_name,
                            "scholar_number": scholar_number,
                            "class_name": class_name,
                            "month": "None",
                            "school_year": syl.year.year_name,
                        })

        # ---- EXPORT / DOWNLOAD ----
        if request.query_params.get("download") == "true":
            return Response(response_data, status=drf_status.HTTP_200_OK)

        # ---- PAGINATE ----
        paginator = CreatePagination()
        page = paginator.paginate_queryset(response_data, request, view=self)
        if page is not None:
            return paginator.get_paginated_response(page)

        return Response(response_data, status=drf_status.HTTP_200_OK)


    @action(detail=False, methods=['post'], url_path='submit_fee')
    def submit_fee(self, request):
        with transaction.atomic():
            payment_mode = request.data.get("payment_method", "").lower()
            cheque_number = request.data.get("cheque_number") 
            student_year_id = request.data.get("student_year_id")
            school_year_id = request.data.get("school_year_id")
            fees_data = request.data.get("fees", [])

            if not student_year_id or not fees_data:
                return Response(
                    {"error": "student_year_id and fees are required."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            payment_date = request.data.get("payment_date")

            parsed_payment_date = timezone.now()

            if payment_date:
                try:
                    if "Z" in payment_date:
                        payment_date = payment_date.replace("Z", "+00:00")
                        
                    # Supports: 2026-07-28
                    if len(payment_date) == 10:
                        parsed_payment_date = timezone.make_aware(
                            datetime.strptime(payment_date, "%Y-%m-%d")
                        )
                    else:
                        # Supports: 2026-07-28T10:30:00 or with timezone
                        dt = datetime.fromisoformat(payment_date)
                        if timezone.is_naive(dt):
                            parsed_payment_date = timezone.make_aware(dt)
                        else:
                            parsed_payment_date = dt
                except Exception:
                    return Response(
                        {
                            "error": "Invalid payment_date. Use 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM:SS'."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            try:
                student_year = StudentYearLevel.objects.get(id=student_year_id)
            except StudentYearLevel.DoesNotExist:
                return Response({"error": "StudentYearLevel not found."}, status=status.HTTP_400_BAD_REQUEST)

            # Generate a single receipt number for all fees
            receipt_number = self.generate_receipt_number()

            # Get admission to fetch class_section
            admission = Admission.objects.filter(student=student_year.student).first()
            class_section = admission.class_section if admission else "N/A"

            total_amount = Decimal("0.00")
            created_records = []
            created_payments = []

            # --- PROCESS ALL FEES ---
            for fee_data in fees_data:
                amount_paid = Decimal(str(fee_data.get("amount", "0.00"))).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

                month_val = fee_data.get("month")  # None for yearly fees, 1-12 for monthly fees

                serializer = self.get_serializer(
                    data={
                        "student_year_id": student_year_id,
                        "fee_structure_id": fee_data.get("fee_type_id"),
                        "school_year_id": school_year_id,
                        "month": month_val,
                    },
                    context={'request': request, 'payment_method': payment_mode}
                )
                serializer.is_valid(raise_exception=True)
                student_fee = serializer.save()

                # --- Set due date ---
                due_date_str = fee_data.get("due_date")
                if due_date_str:
                    student_fee.due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                elif month_val not in (None, ""):
                    month = int(month_val)
                    due_year = get_fee_due_year(student_fee.school_year, month)
                    student_fee.due_date = date(due_year, month, 15)
                else:
                    # Yearly fee — no month, default due date to session start date
                    student_fee.due_date = student_fee.school_year.start_date
                
                # Penalty is not applied currently — intentionally left out
                max_payable = (
                    student_fee.original_amount - student_fee.paid_amount
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                if max_payable < 0:
                    max_payable = Decimal("0.00")

                if amount_paid > max_payable:
                    return Response(
                        {"error": f"Amount cannot exceed due amount: {max_payable} for fee type {student_fee.fee_structure.fee_type}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if payment_mode == "cheque" and not cheque_number:
                    return Response(
                        {"error": "Cheque number is required for cheque payment."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if payment_mode == "cheque" and cheque_number and len(created_records) == 0:
                    if FeePayment.objects.filter(cheque_number=cheque_number, payment_method="cheque").exists():
                        return Response(
                            {"error": "This cheque number has already been used."},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                # NOTE: removed the "admission fee must be paid in April" block entirely —
                # Admission Fee is now a yearly/no-month fee, same as Exam Fee, Caution Fee, etc.
                # No month-based restriction applies to it anymore.

                # --- CREATE FEE PAYMENT FOR EACH STUDENT FEE ---
                if payment_mode == "online":
                    # For online: create pending payment, will initiate later
                    seed = f"{student_fee.id}-{int(timezone.now().timestamp())}-{len(created_records)}"
                    merchantTxnNo = icici_generate_merchant_txn_no(seed, prefix="FEE")
                                        
                    fee_payment = FeePayment.objects.create(
                        student_fee=student_fee,
                        amount=amount_paid,
                        payment_method="online",
                        status="pending",
                        received_by=request.user,
                        notes=f"Online fee payment | Receipt {receipt_number}",
                        icici_merchant_txn_no=merchantTxnNo,
                        receipt_number=receipt_number,
                    )
                    created_payments.append(fee_payment)
                    
                else:
                    # For offline: create success payment immediately
                    fee_payment = FeePayment.objects.create(
                        student_fee=student_fee,
                        amount=amount_paid,
                        payment_method=payment_mode,
                        cheque_number=cheque_number if payment_mode == "cheque" else None,
                        status="success",
                        payment_date=parsed_payment_date,
                        received_by=request.user,
                        receipt_number=receipt_number,
                        notes=f"Fee payment for {student_fee.fee_structure.display_name()} - Month {student_fee.month}"
                    )
                    student_fee.paid_amount += amount_paid
                    created_payments.append(fee_payment)

                # Update due amount
                student_fee.due_amount = max(
                    student_fee.original_amount - student_fee.paid_amount,
                    Decimal("0.00")
                )

                # Set status
                if payment_mode == "online":
                    student_fee.status = "pending"
                else:
                    if student_fee.due_amount <= 0:
                        student_fee.status = "paid"
                    elif student_fee.paid_amount > 0:
                        student_fee.status = "partial"
                    else:
                        student_fee.status = "pending"

                student_fee.receipt_number = receipt_number
                student_fee.save()

                total_amount += amount_paid
                created_records.append(student_fee)

            # --- ONLINE PAYMENT: Initiate for all created payments ---
            if payment_mode == "online":
                # Create a batch transaction for ICICI
                return self.initiate_bulk_payment(request, created_payments, receipt_number, total_amount)

            # --- OFFLINE RESPONSE ---
            return Response(
                {
                    "message": "Fee record(s) submitted successfully!",
                    "student": {
                        "name": f"{student_year.student.user.first_name} {student_year.student.user.last_name}",
                        "class_name": student_year.level.level_name or "N/A",
                        "class_section": class_section
                        },
                    "payment_date": parsed_payment_date,
                    "school_year" : student_year.year.year_name if student_year.year.year_name else "N/A",
                    "receipt_number": receipt_number,
                    "total_amount_paid": str(total_amount),
                    "payment_mode": payment_mode,
                    "fees_processed": len(created_records),
                    "success": True
                },
                status=status.HTTP_201_CREATED
            )

    @action(detail=False, methods=["get"], url_path="fee_history")
    def fee_history(self, request):
            student_year_id = request.query_params.get("student_year_id")
            school_year_id = request.query_params.get("school_year_id")
            
            if not student_year_id or not school_year_id:
                return Response({"detail": "student_year_id and school_year_id are required"},
                                status=status.HTTP_400_BAD_REQUEST)
            
            student_fees = StudentFee.objects.filter(
                student_year_id=student_year_id,
                school_year_id=school_year_id
            ).prefetch_related('payments', 'fee_structure')

            result = []
            for sf in student_fees:
                payments = sf.payments.all()
                result.append({
                    "fee_type": sf.fee_structure.display_name(),
                    "tuition_sub_type": sf.fee_structure.tuition_sub_type,
                    "original_amount": str(sf.original_amount),
                    "paid_amount": str(sf.paid_amount),
                    "due_amount": str(sf.due_amount),
                    "status": sf.status,
                    "month": calendar.month_name[sf.month] if sf.month else None,
                    "payments": [{
                        "amount": str(p.amount),
                        "method": p.payment_method,
                        "status": p.status,
                        "date": p.payment_date
                    } for p in payments]
                })
            return Response(result)


    @action(detail=False, methods=["get"], url_path="pending_fees")
    def pending_fees(self, request):
        school_year_id = request.query_params.get("school_year_id")
        if not school_year_id:
            return Response({"detail": "school_year_id is required"},
                            status=status.HTTP_400_BAD_REQUEST)

        pending_fees = StudentFee.objects.filter(
            school_year_id=school_year_id
        ).exclude(status="paid")

        if not pending_fees.exists():
            return Response({"detail": "No pending fees found."}, status=status.HTTP_404_NOT_FOUND)

        response_data = []
        for fee in pending_fees:
            discount_obj = AppliedFeeDiscount.objects.filter(student=fee.student_year, fee_type=fee.fee_structure).first()
            discount_amount = discount_obj.discount_amount if discount_obj else 0

            adjusted_original_amount = max(fee.original_amount - discount_amount, 0)

            response_data.append({
                "fee_id": fee.id,
                "fee_type": fee.fee_structure.display_name(),
                "original_amount": str(adjusted_original_amount),
                "paid_amount": str(fee.paid_amount),
                "status": fee.status
            })

        return Response(response_data)


    @action(detail=False, methods=["get"], url_path="fee_preview")
    def preview(self, request):
        student_year_id = request.query_params.get("student_year_id")
        stream = request.query_params.get("stream")

        if not student_year_id:
            return Response({"detail": "student_year_id is required"}, status=drf_status.HTTP_400_BAD_REQUEST)
        try:
            student_year_level = StudentYearLevel.objects.get(id=student_year_id)
        except StudentYearLevel.DoesNotExist:
            return Response({"detail": "StudentYearLevel not found"}, status=drf_status.HTTP_404_NOT_FOUND)

        year_level = student_year_level.level
        school_year = student_year_level.year  # <-- needed for month/year label
        year_level_fees = FeeStructure.objects.filter(year_level=year_level)
        paid_fees = StudentFee.objects.filter(student_year=student_year_level)
        student = student_year_level.student

        # --- Student info block ---
        admission = Admission.objects.filter(
            student=student,
            school_year=school_year
        ).first()

        class_section = admission.class_section if admission else None
        
        # --- Student info block, using StudentYearLevelSerializer under the hood ---
        syl_data = StudentYearLevelSerializer(student_year_level).data

        student_info = {
            "student_name": syl_data.get("student_name"),
            "father_name": student_year_level.student.father_name,
            "mother_name": student_year_level.student.mother_name,
            "scholar_number": syl_data.get("scholar_number"),
            "class_name": syl_data.get("level_name"),
            "session": syl_data.get("year_name"),
            "class_section": syl_data.get("section"),
        }

        class_section = student_info["class_section"]

        # Validate stream param if explicitly provided
        VALID_STREAMS = {
            "commerce": "Comm/Arts",
            "comm": "Comm/Arts",
            "arts": "Comm/Arts",
            "pcm": "PCM/PCB",
            "pcb": "PCM/PCB",
        }        
        if stream:
            normalized_stream = stream.strip().lower()
            if normalized_stream not in VALID_STREAMS:
                return Response(
                    {"detail": "Invalid stream. Must be 'comm/arts' or 'pcm/pcb'."},
                    status=drf_status.HTTP_400_BAD_REQUEST
                )
            stream = VALID_STREAMS[normalized_stream]
        else:
            # No explicit stream passed — for class 11/12, class_section itself
            # holds the stream (e.g. "Comm/Arts", "PCM/PCB"). Use it as fallback.
            if class_section:
                normalized_section = class_section.strip().lower()
                if normalized_section in VALID_STREAMS:
                    stream = VALID_STREAMS[normalized_section]

        # Session starts in July
        ACADEMIC_MONTHS = [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6]

        MONTHLY_FEE_TYPES = {"tuition fee"}

        def build_fee_entry(fee, total_paid, discount_total, base_amount):
            real_due = max(base_amount - total_paid, Decimal("0.00"))
            if real_due == 0 and total_paid > 0:
                status_str = "Paid"
            elif total_paid > 0:
                status_str = "Partially Paid"
            else:
                status_str = "Pending"
            return {
                "fee_id": fee.id,
                "fee_type": fee.display_name(),
                "tuition_sub_type": fee.tuition_sub_type,
                "original_amount": str(base_amount),
                "paid_amount": str(total_paid),
                "status": status_str,
                "applied_discount": str(discount_total),
                "due_amount": str(real_due),
            }

        annual_fees = []
        monthly_fees = []
        for fee in year_level_fees:
            if fee.fee_type.lower() in MONTHLY_FEE_TYPES:
                # Apply stream filter only to tuition fees
                if stream and fee.tuition_sub_type != stream:
                    continue
                monthly_fees.append(fee)
            else:
                annual_fees.append(fee)

        # ---------- ANNUAL (one-time) fees ----------
        annual_result = []
        for fee in annual_fees:
            discount_total = AppliedFeeDiscount.objects.filter(
                student=student_year_level,
                fee_type=fee
            ).aggregate(total_discount=Sum('discount_amount'))['total_discount'] or Decimal('0.00')

            base_amount = max(Decimal(fee.fee_amount) - Decimal(discount_total), Decimal('0.00'))

            total_paid = paid_fees.filter(fee_structure=fee).aggregate(
                Sum('paid_amount')
            )['paid_amount__sum'] or Decimal('0.00')

            annual_result.append(build_fee_entry(fee, total_paid, discount_total, base_amount))

        # ---------- MONTHLY (recurring) fees ----------
        months_result = []
        for month_number in ACADEMIC_MONTHS:
            due_year = get_fee_due_year(school_year, month_number)
            month_label = f"{calendar.month_name[month_number]} {due_year}"
            month_data = {"month": month_label, "fees": []}

            for fee in monthly_fees:
                discount_total = AppliedFeeDiscount.objects.filter(
                    student=student_year_level,
                    fee_type=fee
                ).aggregate(total_discount=Sum('discount_amount'))['total_discount'] or Decimal('0.00')

                base_amount = max(Decimal(fee.fee_amount) - Decimal(discount_total), Decimal('0.00'))

                sf = paid_fees.filter(fee_structure=fee, month=month_number).first()
                total_paid = sf.paid_amount if sf else Decimal("0.00")

                month_data["fees"].append(build_fee_entry(fee, total_paid, discount_total, base_amount))

            if month_data["fees"]:
                months_result.append(month_data)

        return Response({
            "student": student_info,
            "annual": annual_result,
            "months": months_result,
        })
    
    
    def initiate_bulk_payment(self, request, fee_payments, receipt_number, total_amount):
        """
        Initiate ICICI payment for multiple fees
        - Creates one ICICI transaction with total amount
        - Stores all fee_payment IDs for later reconciliation
        """
        user = request.user
        
        if not fee_payments:
            return Response(
                {"error": "No payments to process"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get first fee payment's student details
        first_payment = fee_payments[0]
        student_fee = first_payment.student_fee
        student = student_fee.student_year.student

        # ICICI credentials (UAT)
        MERCHANT_ID = settings.ICICI_MERCHANT_ID
        AGGREGATOR_ID = settings.ICICI_AGGREGATOR_ID

        # Create a batch merchant transaction number
        # ICICI format: alphanumeric only, max 20 chars
        txn_date = timezone.now().strftime("%Y%m%d%H%M%S")
        
        # For ICICI, use the FIRST payment's merchant txn number
        batch_merchant_txn_no = fee_payments[0].icici_merchant_txn_no
        if not batch_merchant_txn_no:
            seed = f"batch-{receipt_number}-{int(timezone.now().timestamp())}"
            batch_merchant_txn_no = icici_generate_merchant_txn_no(seed, prefix="FEE")
        
        # Prepare ICICI payload
        amount_str = icici_normalize_amount(total_amount)
        raw_name = f"{student.user.first_name} {student.user.last_name}".strip()
        customer_name = re.sub(r"[^A-Za-z0-9 ]", "", raw_name).strip() or "Customer"
        customer_email = (student.user.email or "test@example.com").strip()
        raw_mobile = student.contact_number or ""
        mobile = re.sub(r"\D", "", raw_mobile)
        if len(mobile) < 10:
            mobile = "9999999999"

        payload = {
            "merchantId": MERCHANT_ID,
            "aggregatorID": AGGREGATOR_ID,
            "merchantTxnNo": batch_merchant_txn_no,  # Use first payment's unique number
            "amount": amount_str,
            "currencyCode": "356",
            "payType": "0",
            "transactionType": "SALE",
            "returnURL": settings.ICICI_RETURN_URL,
            "txnDate": txn_date,
            "customerName": customer_name,
            "customerEmailID": customer_email,
            "customerMobileNo": mobile,
        }

        # Generate secureHash (v1 - values concatenated by sorted parameter names)
        payload["secureHash"] = icici_secure_hash_v1(payload, settings.ICICI_SECRET_KEY)

        # Call ICICI Initiate Sale API
        url = settings.ICICI_INITIATE_SALE_URL
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        response = requests.post(url, json=payload, headers=headers, timeout=30)

        try:
            response_data = response.json()
        except ValueError:
            return Response(
                {
                    "error": "ICICI returned non-JSON response",
                    "status_code": response.status_code,
                    "raw_response": response.text[:500],
                },
                status=status.HTTP_502_BAD_GATEWAY
            )

        # Validate ICICI response
        if response_data.get("responseCode") != "R1000":
            # Rollback: Delete all pending payments and student fees
            for fp in fee_payments:
                student_fee = fp.student_fee
                fp.delete()
                student_fee.delete()
                
            return Response(
                {
                    "error": "ICICI initiation failed",
                    "icici_response": response_data
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update all fee payments with the FIRST payment's merchant txn number
        # (they all share the same batch_merchant_txn_no now)
        for fp in fee_payments:
            if fp.icici_merchant_txn_no != batch_merchant_txn_no:
                fp.icici_merchant_txn_no = batch_merchant_txn_no
            fp.notes = f"{fp.notes} | Batch Receipt: {receipt_number}"
            fp.save()

        redirect_url = (
            response_data["redirectURI"]
            + "?tranCtx="
            + response_data["tranCtx"]
        )

        # Return redirect URL to frontend
        return Response(
            {
                "redirect_url": redirect_url,
                "merchantTxnNo": batch_merchant_txn_no,
                "receipt_number": receipt_number,
                "total_amount": str(total_amount),
                "fees_count": len(fee_payments),
                "fee_payment_ids": [fp.id for fp in fee_payments]
            },
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=["get"], url_path="get_receipt")
    def get_receipt(self, request):
        receipt_number = request.query_params.get("receipt_number")
        if not receipt_number:
            return Response({"detail": "receipt_number is required"}, status=drf_status.HTTP_400_BAD_REQUEST)

        payments = FeePayment.objects.filter(
            receipt_number=receipt_number
        ).select_related(
            "student_fee",
            "student_fee__fee_structure",
            "student_fee__student_year",
            "student_fee__student_year__student",
            "student_fee__student_year__student__user",
            "student_fee__student_year__level",
            "student_fee__school_year",
        )

        if not payments.exists():
            return Response({"detail": "No receipt found with this number"}, status=drf_status.HTTP_404_NOT_FOUND)

        first_payment = payments.first()
        student_fee = first_payment.student_fee
        student_year = student_fee.student_year
        student = student_year.student

        admission = Admission.objects.filter(
            student=student,
            school_year=student_fee.school_year
        ).first()
        class_section = admission.class_section if admission else None

        parent_name = student.father_name or student.mother_name or "Not Mentioned"

        # Unique months across all payments in this receipt, in calendar order
        months_seen = set()
        for p in payments:
            if p.student_fee.month:
                months_seen.add(p.student_fee.month)
        months_sorted = sorted(months_seen)
        months_str = ", ".join(calendar.month_name[m] for m in months_sorted) if months_sorted else "N/A"

        # Particulars: group by fee_type display name, sum amount if repeated
        particulars = {}
        grand_total = Decimal("0.00")
        for p in payments:
            fee_label = p.student_fee.fee_structure.display_name()
            particulars[fee_label] = particulars.get(fee_label, Decimal("0.00")) + p.amount
            grand_total += p.amount

        particulars_list = [
            {"particular": label, "amount": str(amount)}
            for label, amount in particulars.items()
        ]

        return Response({
            "receipt_number": receipt_number,
            "date": first_payment.payment_date.strftime("%d %b %Y") if first_payment.payment_date else "N/A",
            "child_name": f"{student.user.first_name} {student.user.last_name}" if student.user else "N/A",
            "parent_name": parent_name,
            "months": months_str,
            "grade": student_year.level.level_name if student_year.level else "N/A",
            "section": class_section if class_section else "Not Mentioned",
            "particulars": particulars_list,
            "grand_total": str(grand_total),
            "payment_mode": first_payment.payment_method
        })

    @action(detail=False, methods=["get"], url_path="grouped_receipts")
    def grouped_receipts(self, request):
        student_year_id = request.query_params.get("student_year_id")
        receipt_number = request.query_params.get("receipt_number")

        # If student_year_id is provided → filter
        # Else → return ALL receipts
        fees_qs = StudentFee.objects.all()

        if student_year_id:
            fees_qs = fees_qs.filter(student_year_id=student_year_id)

        if receipt_number:
            fees_qs = fees_qs.filter(receipt_number=receipt_number)

        fees = fees_qs.select_related(
            "student_year__student__user",
            "student_year__level",
            "fee_structure"
        ).order_by("-created_at")

        if not fees.exists():
            return Response({"receipts": []})

        receipt_groups = {}
        for fee in fees:
            if fee.receipt_number not in receipt_groups:
                receipt_groups[fee.receipt_number] = {
                    "receipt_number": fee.receipt_number,
                    "payment_date": fee.created_at.date().strftime("%Y-%m-%d"),
                    "payment_mode": fee.payments.last().payment_method if fee.payments.exists() else None,
                    "total_amount_paid": Decimal("0.00"),
                    "school_year": fee.school_year.year_name if fee.school_year else "N/A",
                    "student": {
                        "id": fee.student_year.student.id,
                        "student_year_id": fee.student_year.id,
                        "name": f"{fee.student_year.student.user.first_name} {fee.student_year.student.user.last_name}",
                        "roll_number": fee.student_year.student.roll_number,
                        "father_name": fee.student_year.student.father_name,
                        "mother_name": fee.student_year.student.mother_name,
                        "scholar_number": fee.student_year.student.scholar_number,
                        "class_name": fee.student_year.level.level_name,
                        "class_section": getattr(
                            Admission.objects.filter(student=fee.student_year.student).first(),
                            "class_section",
                            "N/A"
                        ),
                    },
                    "guardian": {
                        "name": "",
                        "contact": ""
                    },
                    "fees_submitted": {}
                }

            discount_value = AppliedFeeDiscount.objects.filter(
                student=fee.student_year,
                fee_type=fee.fee_structure
            ).values_list("discount_amount", flat=True).first() or Decimal("0.00")

            month_name = calendar.month_name[fee.month] if fee.month else "Unknown"

            if month_name not in receipt_groups[fee.receipt_number]["fees_submitted"]:
                receipt_groups[fee.receipt_number]["fees_submitted"][month_name] = []

            receipt_groups[fee.receipt_number]["fees_submitted"][month_name].append({
                "fee_type": fee.fee_structure.display_name(),
                "tuition_sub_type": fee.fee_structure.tuition_sub_type,
                "amount_paid": str(fee.paid_amount),
                "original_amount": str(fee.original_amount),
                "discount": str(discount_value),
                "due_amount": str(fee.due_amount),
                "status": fee.status,
                "student_fee_id": fee.id,
            })

            receipt_groups[fee.receipt_number]["total_amount_paid"] += fee.paid_amount

        # Guardian details → only if receipts relate to 1 student
        student = fees.first().student_year.student

        parent_name = student.father_name or student.mother_name or "N/A"
        contact = student.contact_number if student.contact_number else "N/A"

        for rec in receipt_groups.values():
            rec["guardian"] = {
                "name": parent_name,
                "contact": contact,
            }

        # Convert Decimal totals to strings for JSON
        for rec in receipt_groups.values():
            rec["total_amount_paid"] = str(rec["total_amount_paid"])

        # ---- SORT MONTHS CHRONOLOGICALLY ----
        month_order = list(calendar.month_name)  # ['', 'January', 'February', ...]

        for rec in receipt_groups.values():
            fees_submitted = rec["fees_submitted"]

            rec["fees_submitted"] = {
                month: fees_submitted[month]
                for month in sorted(
                    fees_submitted.keys(),
                    key=lambda m: month_order.index(m) if m in month_order else 999
                )
            }

        # ---- Sort receipts (most recent first, matches original queryset order) ----
        receipts_list = sorted(
            receipt_groups.values(),
            key=lambda r: r["payment_date"],
            reverse=True
        )

        # ---- PAGINATE ----
        paginator = CreatePagination()
        page = paginator.paginate_queryset(receipts_list, request, view=self)
        if page is not None:
            return paginator.get_paginated_response(page)

        return Response(receipts_list, status=200)

    @action(detail=False, methods=["get"], url_path="search_receipts")
    def search_receipts(self, request):
        student = request.query_params.get("student")            # Name or Scholar Number
        class_id = request.query_params.get("class_id")          # Year Level ID
        school_year_id = request.query_params.get("school_year_id")
        month = request.query_params.get("month")                # e.g. 7 or July
        fee_type = request.query_params.get("fee_type")
        receipt_number = request.query_params.get("receipt_number")
        start_date = request.query_params.get("start_date")      # YYYY-MM-DD
        end_date = request.query_params.get("end_date")          # YYYY-MM-DD

        payments_qs = FeePayment.objects.select_related(
            "student_fee__student_year__student__user",
            "student_fee__student_year__level",
            "student_fee__fee_structure",
            "student_fee__school_year",
        ).order_by("-payment_date")

        # Receipt Number
        if receipt_number:
            payments_qs = payments_qs.filter(
                receipt_number__icontains=receipt_number
            )

        # Class
        if class_id:
            payments_qs = payments_qs.filter(
                student_fee__student_year__level_id=class_id
            )

        # School Year
        if school_year_id:
            payments_qs = payments_qs.filter(
                student_fee__school_year_id=school_year_id
            )

        # Fee Type
        if fee_type:
            if fee_type.startswith("Tuition Fee"):
                payments_qs = payments_qs.filter(
                    student_fee__fee_structure__fee_type="Tuition Fee"
                )

                if "(" in fee_type and ")" in fee_type:
                    sub_type = fee_type.split("(")[1].split(")")[0].strip()

                    payments_qs = payments_qs.filter(
                        student_fee__fee_structure__tuition_sub_type=sub_type
                    )
            else:
                payments_qs = payments_qs.filter(
                    student_fee__fee_structure__fee_type=fee_type
                )

        # Month
        if month:
            if month.isdigit():
                payments_qs = payments_qs.filter(
                    student_fee__month=int(month)
                )
            else:
                month_num = None
                for i, name in enumerate(calendar.month_name):
                    if name.lower() == month.strip().lower():
                        month_num = i
                        break
                if month_num:
                    payments_qs = payments_qs.filter(
                        student_fee__month=month_num
                    )

        # Student Name / Scholar Number
        if student:
            payments_qs = payments_qs.filter(
                Q(student_fee__student_year__student__user__first_name__icontains=student)
                | Q(student_fee__student_year__student__user__last_name__icontains=student)
                | Q(student_fee__student_year__student__scholar_number__icontains=student)
            )

        # Payment Date Range
        # Use timezone-aware datetime range so filtering works correctly on
        # MySQL in production where USE_TZ=True stores datetimes in UTC but
        # the app timezone is Asia/Kolkata. Raw __date__ lookups can miss
        # boundary records due to DB server UTC offset.
        if start_date:
            try:
                parsed_start = datetime.strptime(start_date, "%Y-%m-%d")
                start_dt = make_aware(
                    datetime.combine(parsed_start, dt_time.min)
                )  # 2026-07-27 00:00:00 IST → stored as UTC in DB
                payments_qs = payments_qs.filter(
                    payment_date__gte=start_dt
                )
            except ValueError:
                return Response(
                    {"error": "Invalid start_date. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if end_date:
            try:
                parsed_end = datetime.strptime(end_date, "%Y-%m-%d")
                end_dt = make_aware(
                    datetime.combine(parsed_end, dt_time.max)
                )  # 2026-07-27 23:59:59.999999 IST → stored as UTC in DB
                payments_qs = payments_qs.filter(
                    payment_date__lte=end_dt
                )
            except ValueError:
                return Response(
                    {"error": "Invalid end_date. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
        if not payments_qs.exists():
            return Response({"receipts": []}, status=200)

        # Group by receipt number
        receipt_groups = {}

        for payment in payments_qs:
            if not payment.receipt_number:
                continue

            student_fee = payment.student_fee
            student_year = student_fee.student_year
            student_obj = student_year.student

            if payment.receipt_number not in receipt_groups:
                admission = Admission.objects.filter(
                    student=student_obj,
                    school_year=student_fee.school_year
                ).first()

                receipt_groups[payment.receipt_number] = {
                    "receipt_number": payment.receipt_number,
                    "payment_date": payment.payment_date.strftime("%Y-%m-%d")
                    if payment.payment_date
                    else None,
                    "payment_method": payment.payment_method,
                    "payment_status": payment.status,
                    "school_year": (
                        student_fee.school_year.year_name
                        if student_fee.school_year
                        else "N/A"
                    ),
                    "student": {
                        "id": student_obj.id,
                        "student_year_id": student_year.id,
                        "name": (
                            f"{student_obj.user.first_name} {student_obj.user.last_name}"
                            if student_obj.user
                            else "N/A"
                        ),
                        "scholar_number": student_obj.scholar_number,
                        "class_name": (
                            student_year.level.level_name
                            if student_year.level
                            else "N/A"
                        ),
                        "class_section": (
                            admission.class_section
                            if admission
                            else "N/A"
                        ),
                    },
                    "total_amount_paid": Decimal("0.00"),
                    "payments": [],
                }

            receipt_groups[payment.receipt_number]["payments"].append({
                "payment_id": payment.id,
                "fee_type": student_fee.fee_structure.display_name(),
                "tuition_sub_type": student_fee.fee_structure.tuition_sub_type,
                "month": (
                    calendar.month_name[student_fee.month]
                    if student_fee.month
                    else None
                ),
                "amount": str(payment.amount),
                "payment_method": payment.payment_method,
                "status": payment.status,
                "cheque_number": payment.cheque_number,
            })

            receipt_groups[payment.receipt_number]["total_amount_paid"] += payment.amount

        for receipt in receipt_groups.values():
            receipt["total_amount_paid"] = str(receipt["total_amount_paid"])

        receipts_list = sorted(
            receipt_groups.values(),
            key=lambda x: x["payment_date"] or "",
            reverse=True,
        )

        paginator = CreatePagination()
        page = paginator.paginate_queryset(receipts_list, request, view=self)

        if page is not None:
            return paginator.get_paginated_response(page)

        return Response({"receipts": receipts_list}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=["get"], url_path="student-fee-card")
    def student_fee_card(self, request):
        student_id = request.query_params.get("student_id")
        if not student_id:
            return Response({"error": "student_id is required"}, status=400)

        student_year = StudentYearLevel.objects.filter(
            student_id=student_id,
            student__is_active=True
        ).select_related("student__user", "level").first()

        if not student_year:
            return Response({"error": "Student not found"}, status=404)

        fees = (
            StudentFee.objects.filter(student_year=student_year)
            .select_related("fee_structure")
            .order_by("month")
        )

        monthly_map = {}

        for fee in fees:
            month = fee.month
            if month not in monthly_map:
                monthly_map[month] = {
                    "month": calendar.month_name[month] if month else "Yearly",
                    "total_amount": Decimal("0.00"),
                    "paid_amount": Decimal("0.00"),
                    "due_amount": Decimal("0.00"),
                    "fee_type": []
                }

            total = fee.original_amount

            monthly_map[month]["total_amount"] += total
            monthly_map[month]["paid_amount"] += fee.paid_amount
            monthly_map[month]["fee_type"].append({
                "type": fee.fee_structure.display_name(),
                "tuition_sub_type": fee.fee_structure.tuition_sub_type,
                "amount": float(total)
            })

        result = {
            "student_id": student_year.student.id,
            "student_name": f"{student_year.student.user.first_name} {student_year.student.user.last_name}",
            "year_level": student_year.level.level_name,
            "monthly_summary": []
        }

        for data in monthly_map.values():
            data["due_amount"] = max(
                data["total_amount"] - data["paid_amount"], Decimal("0.00")
            )
            result["monthly_summary"].append({
                **data,
                "total_amount": float(data["total_amount"]),
                "paid_amount": float(data["paid_amount"]),
                "due_amount": float(data["due_amount"]),
            })

        return Response(result)


    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated], url_path="unpaid-fees")
    def unpaid_fees(self, request):
        user = request.user
        roles = [r.name.lower() for r in user.role.all()]

        if not any(r in roles for r in ["director", "teacher", "office staff"]):
            return Response({"detail": "Permission denied"}, status=403)

        class_id = request.query_params.get("class_id")
        month = request.query_params.get("month")
        min_due = request.query_params.get("min_due_amount")
        max_due = request.query_params.get("max_due_amount")
        ranking = request.query_params.get("ranking") == "true"
        top = request.query_params.get("top")

        qs = StudentFee.objects.filter(
            due_amount__gt=0,
            student_year__student__is_active=True
        ).select_related(
            "student_year__student__user",
            "student_year__level",
            "fee_structure"
        )

        # Teacher restriction
        if "teacher" in roles:
            teacher = get_object_or_404(Teacher, user=user)
            qs = qs.filter(student_year__level__in=teacher.year_levels.all())

        # Filters
        if class_id:
            qs = qs.filter(student_year__level_id=class_id)

        if month:
            qs = qs.filter(month=month)

        if min_due:
            qs = qs.filter(due_amount__gte=min_due)

        if max_due:
            qs = qs.filter(due_amount__lte=max_due)

        # Ranking logic
        if ranking:
            qs = qs.order_by("-due_amount")

        if top and ranking:
            try:
                qs = qs[:int(top)]
            except ValueError:
                pass

        data = []
        for fee in qs:
            data.append({
                "student_id": fee.student_year.student.id,
                "student_name": f"{fee.student_year.student.user.first_name} {fee.student_year.student.user.last_name}",
                "class": fee.student_year.level.level_name,
                "month": fee.month,
                "fee_type": fee.fee_structure.display_name(),
                "tuition_sub_type": fee.fee_structure.tuition_sub_type,
                "total_amount": float(fee.original_amount),
                "paid_amount": float(fee.paid_amount),
                "due_amount": float(fee.due_amount),
                "status": fee.status,
                "receipt_number": fee.receipt_number,
            })

        return Response({
            "ranking": ranking,
            "count": len(data),
            "results": data
        })

    @action(detail=False, methods=["get"], url_path="overdue_accounts_summary")
    def overdue_accounts_summary(self, request):
        school_year_id = request.query_params.get("school_year_id")
        if not school_year_id:
            return Response(
                {"error": "school_year_id is required"},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        today = timezone.now().date()

        syl_qs = StudentYearLevel.objects.select_related(
            'student', 'student__user', 'level', 'year'
        ).filter(year_id=school_year_id, student__is_active=True)

        all_syls = list(syl_qs)
        if not all_syls:
            return Response(
                {"error": "No students found for this school_year_id"},
                status=drf_status.HTTP_404_NOT_FOUND,
            )

        school_year_name = all_syls[0].year.year_name
        all_syl_ids = [syl.id for syl in all_syls]

        all_paid_fees = StudentFee.objects.filter(student_year_id__in=all_syl_ids)
        paid_fees_by_syl_fee_month = defaultdict(Decimal)
        for pf in all_paid_fees:
            key = (pf.student_year_id, pf.fee_structure_id, pf.month)
            paid_fees_by_syl_fee_month[key] += pf.paid_amount

        all_discounts = AppliedFeeDiscount.objects.filter(student_id__in=all_syl_ids)
        discounts_by_syl_fee = defaultdict(Decimal)
        for d in all_discounts:
            key = (d.student_id, d.fee_type_id)
            discounts_by_syl_fee[key] += d.discount_amount

        all_fee_structures = FeeStructure.objects.filter(
            school_year_id=school_year_id
        ).prefetch_related('year_level')
        fees_by_year_level = defaultdict(list)
        for fee in all_fee_structures:
            for yl in fee.year_level.all():
                fees_by_year_level[yl.id].append(fee)

        ACADEMIC_MONTHS = [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6]
        MONTHLY_FEE_TYPES = {"tuition fee"}

        all_student_ids = [syl.student_id for syl in all_syls]
        all_admissions = Admission.objects.filter(student_id__in=all_student_ids)
        admissions_by_student = {adm.student_id: adm for adm in all_admissions}

        VALID_STREAMS = {
            "commerce": "Comm/Arts",
            "comm": "Comm/Arts",
            "arts": "Comm/Arts",
            "pcm": "PCM/PCB",
            "pcb": "PCM/PCB",
        }

        classes = defaultdict(list)

        for syl in all_syls:
            student = syl.student
            student_name = f"{student.user.first_name} {student.user.last_name}" if student and student.user else "N/A"
            scholar_number = student.scholar_number if student and student.scholar_number else 'N/A'
            class_name = syl.level.level_name if syl.level else 'N/A'

            admission = admissions_by_student.get(student.id)
            student_stream = None
            if admission and admission.class_section:
                normalized_section = admission.class_section.strip().lower()
                if normalized_section in VALID_STREAMS:
                    student_stream = VALID_STREAMS[normalized_section]

            year_level_fees = fees_by_year_level.get(syl.level_id, [])

            available_subtypes = sorted({
                fee.tuition_sub_type for fee in year_level_fees
                if fee.fee_type == 'Tuition Fee' and fee.tuition_sub_type and fee.tuition_sub_type != 'General'
            })

            rows_for_student = []

            if student_stream:
                yearly, received = _calculate_student_totals(
                    syl, year_level_fees, discounts_by_syl_fee,
                    paid_fees_by_syl_fee_month, ACADEMIC_MONTHS,
                    MONTHLY_FEE_TYPES, stream_filter=student_stream
                )
                rows_for_student.append((student_name, student_stream, yearly, received))

            elif len(available_subtypes) >= 2:
                # No section defined, but class offers multiple tuition streams
                # -> one row per stream
                for subtype in available_subtypes:
                    yearly, received = _calculate_student_totals(
                        syl, year_level_fees, discounts_by_syl_fee,
                        paid_fees_by_syl_fee_month, ACADEMIC_MONTHS,
                        MONTHLY_FEE_TYPES, stream_filter=subtype
                    )
                    rows_for_student.append((student_name, subtype, yearly, received))

            else:
                # No stream ambiguity (0 or 1 tuition subtype in this class)
                yearly, received = _calculate_student_totals(
                    syl, year_level_fees, discounts_by_syl_fee,
                    paid_fees_by_syl_fee_month, ACADEMIC_MONTHS,
                    MONTHLY_FEE_TYPES, stream_filter=None
                )
                rows_for_student.append((student_name, None, yearly, received))

            for name, stream_label, yearly, received in rows_for_student:
                balance = max(yearly - received, Decimal('0.00'))
                classes[class_name].append({
                    "student_name": name,
                    "stream": stream_label,
                    "scholar_number": scholar_number,
                    "yearly_fees": yearly,
                    "received_fees": received,
                    "balance": balance,
                    "due": "Y" if balance > 0 else "N",
                })

        class_blocks = []
        grand_yearly = Decimal('0.00')
        grand_received = Decimal('0.00')
        grand_balance = Decimal('0.00')

        for class_name, students in classes.items():
            class_yearly = Decimal('0.00')
            class_received = Decimal('0.00')
            class_balance = Decimal('0.00')

            student_rows = []
            for idx, s in enumerate(students, start=1):
                display_name = s["student_name"]
                if s["stream"]:
                    display_name = f"{display_name} ({s['stream']})"

                student_rows.append({
                    "s_no": idx,
                    "student_name": display_name,
                    "stream": s["stream"],
                    "scholar_number": s["scholar_number"],
                    "yearly_fees": f"{s['yearly_fees']:.2f}",
                    "received_fees": f"{s['received_fees']:.2f}",
                    "balance": f"{s['balance']:.2f}",
                    "due": s["due"],
                })
                class_yearly += s["yearly_fees"]
                class_received += s["received_fees"]
                class_balance += s["balance"]

            class_blocks.append({
                "class_name": class_name,
                "student_count": len(students),
                "students": student_rows,
                "class_total": {
                    "yearly_fees": f"{class_yearly:.2f}",
                    "received_fees": f"{class_received:.2f}",
                    "balance": f"{class_balance:.2f}",
                },
            })

            grand_yearly += class_yearly
            grand_received += class_received
            grand_balance += class_balance

        response_data = {
            "title": "Overdue Accounts Summary",
            "school_year": school_year_name,
            "generated": today.strftime("%d-%b-%Y"),
            "classes": class_blocks,
            "grand_total": {
                "yearly_fees": f"{grand_yearly:.2f}",
                "received_fees": f"{grand_received:.2f}",
                "balance": f"{grand_balance:.2f}",
            },
        }

        return Response(response_data, status=drf_status.HTTP_200_OK)

        
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def icici_return(request):
    data = request.POST if request.method == "POST" else request.GET

    merchant_txn_no = data.get("merchantTxnNo")
    response_code = data.get("responseCode")
    secure_hash = data.get("secureHash")

    if not merchant_txn_no:
        return render(request, "payments/failed.html", {
            "response_code": "Invalid callback",
            "frontend_url": settings.FRONTEND_BASE_URL
        })

    payments = FeePayment.objects.filter(
        icici_merchant_txn_no=merchant_txn_no
    )

    if not payments.exists():
        return render(request, "payments/failed.html", {
            "response_code": "Payment not found",
            "frontend_url": settings.FRONTEND_BASE_URL
        })

    # Validate secure hash (v1). If missing or mismatch, reject.
    if not secure_hash:
        payments.update(
            status="failed",
            icici_status_code="HASH_MISSING"
        )
        return render(request, "payments/failed.html", {
            "response_code": "HASH_MISSING",
            "frontend_url": settings.FRONTEND_BASE_URL
        })

    calculated_hash = icici_secure_hash_v1(data, settings.ICICI_SECRET_KEY)
    if secure_hash.lower() != calculated_hash.lower():
        payments.update(
            status="failed",
            icici_status_code="HASH_MISMATCH"
        )
        return render(request, "payments/failed.html", {
            "response_code": "HASH_MISMATCH",
            "frontend_url": settings.FRONTEND_BASE_URL
        })

    if payments.filter(status="success").exists():
        return render(request, "payments/success.html", {
            "txn_id": payments.first().icici_txn_id,
            "frontend_url": settings.FRONTEND_BASE_URL
        })

    # FAILED
    success_codes = {"0000", "000"}
    if response_code not in success_codes:
        payments.update(
            status="failed",
            icici_status_code=response_code
        )
        return render(request, "payments/failed.html", {
            "response_code": response_code,
            "frontend_url": settings.FRONTEND_BASE_URL
        })

    # SUCCESS
    icici_txn_id = data.get("txnID")
    icici_payment_id = data.get("paymentID")
    payment_time = None
    payment_time_raw = data.get("paymentDateTime") or data.get("paymentDate") or data.get("txnDate")
    if payment_time_raw:
        for fmt in ("%Y%m%d%H%M%S", "%Y%m%d%H%M"):
            try:
                payment_time = timezone.make_aware(datetime.strptime(payment_time_raw, fmt))
                break
            except ValueError:
                continue

    for payment in payments:
        payment.status = "success"
        payment.icici_status_code = response_code
        payment.icici_txn_id = icici_txn_id
        payment.icici_payment_id = icici_payment_id
        payment.payment_date = payment_time or timezone.now()
        payment.save()

        fee = payment.student_fee
        fee.paid_amount += payment.amount
        fee.due_amount = max(
            fee.original_amount - fee.paid_amount,
            Decimal("0.00")
        )
        fee.payment_method_output = "online"
        fee.status = "paid" if fee.due_amount == 0 else "partial"
        fee.save()

    return render(request, "payments/success.html", {
        "txn_id": icici_txn_id,
        "frontend_url": settings.FRONTEND_BASE_URL
    })


def student_display_name(student):
    return f"{student.user.first_name} {student.user.last_name}"
class AppliedFeeDiscountViewSet(viewsets.ModelViewSet):
    queryset = AppliedFeeDiscount.objects.all()
    serializer_class = AppliedFeeDiscountSerializer 
    permission_classes = [IsAuthenticated]


    def list(self, request):
        student_year_id = request.query_params.get("student_year_id")

        if student_year_id:
            return Response({
                "available_fees": self.get_available_fees(student_year_id),
                "applied_discounts": self.get_applied_discounts(student_year_id)
            })
        else:
            queryset = self.queryset.select_related(
                "student", "student__level", "student__year", "fee_type", "approved_by"
            )
            serializer = AppliedFeeDiscountSerializer(queryset, many=True)
            return Response(serializer.data)

    def get_available_fees(self, student_year_id):
        fees = StudentFee.objects.filter(
            student_year_id=student_year_id,
            status__in=["pending", "partial"]
        ).select_related(
            'student_year',
            'student_year__student',
            'student_year__level',
            'student_year__year',
            'fee_structure'
        )

        fee_list = []
        for fee in fees:
            original_amount = Decimal(str(fee.original_amount))
            due_amount = Decimal(str(fee.due_amount))
            fee_list.append({
                "student_fee_id": fee.id,
                "student_year_id": fee.student_year.id,
                "student_class": fee.student_year.level.level_name if fee.student_year.level else None,
                "school_year": fee.student_year.year.year_name if fee.student_year.year else None,
                "fee_type": fee.fee_structure.display_name(),
                "tuition_sub_type": fee.fee_structure.tuition_sub_type,
                "original_amount": float(original_amount),
                "due_amount": float(due_amount),
                "student_name": student_display_name(fee.student_year.student)
            })
        return fee_list

    def get_applied_discounts(self, student_year_id):
        discounts = AppliedFeeDiscount.objects.filter(
            student_id=student_year_id
        ).select_related(
            "student", "student__level", "student__year", "fee_type", "approved_by"
        )

        discount_list = []
        for d in discounts:
            original_amount = Decimal(str(d.fee_type.fee_amount))
            discount_amount = d.discount_amount
            discount_percentage = (discount_amount / original_amount * Decimal('100')) if original_amount else Decimal('0')

            discount_list.append({
                "id": d.id,
                "student": student_display_name(d.student.student),
                "student_year_id": d.student.id,
                "student_class": d.student.level.level_name if d.student.level else None,
                "school_year": d.student.year.year_name if d.student.year else None,
                "fee_type": d.fee_type.display_name(),
                "tuition_sub_type": d.fee_type.tuition_sub_type,
                "discount_name": d.discount_name,
                "discount_amount": float(discount_amount),
                "discounted_amount_percent": float(discount_percentage),
                "approved_by": getattr(d.approved_by, "username", "Admin"),
                "approved_at": d.approved_at,
            })

        return discount_list


    @action(detail=False, methods=["post"], url_path="apply")
    @transaction.atomic

    def apply_discount(self, request):
        user = request.user
        student_year_id = request.data.get("student_year_id")
        fee_structure_id = request.data.get("fee_structure_id")
        discount_name = request.data.get("discount_name")
        discount_percentage = request.data.get("discounted_amount_percent")

        user_roles = [r.name.lower() for r in request.user.role.all()]
        if "director" not in user_roles:
            return Response({"detail": "Only directors are authorized to apply discounts."}, status=403)

        if not all([student_year_id, fee_structure_id, discount_name, discount_percentage]):
            return Response(
                {"detail": "student_year_id, fee_structure_id, discount_name, and discounted_amount_percent are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            student_year = StudentYearLevel.objects.get(id=student_year_id)
            fee_structure = FeeStructure.objects.get(id=fee_structure_id)
        except (StudentYearLevel.DoesNotExist, FeeStructure.DoesNotExist):
            return Response(
                {"detail": "Invalid student_year_id or fee_structure_id."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not hasattr(student_year, "student") or not hasattr(student_year.student, "user"):
            return Response(
                {"detail": "Invalid student record. Discount can only be applied to valid students."},
                status=status.HTTP_400_BAD_REQUEST,
            )


        if not fee_structure.year_level.filter(id=student_year.level.id).exists():
            return Response({
                "detail": "Discount can only be applied to fees of the student's own class."
            }, status=400)

        try:
            discount_percent = Decimal(str(discount_percentage))
            if discount_percent < 0 or discount_percent > 100:
                return Response(
                    {"detail": "Discount percentage must be between 0 and 100."},
                    status=status.HTTP_400_BAD_REQUEST,
                )


            max_allowed_percent = Decimal("90.00")
            if discount_percent > max_allowed_percent:
                return Response(
                    {"detail": f"Discount cannot exceed {max_allowed_percent}% of the fee."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            fee_amount = Decimal(fee_structure.fee_amount or 0)
            final_discount_amount = (fee_amount * discount_percent) / Decimal("100")

            if final_discount_amount > fee_amount:
                return Response(
                    {"detail": "Discount amount cannot be greater than the fee amount."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except Exception as e:
            return Response(
                {"detail": f"Invalid discount percentage: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if AppliedFeeDiscount.objects.filter(student=student_year, fee_type=fee_structure).exists():
            return Response(
                {"detail": "Discount already applied for this student and fee type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        discount = AppliedFeeDiscount.objects.create(
            student=student_year,
            fee_type=fee_structure,
            discount_name=discount_name,
            discount_amount=final_discount_amount,
            approved_by=user,
            approved_at=timezone.now(),
        )

        return Response(
            {
                "detail": "Discount applied successfully",
                "student_name": f"{student_year.student.user.first_name} {student_year.student.user.last_name}",
                "student_year_id": student_year.id,
                "fee_type": fee_structure.display_name(),
                "tuition_sub_type": fee_structure.tuition_sub_type,
                "discount_name": discount.discount_name,
                "discount_amount": float(final_discount_amount),
                "discounted_amount_percent": float(discount_percentage),
                "approved_by": getattr(user, "username", "Admin"),
            },
            status=status.HTTP_200_OK,
        )


    @action(detail=True, methods=["put"], url_path="update_discount")
    @transaction.atomic
    def update_discount(self, request, pk=None):
        user = request.user
        discount = self.get_object()  

        user_roles = [r.name.lower() for r in user.role.all()]
        if "director" not in user_roles:
            return Response({"detail": "Only directors can update discounts."}, status=403)

        discount_name = request.data.get("discount_name")
        discounted_amount_percent = request.data.get("discounted_amount_percent")

        if not all([discount_name, discounted_amount_percent]):
            return Response({"detail": "Both discount_name and discounted_amount_percent are required."}, status=400)

        try:
            discount_percent = Decimal(str(discounted_amount_percent))
            if not (0 <= discount_percent <= 100):
                raise ValueError("Discount must be 0-100%.")

            max_percent = Decimal("80.00")
            if discount_percent > max_percent:
                return Response({"detail": f"Discount cannot exceed {max_percent}%."}, status=400)

            fee_amount = Decimal(discount.fee_type.fee_amount or 0)
            final_discount_amount = (fee_amount * discount_percent) / Decimal("100")
        except Exception as e:
            return Response({"detail": f"Invalid discount percentage: {e}"}, status=400)

        discount.discount_name = discount_name
        discount.discount_amount = final_discount_amount
        discount.approved_by = user
        discount.approved_at = timezone.now()
        discount.save(update_fields=["discount_name", "discount_amount", "approved_by", "approved_at"])

        return Response({
            "detail": "Discount updated successfully",
            "student_name": student_display_name(discount.student.student),
            "student_year_id": discount.student.id,
            "fee_type": discount.fee_type.display_name(),
            "tuition_sub_type": discount.fee_type.tuition_sub_type,
            "discount_name": discount.discount_name,
            "discount_amount": float(final_discount_amount),
            "discounted_amount_percent": float(discount_percent),
            "approved_by": getattr(user, "username", "Admin"),
        }, status=200)


class DefaulterNotifyView(APIView):
    def get(self, request):
        year_level_id = request.query_params.get("year_level")
        section = request.query_params.get("section")

        # Filter class + section
        admissions = Admission.objects.filter(is_active=True)

        if year_level_id:
            admissions = admissions.filter(year_level_id=year_level_id)

        if section:
            admissions = admissions.filter(class_section=section)

        # Fetch students belonging to filtered admissions
        student_year_ids = admissions.values_list("student__id", flat=True)
        student_year_levels = StudentYearLevel.objects.filter(student_id__in=student_year_ids, student__is_active=True)

        today = timezone.now().date()
        three_months_before = today.replace(
            year=today.year if today.month > 3 else today.year - 1,
            month=(today.month - 3) if today.month > 3 else (12 - (3 - today.month)),
        )

        defaulters = []

        for sy in student_year_levels:
            fees = StudentFee.objects.filter(student_year=sy)

            # Unpaid for last 3 months
            unpaid_last_3 = fees.filter(
                month__gte=three_months_before.month,
                month__lte=today.month,
                status__in=["pending", "partial"]
            ).exists()

            # Any remaining dues
            has_due = fees.filter(due_amount__gt=0).exists()

            if unpaid_last_3 or has_due:
                defaulters.append(sy)

        # Send email one-by-one (load-friendly)
        for d in defaulters:
            user = d.student.user
            email = user.email
            phone = d.student.contact_number if hasattr(d.student, 'contact_number') else None

            # Build unpaid fee details
            unpaid_fees = StudentFee.objects.filter(
                student_year=d,
                status__in=["pending", "partial"],
                due_amount__gt=0
            )

            # Group fees by month
            month_wise_fees = defaultdict(list)
            total_due = 0

            for fee in unpaid_fees:
                month_name = fee.get_month_display()
                month_wise_fees[month_name].append(fee)
                total_due += fee.due_amount   # sum total

            fee_lines = ""

            for month, fees in month_wise_fees.items():
                fee_lines += f"{month}\n"
                for f in fees:
                    fee_lines += f"- {f.fee_structure.fee_type} : ₹{f.due_amount}\n"
                fee_lines += "\n" 

            fee_lines += f"Total Due Amount : ₹{total_due}\n"

            # Final message
            message = (
                f"Dear {user.first_name},\n\n"
                f"You have pending school fees:\n\n"
                f"{fee_lines}\n"
                f"Please clear your dues as soon as possible.\n\n"
                f"Thank you."
            )

            # Send Email
            if email:
                send_email_notification(email, "Fee Due Notice", message)

            # Send WhatsApp
            if phone:
                send_whatsapp(message, phone)

        return Response(
            {
                "message": "Notifications sent to all defaulters.",
                "defaulters_count": len(defaulters),
            },
            status=status.HTTP_200_OK,
        )


class StudentPromotionViewSet(viewsets.ViewSet):
    @action(detail=False, methods=['post'], url_path='promote')
    def promote(self, request):
        """
        Payload: {
            "student_ids": [1, 2, 3],
            "level_id": 5,
            "year_id": 2
        }
        level_id  = target YearLevel to move students to (promote or demote)
        year_id   = target SchoolYear (session) to assign
        """

        student_ids = request.data.get('student_ids', [])
        level_id = request.data.get('level_id')
        year_id = request.data.get('year_id')

        if not student_ids:
            return Response(
                {"error": "Please provide student_ids."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not level_id or not year_id:
            return Response(
                {"error": "Please provide both level_id and year_id."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate target level and year exist
        try:
            target_level = YearLevel.objects.get(id=level_id)
        except YearLevel.DoesNotExist:
            return Response(
                {"error": f"YearLevel with id {level_id} not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            target_year = SchoolYear.objects.get(id=year_id)
        except SchoolYear.DoesNotExist:
            return Response(
                {"error": f"SchoolYear with id {year_id} not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        results = []

        with transaction.atomic():
            for s_id in student_ids:

                result = {"student_id": s_id}

                # Optional: add student name
                student = Student.objects.filter(id=s_id, is_active=True).first()
                if student:
                    result["student_name"] = str(student)
                else:
                    result.update({
                        "status": "failed",
                        "reason": "Student not found"
                    })
                    results.append(result)
                    continue

                # 1. Get latest enrollment (SYL)
                current_enrollment = StudentYearLevel.objects.filter(
                    student_id=s_id
                ).order_by('-year__start_date').first()

                if not current_enrollment:
                    result.update({
                        "status": "failed",
                        "reason": "No enrollment found"
                    })
                    results.append(result)
                    continue

                # 2. Check if student already has an enrollment in the target year
                existing_enrollment = StudentYearLevel.objects.filter(
                    student_id=s_id,
                    year=target_year
                ).first()

                if existing_enrollment:
                    # Already in the exact same level and year — skip
                    if existing_enrollment.level_id == target_level.id:
                        result.update({
                            "status": "failed",
                            "reason": f"Student is already in {target_level.level_name} for session {target_year.year_name}"
                        })
                        results.append(result)
                        continue

                    # Update the existing enrollment's level (class change within same session)
                    old_level_name = existing_enrollment.level.level_name
                    existing_enrollment.level = target_level
                    existing_enrollment.save()

                    result.update({
                        "status": "success",
                        "reason": "Class updated in existing session",
                        "from_level": old_level_name,
                        "from_year": target_year.year_name,
                        "to_level": target_level.level_name,
                        "to_year": target_year.year_name,
                        "new_year_id": target_year.id,
                        "new_level_id": target_level.id
                    })
                    results.append(result)
                    continue

                # 3. Create new enrollment with the chosen level and year
                StudentYearLevel.objects.create(
                    student_id=s_id,
                    year=target_year,
                    level=target_level,
                    house=current_enrollment.house
                )

                result.update({
                    "status": "success",
                    "reason": "Moved successfully",
                    "from_level": current_enrollment.level.level_name,
                    "from_year": current_enrollment.year.year_name,
                    "to_level": target_level.level_name,
                    "to_year": target_year.year_name,
                    "new_year_id": target_year.id,
                    "new_level_id": target_level.id
                })

                results.append(result)

        # Summary
        success_count = sum(1 for r in results if r["status"] == "success")
        fail_count = len(results) - success_count

        return Response({
            "message": "Promotion process completed.",
            "results": results,
            "summary": {
                "total": len(results),
                "promoted": success_count,
                "failed": fail_count
            }
        }, status=status.HTTP_200_OK)
