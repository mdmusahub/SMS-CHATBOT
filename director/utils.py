

# ***********************************2222**************************


# from django.db import models
# import os
# def Document_folder(instance, filename):
#     base_path = "Document_folder"

#     if instance.document and instance.document.student:
#         user = instance.document.student.user
#         year_level = (
#             instance.document.student.studentyearlevel_set.first().level.level_name
#             if instance.document.student.studentyearlevel_set.exists()
#             else "unknown_level"
#         )
#         folder_path = f"student/{year_level}/{user.first_name}_{user.last_name}"

#     elif instance.document and instance.document.teacher:
#         user = instance.document.teacher.user
#         folder_path = f"teacher/{user.first_name}_{user.last_name}"

#     elif instance.document and instance.document.guardian:
#         user = instance.document.guardian.user
#         folder_path = f"guardian/{user.first_name}_{user.last_name}"

#     elif instance.document and instance.document.office_staff:
#         user = instance.document.office_staff.user
#         folder_path = f"office_staff/{user.first_name}_{user.last_name}"

#     else:
#         folder_path = "unknown"

#     # Debugging print statements
#     print(f"DEBUG: ROLE DETECTED: {folder_path.split('/')[0]}")
#     print(f"DEBUG: FULL FOLDER PATH: {os.path.join(base_path, folder_path)}")
#     print(f"DEBUG: FILE PATH: {os.path.join(base_path, folder_path, filename)}")

#     return os.path.join(base_path, folder_path, filename)

#### commented as of 19 june25 at 11:11 PM till here










#### added as of 19 june25 at 11:11 PM from here

# import os

# def Document_folder(instance, filename):
#     try:
#         document = instance.document  # access the FK to Document
#     except Exception as e:
#         print(" No document attached to file:", e)
#         return f"Document_folder/unknown/{filename}"

#     base_path = "Document_folder"


#     if document.student:
#         user = document.student.user
#         year_level = (
#             document.student.studentyearlevel_set.first().level.level_name
#             if document.student.studentyearlevel_set.exists()
#             else "unknown_level"
#         )
#         folder_path = f"student/{year_level}/{user.first_name}_{user.last_name}"
#     elif document.teacher:
#         user = document.teacher.user
#         folder_path = f"teacher/{user.first_name}_{user.last_name}"
#     elif document.guardian:
#         user = document.guardian.user
#         folder_path = f"guardian/{user.first_name}_{user.last_name}"
#     elif document.office_staff:
#         user = document.office_staff.user
#         folder_path = f"office_staff/{user.first_name}_{user.last_name}"
#     else:
#         folder_path = "unknown"

#     return os.path.join(base_path, folder_path, filename)


import hashlib
import hmac
import json
from twilio.rest import Client 
import os
from datetime import datetime

def Document_folder(instance, filename):
    try:
        document = instance.document  # access the FK to Document
    except Exception as e:
        print(" No document attached to file:", e)
        return f"Document_folder/unknown/{filename}"

    base_path = "Document_folder"

    if document.student:
        user = document.student.user
        year_level = (
            document.student.student_year_levels.first().level.level_name
            if document.student.student_year_levels.exists()
            else "unknown_level"
        )
        folder_path = f"student/{year_level}/{user.first_name}_{user.last_name}"
    elif document.teacher:
        user = document.teacher.user
        folder_path = f"teacher/{user.first_name}_{user.last_name}"
    elif document.guardian:
        user = document.guardian.user
        folder_path = f"guardian/{user.first_name}_{user.last_name}"
    elif document.office_staff:
        user = document.office_staff.user
        folder_path = f"office_staff/{user.first_name}_{user.last_name}"
    else:
        folder_path = "unknown"

    return os.path.join(base_path, folder_path, filename)


# ---------------------- Exam Paper
def clean_name(name):
    if not name:
        return "unknown"
    return name.replace("\xa0", "_").replace(" ", "_")


def ExamPaper_folder(instance, filename):
    try:
        paper = instance  
        teacher = paper.teacher.user
        teacher_name = f"{teacher.first_name}_{teacher.last_name}"
    except Exception as e:
        print("Error accessing teacher:", e)
        teacher_name = "unknown_teacher"

    try:
        # class_name = paper.exam.year_level.level_name
        class_name = paper.year_level.level_name

    except Exception as e:
        print("Error accessing class name:", e)
        class_name = "unknown_class"

    try:
        subject_name = paper.subject.subject_name
        school_year = paper.term.year.year_name
        exam_type = paper.exam_type.name

        new_filename = f"{subject_name}-{school_year}-{exam_type}{os.path.splitext(filename)[1]}"
    except Exception as e:
        print("Error building file name:", e)
        new_filename = filename

    folder_path = os.path.join("ExamPaper_folder", teacher_name, class_name)
    full_path = os.path.join(folder_path, new_filename)

    print("file path:", full_path)  
    return full_path

# ------------------ File Download's
from django.http import FileResponse
from rest_framework.response import Response

def get_file_response(file_field, file_label="file"):
    if file_field and hasattr(file_field, "path") and os.path.exists(file_field.path):
        response = FileResponse(open(file_field.path, 'rb'))
        response["Content-Disposition"] = f'attachment; filename="{os.path.basename(file_field.name)}"'
        return response
    return Response({"error": f"{file_label} not found."}, status=404)



#------------------------------------------REPORTCARD Util----------------------------------------------------
from collections import defaultdict
from .models import *

def calculate_subject_summary(subjects_data):
    required_exams = {"sa1", "sa2"}
    subject_marks = defaultdict(dict)  # subject -> {exam_type: mark}

    # Collect marks
    for exam in subjects_data:
        exam_type = exam.get("exam_type", "").lower()
        if exam_type not in required_exams:
            continue

        for subject, mark in exam.get("subjects", {}).items():
            try:
                subject_marks[subject][exam_type] = float(mark)
            except (TypeError, ValueError):
                continue

    # Validate missing exam types per subject
    missing_data = {
        subject: list(required_exams - marks.keys())
        for subject, marks in subject_marks.items()
        if required_exams - marks.keys()
    }

    if missing_data:
        return {
            "subject_avg": {
                "error": "Some subjects are missing marks for required exams.",
                "missing_exam_data": {
                    subject: [x.upper() for x in exams]
                    for subject, exams in missing_data.items()
                }
            },
            "total_marks": 0,
            "max_marks": 0,
            "percentage": 0,
            "grade": "F",
            "supplementary_in": []
        }

    if not subject_marks:
        return {
            "subject_avg": {
                "error": "SA1&SA2 Missing"
            },
            "total_marks": 0,
            "max_marks": 0,
            "percentage": 0,
            "grade": "F",
            "supplementary_in": []
        }

    # Calculate per-subject percent
    subject_avg = {}
    supplementary_in = []
    
    for subject, exams in subject_marks.items():
        sa1 = exams.get("sa1", 0)
        sa2 = exams.get("sa2", 0)
        obtained = sa1 + sa2

        # Scale: max combined SA1+SA2 is 200 → scale to 100
        percent = round((obtained / 200) * 100, 2)
        subject_avg[subject] = round(obtained / 2, 2)  # still averaging for display

        if percent < 40:
            supplementary_in.append(subject)

    # Final totals
    total_obtained = sum(subject_avg.values())
    subject_count = len(subject_avg)
    total_possible = subject_count * 100
    percentage = round((total_obtained / total_possible) * 100, 2) if total_possible else 0

    # Grade logic
    if percentage >= 90:
        grade = "A++"
    elif percentage >= 80:
        grade = "A+"
    elif percentage >= 70:
        grade = "A"
    elif percentage >= 60:
        grade = "B"
    elif percentage >= 50:
        grade = "C"
    elif percentage >= 40:
        grade = "D"
    else:
        grade = "F"

    return {
        "subject_avg": subject_avg,
        "total_marks": total_obtained,
        "max_marks": total_possible,
        "percentage": percentage,
        "grade": grade,
        "supplementary_in": supplementary_in
    }


# ---------------------  Income and Expense 

def income_attachments(instance, filename):
    category_name = instance.category.name.replace(" ", "_").lower()
    return os.path.join(
        "income_attachments",
        str(datetime.now().year),               
        str(datetime.now().month).zfill(2),       
        f"{category_name}_{filename}"  
        )


def expense_attachments(instance, filename):
    category_name = instance.category.name.replace(" ", "_").lower()
    year = instance.school_year.start_date.year if instance.school_year else datetime.now().year
    # month = instance.expense_date.month if instance.expense_date else datetime.now().month
    month_name = instance.expense_date.strftime("%B") if instance.expense_date else datetime.now().strftime("%B")

    return os.path.join(
        "expense_attachments",
        str(year),
        month_name,  
        f"{category_name}_{filename}"
    )

from django.core.mail import send_mail
from django.conf import settings

def send_email_notification(to_email, subject, message):
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to_email],
        fail_silently=False,
    )
    

def normalize_phone(num):
    num = str(num).strip()

    # remove spaces and weird chars
    num = num.replace(" ", "").replace("-", "")

    # ensure it starts with +91 only once
    if num.startswith("0"):
        num = num[1:]   # remove leading 0

    if not num.startswith("+91"):
        num = "+91" + num

    return num

def send_whatsapp(message_text, phone_number):
    client = Client(
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN
    )

    try:
        phone = normalize_phone(phone_number)

        msg = client.messages.create(
            from_=settings.TWILIO_WHATSAPP_NUMBER,
            body=message_text,
            to=f"whatsapp:{phone}"
        )
        return {"number": phone, "status": "sent", "sid": msg.sid}

    except Exception as e:
        print("WhatsApp Error:", str(e))
        return {"number": phone, "status": "failed", "error": str(e)}
    
# ---------------------------------- Fee Due Year Utility --------------------------------------------
from datetime import date
from decimal import Decimal
from django.utils import timezone

def get_fee_due_year(school_year, month):
    # Session runs July–June, e.g. July2026–June2027
    # Jul–Dec → start_date.year, Jan–Jun → end_date.year
    if month >= 7:
        return int(school_year.start_date.year)
    return int(school_year.end_date.year)

# def calculate_penalty(fee_type, school_year, month):
#     if fee_type.lower() != "tuition fee":
#         return Decimal("0.00")

#     today = timezone.now().date()

#     # decide correct year for the month
#     due_year = get_fee_due_year(school_year, month)
#     due_date = date(due_year, month, 15)

#     if today > due_date:
#         return Decimal("25.00")

#     return Decimal("0.00")


def hmac_digest(msg, key_string):
    # Encode the key and message as bytes
    key = key_string.encode('utf-8')
    msg_bytes = msg.encode('ascii')
    
    # Create an HMAC object with the SHA-256 algorithm
    mac = hmac.new(key, msg_bytes, hashlib.sha256)
    
    # Return the hexadecimal digest
    return mac.hexdigest()


def icici_normalize_amount(amount):
    try:
        dec = Decimal(str(amount))
    except Exception:
        dec = Decimal("0.00")
    return f"{dec:.2f}"


def icici_generate_merchant_txn_no(seed, prefix="F", max_len=20):
    """
    ICICI merchantTxnNo:
    - Alphanumeric
    - Max length per spec (default 20)
    """
    digest = hashlib.sha256(str(seed).encode("utf-8")).hexdigest().upper()
    if not prefix:
        return digest[:max_len]

    keep = max_len - len(prefix)
    if keep <= 0:
        return digest[:max_len]
    return f"{prefix}{digest[:keep]}"


def icici_secure_hash_v1(params, key_string):
    """
    Hash calculation (v1):
    - Sort parameter names ascending
    - Concatenate values
    - Exclude null/empty and secureHash itself
    """
    items = []
    for k, v in params.items():
        if k == "secureHash":
            continue
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            if not v:
                continue
            v = v[0]
        v_str = str(v)
        if v_str == "":
            continue
        items.append((k, v_str))

    items.sort(key=lambda kv: kv[0])
    concat = "".join(v for _, v in items)
    return hmac_digest(concat, key_string)


def icici_secure_hash_v2(payload, key_string):
    """
    Hash calculation (v2):
    - Minified JSON string of request/response
    - HMAC SHA256
    - Hex lowercase
    """
    json_str = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    key = key_string.encode("utf-8")
    msg_bytes = json_str.encode("utf-8")
    mac = hmac.new(key, msg_bytes, hashlib.sha256)
    return mac.hexdigest()


'''------------------------------------Transfer Certificates Template--------------------------------------------'''
"""
POST /d/GenerateTC/

Accepts the filled Transfer Certificate form fields (from the frontend modal),
renders them into a PDF that visually matches your physical TC layout, 
and returns that PDF directly in the response.

The frontend does NOT need to save this anywhere separately — it just
takes the returned PDF blob and attaches it as `files` in the existing
POST /d/Document/ call, alongside:
    document_types = <id of "Transfer Certificate" type>
    identities     = tc_no
    student        = <student id>

So this endpoint only generates the file. Existing DocumentView
handles the actual save — nothing there needs to change.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from student.models import Student, StudentYearLevel

REQUIRED_FIELDS = ['tc_no', 'scholar_no', 'student_name', 'date_of_birth', 'from_date', 'to_date']

# Maps our TC field name -> the exact DocumentType.name used as a fallback
# source when the Student model field itself is empty.
DOCUMENT_TYPE_FALLBACKS = {
    'aadhaar_no': 'Aadhaar Number',
    'apaar_id': 'Apaar ID',
    'fmid': 'Family ID',
    'pen_no': 'PEN Number',
    'sssm_id': 'SSSM ID',
}


def _prefill_from_student(student_id, data):
    """
    Fill in anything the frontend didn't send, using the Student record.
    Anything the frontend already sent (user edited it) takes priority.
    """
    from .models import Admission

    if not student_id:
        return data

    student = Student.objects.filter(id=student_id, is_active=True).select_related('user').first()
    if not student:
        return data
    
    student_year = (
        StudentYearLevel.objects.filter(student_id=student_id)
        .select_related("level", "year")
        .order_by("-id")
        .first()
    )
    admission = Admission.objects.filter(student=student_year.student).first()

    defaults = {
        'student_name': f"{student.user.first_name} {student.user.last_name}".strip(),
        'father_name': student.father_name,
        'mother_name': student.mother_name,
        'date_of_birth': student.date_of_birth.strftime('%d-%m-%Y') if student.date_of_birth else '',
        "year_level": student_year.level.level_name if student_year and student_year.level else "",
        "school_year": student_year.year.year_name if student_year and student_year.year else "",
        'scholar_no': student.scholar_number,
        'aadhaar_no': student.aadhaar_number,
        'fmid': student.FMID_number,
        'apaar_id': student.apaar_number,
        'pen_no': student.PEN_number,
        'admission_date': admission.admission_date,
    }

    for key, val in defaults.items():
        if not data.get(key) and val:
            data[key] = val

    return data


def _prefill_from_documents(student_id, data):
    """
    Backup source, used only for whatever is STILL missing after the
    Student model pass — e.g. the Student record never had `aadhaar_number`
    filled in, but a parent uploaded an "Aadhaar Number" document earlier,
    and that document's `identities` value holds the actual number.
    """
    from .models import Document
    if not student_id:
        return data

    still_missing = [f for f in DOCUMENT_TYPE_FALLBACKS if not data.get(f)]
    if not still_missing:
        return data

    type_names = [DOCUMENT_TYPE_FALLBACKS[f] for f in still_missing]

    docs = (
        Document.objects.filter(
            student_id=student_id,
            document_types__name__in=type_names,
            is_active=True,
        )
        .prefetch_related('document_types')
        .distinct()
    )

    # Build type_name -> identity value, in case a student has multiple docs
    by_type = {}
    for doc in docs:
        if not doc.identities:
            continue
        for dt in doc.document_types.all():
            if dt.name in type_names and dt.name not in by_type:
                # identities can be a comma-joined string if multiple were
                # submitted together — take the first meaningful value
                by_type[dt.name] = doc.identities.split(',')[0].strip()

    for field in still_missing:
        type_name = DOCUMENT_TYPE_FALLBACKS[field]
        if type_name in by_type:
            data[field] = by_type[type_name]

    return data

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_transfer_certificate_data(request):
    student_id = request.query_params.get("student_id")

    if not student_id:
        return Response(
            {"error": "student_id is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    student = Student.objects.filter(id=student_id).first()
    if not student:
        return Response(
            {"error": "Student not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    data = {"student_id": student_id}

    # 1. Fill from Student model
    data = _prefill_from_student(student_id, data)

    # 2. Fill remaining missing fields from Document
    data = _prefill_from_documents(student_id, data)

    return Response(data, status=status.HTTP_200_OK)


def _calculate_student_totals(syl, year_level_fees, discounts_by_syl_fee,
                               paid_fees_by_syl_fee_month, ACADEMIC_MONTHS,
                               MONTHLY_FEE_TYPES, stream_filter):
    """
    Computes yearly_fees_total and received_fees_total for one student,
    given a specific tuition stream filter (or None = no filtering needed).
    """
    yearly_fees_total = Decimal('0.00')
    received_fees_total = Decimal('0.00')

    for fee in year_level_fees:
        if fee.fee_type == 'Tuition Fee' and fee.tuition_sub_type and fee.tuition_sub_type != 'General':
            if stream_filter and fee.tuition_sub_type != stream_filter:
                continue

        is_monthly = fee.fee_type.lower() in MONTHLY_FEE_TYPES

        discount_total = discounts_by_syl_fee.get((syl.id, fee.id), Decimal('0.00'))
        base_amount = max(Decimal(fee.fee_amount) - discount_total, Decimal('0.00'))

        if is_monthly:
            yearly_fees_total += base_amount * len(ACADEMIC_MONTHS)
            for month_number in ACADEMIC_MONTHS:
                received_fees_total += paid_fees_by_syl_fee_month.get(
                    (syl.id, fee.id, month_number), Decimal('0.00')
                )
        else:
            yearly_fees_total += base_amount
            received_fees_total += paid_fees_by_syl_fee_month.get(
                (syl.id, fee.id, None), Decimal('0.00')
            )

    return yearly_fees_total, received_fees_total