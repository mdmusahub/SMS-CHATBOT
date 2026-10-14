import random
import string
import uuid
from django.db import models

from authentication.models import User

# from authentication.models import User
from student.models import *
from director.utils import * 
from .utils import * 

from teacher.models import * 
from django.utils.timezone import now
import calendar




class Role(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Role"
        verbose_name_plural = "Roles"
        db_table = "Role"


class Country(models.Model):
    name = models.CharField(max_length=120)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Country"
        verbose_name_plural = "Countries"
        db_table = "Country"


class State(models.Model):
    name = models.CharField(max_length=120)
    country = models.ForeignKey(Country, on_delete=models.DO_NOTHING)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "State"
        verbose_name_plural = "States"
        db_table = "State"


class City(models.Model):
    name = models.CharField(max_length=120)
    state = models.ForeignKey(State, on_delete=models.DO_NOTHING)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "City"
        verbose_name_plural = "Cities"
        db_table = "City"

class AddressManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)
    
    def all_including_inactive(self):
        return super().get_queryset()
    
class Address(models.Model):
    user = models.ForeignKey("authentication.User", on_delete=models.DO_NOTHING)
    house_no = models.CharField(max_length=100,null=True, blank=True)
    habitation = models.CharField(max_length=100,null=True, blank=True)
    ward_no = models.IntegerField(null=True, blank=True)
    zone_no = models.IntegerField(null=True, blank=True)
    block = models.CharField(max_length=100,null=True, blank=True)
    district = models.CharField(max_length=100,null=True, blank=True)
    division = models.CharField(max_length=100,null=True, blank=True)
    area_code = models.IntegerField(null=True, blank=True)
    country = models.ForeignKey(Country, on_delete=models.DO_NOTHING)
    state = models.ForeignKey(State, on_delete=models.DO_NOTHING)
    city = models.ForeignKey(City, on_delete=models.DO_NOTHING)
    address_line = models.CharField(max_length=250,null=True, blank=True)
    is_active = models.BooleanField(default=True)

    objects = AddressManager()

    def __str__(self):
        return f"{self.user} - {self.address_line}"

    class Meta:
        verbose_name = "Address"
        verbose_name_plural = "Addresses"
        db_table = "Address"
        indexes = [models.Index(fields=['is_active'])]

class DirectorManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)
    
    def all_including_inactive(self):
        return super().get_queryset()
    
class Director(models.Model):
    user = models.OneToOneField("authentication.User", on_delete=models.SET_NULL,null=True)
    phone_no = models.CharField(max_length=15, null=True, blank=True)
    gender = models.CharField(max_length=10,null=True, blank=True)
    is_active = models.BooleanField(default=True)

    objects = DirectorManager()

    def __str__(self):
        return str(self.user)

    class Meta:
        verbose_name = "Director"
        verbose_name_plural = "Directors"
        db_table = "Director"
        indexes = [models.Index(fields=['is_active'])]

class BankingDetailsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)
    
    def all_including_inactive(self):
        return super().get_queryset()

class BankName(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Bank Name"
        verbose_name_plural = "Bank Names"
        db_table = "BankName"
    
class BankingDetail(models.Model):
    account_no = models.BigIntegerField(null=True, blank=True)   # was NOT NULL → caused your IntegrityError
    ifsc_code = models.CharField(max_length=225, null=True, blank=True)
    holder_name = models.CharField(max_length=255, null=True, blank=True)
    user = models.OneToOneField("authentication.User", on_delete=models.DO_NOTHING)
    is_active = models.BooleanField(default=True)
    bank_name = models.ForeignKey(BankName, on_delete=models.DO_NOTHING, null=True, blank=True)

    objects = BankingDetailsManager()

    def __str__(self):
        return f"{self.holder_name} ({self.account_no})"

    class Meta:
        verbose_name = "Banking Detail"
        verbose_name_plural = "Banking Details"
        db_table = "BankingDetail"
        indexes = [models.Index(fields=['is_active'])]
        

class SchoolYear(models.Model):
    year_name = models.CharField(max_length=250)
    start_date = models.DateField(null=False)
    end_date = models.DateField(null=False)

    def __str__(self):
        return self.year_name

    class Meta:
        verbose_name = "School Year"
        verbose_name_plural = "School Years"
        db_table = "SchoolYear"


# 


class Term(models.Model):
    year = models.ForeignKey(SchoolYear, on_delete=models.DO_NOTHING)
    term_number = models.IntegerField()
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return f"{self.year} - Term {self.term_number}"

    class Meta:
        verbose_name = "Term"
        verbose_name_plural = "Terms"
        db_table = "Term"


class Period(models.Model):
    year = models.ForeignKey(SchoolYear, on_delete=models.DO_NOTHING)
    name = models.CharField(max_length=250)
    start_period_time = models.TimeField()
    end_period_time = models.TimeField()

    def __str__(self):
        return f"{self.start_period_time} - {self.end_period_time} - {self.name}"

    # def __str__(self):
    #     return f"{self.year} - {self.name}"
    class Meta:
        verbose_name = "Period"
        verbose_name_plural = "Periods"
        db_table = "Period"


class Department(models.Model):
    department_name = models.CharField(max_length=250, null=False)

    def __str__(self):
        return self.department_name

    class Meta:
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        db_table = "Department"


class Subject(models.Model):
    department = models.ForeignKey(Department, on_delete=models.DO_NOTHING)
    subject_name = models.CharField(max_length=250, null=False)
    year_levels = models.ManyToManyField("YearLevel", related_name="subjects")

    def __str__(self):
        return f"{self.department} - {self.subject_name}"

    class Meta:
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"
        db_table = "Subject"


class ClassRoomType(models.Model):
    name = models.CharField(max_length=250, null=False)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Class Room Type"
        verbose_name_plural = "Class Room Types"
        db_table = "ClassRoomType"


class ClassRoom(models.Model):
    room_type = models.ForeignKey(ClassRoomType, on_delete=models.DO_NOTHING)
    room_name = models.CharField(max_length=200)
    capacity = models.IntegerField()

    def __str__(self):
        return f"{self.room_type} - {self.room_name}"

    class Meta:
        verbose_name = "Class Room"
        verbose_name_plural = "Class Rooms"
        db_table = "ClassRoom"


class ClassPeriod(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.DO_NOTHING)

    year_level = models.ForeignKey("YearLevel", on_delete=models.DO_NOTHING)
    teacher = models.ForeignKey("teacher.Teacher", on_delete=models.DO_NOTHING, related_name="assigned_periods", null=True, blank=True)
    term = models.ForeignKey(Term, on_delete=models.DO_NOTHING)
    start_time = models.ForeignKey(
        Period, on_delete=models.DO_NOTHING, related_name="start_time"
    )  
    end_time = models.ForeignKey(
        Period, on_delete=models.DO_NOTHING, related_name="end_time"
    )
    classroom = models.ForeignKey(ClassRoom, on_delete=models.DO_NOTHING)
    name = models.CharField(max_length=250)
   


    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "ClassPeriod"
        verbose_name_plural = "ClassPeriods"
        db_table = "ClassPeriod"



class AdmissionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)
    
    def all_including_inactive(self):
        return super().get_queryset()

class Admission(models.Model):
    enrollment_no = models.CharField(max_length=20, blank=True, null=True)
    student = models.ForeignKey(Student, on_delete=models.DO_NOTHING)
    admission_date = models.DateField(auto_now_add=True)
    previous_school_name = models.CharField(max_length=100, blank=True, null=True)
    previous_standard_studied = models.CharField(max_length=15, blank=True, null=True)
    tc_letter = models.CharField(max_length=80, blank=True, null=True)
    guardian = models.ForeignKey(Guardian, on_delete=models.DO_NOTHING, null=True, blank=True)
    year_level = models.ForeignKey('YearLevel', on_delete=models.SET_NULL, null=True, blank=True)
    school_year = models.ForeignKey(SchoolYear, on_delete=models.DO_NOTHING)
    is_rte = models.BooleanField(default=False)
    rte_number = models.CharField(max_length=50, blank=True, null=True)
    emergency_contact_no = models.CharField(max_length=100, blank=True, null=True)
    entire_road_distance_from_home_to_school = models.CharField(max_length=100, blank=True, null=True)
    obtain_marks = models.FloatField(blank=True, null=True)
    total_marks = models.FloatField(blank=True, null=True)
    previous_percentage = models.FloatField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    class_section = models.CharField(max_length=15, null=True, blank=True)
    # department = models.ForeignKey(Department, on_delete=models.DO_NOTHING, null=True, blank=True)

    objects = AdmissionManager()

    def save(self, *args, **kwargs):
        # Guard against None before dividing
        if self.obtain_marks is not None and self.total_marks and self.total_marks > 0:
            self.previous_percentage = round((self.obtain_marks / self.total_marks) * 100, 2)
        else:
            self.previous_percentage = None   # null is cleaner than 0 when marks are absent
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Admission of {self.student} (Guardian: {self.guardian}) - YearLevel: {self.year_level if self.year_level else 'None'}"

    class Meta:
        db_table = "Admission"
        indexes = [models.Index(fields=['is_active'])]


from django.db import models
import random
import string
from django.conf import settings
from django.utils import timezone


class MasterFee(models.Model):
    PAYMENT_CHOICES = (
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("yearly", "Yearly"),
        ("Others","Others")
    )
    payment_structure = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default="monthly")

    class Meta:
        db_table = "MasterFee"

    def __str__(self):
        return f"{self.payment_structure}"
   



class YearLevel(models.Model):
    level_name = models.CharField(max_length=250)
    level_order = models.IntegerField()
    fee = models.ForeignKey(MasterFee, on_delete=models.PROTECT,related_name="year_levels",null=True, blank=True)

    def __str__(self):
        return f"{self.level_name}"


    class Meta:
        verbose_name = "Year Level"
        verbose_name_plural = "Year Levels"
        db_table = "YearLevel"

class FeeRecordManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)
    
    def all_including_inactive(self):
        return super().get_queryset()
    

FEE_TYPE_CHOICES =  [
        ('Admission Fee', 'Admission Fee'),
        ('Exam Fee', 'Exam Fee'),
        ('Tuition Fee', 'Tuition Fee'),
        ('Activity Fee', 'Activity Fee'),
        ('Caution Fee', 'Caution Fee'),
        ('Maintenance', 'Maintenance'),
        ('Form Fee', 'Form Fee'),
        ('Others', 'Others'),
    ]

TUITION_SUB_TYPE = [
        ('General', 'General'),
        ('Comm/Arts', 'Comm / Arts'),
        ('PCM/PCB', 'PCM / PCB'),
    ]

class FeeStructure(models.Model):
    school_year = models.ForeignKey(SchoolYear, on_delete=models.PROTECT, related_name="fee_structures")
    master_fee = models.ForeignKey(MasterFee, on_delete=models.CASCADE, related_name="fee_structures")
    fee_type = models.CharField(max_length=100, choices=FEE_TYPE_CHOICES)
    tuition_sub_type = models.CharField(
        max_length=50,
        choices=TUITION_SUB_TYPE,
        null=True,
        blank=True,
        help_text="Only applicable when fee_type is 'Tuition Fee'"
    )
    fee_amount = models.DecimalField(max_digits=10,decimal_places=2)
    year_level = models.ManyToManyField("YearLevel", related_name="fee_structures")

    class Meta:
        db_table = "fee_structure"

    def is_tuition_fee(self):
        return self.fee_type == 'Tuition Fee'

    def display_name(self):
        if self.is_tuition_fee() and self.tuition_sub_type:
            return f"Tuition Fee ({self.tuition_sub_type})"
        return self.fee_type

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.fee_type == 'Tuition Fee' and not self.tuition_sub_type:
            raise ValidationError("Tuition Fee requires a sub-type (General / Comm/Arts / PCM/PCB).")
        if self.fee_type != 'Tuition Fee' and self.tuition_sub_type:
            raise ValidationError("Sub-type is only valid for Tuition Fee.")

    def __str__(self):
        year_levels = ", ".join(
            self.year_level.values_list("level_name", flat=True)
        )
        return (
            f"{self.school_year.year_name} | "
            f"{year_levels} | "
            f"{self.display_name()} | ₹{self.fee_amount}"
        )


class AppliedFeeDiscount(models.Model):
    # student_fee = models.ForeignKey(StudentFee, on_delete=models.CASCADE, related_name="discounts")#
    student = models.ForeignKey("student.StudentYearLevel", on_delete=models.CASCADE, related_name="discounts")
    fee_type = models.ForeignKey(FeeStructure,on_delete=models.CASCADE)
    discount_name = models.CharField(max_length=100)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "applied_fee_discount"

    def __str__(self):
        return f"{self.discount_name} - {self.discount_amount} - {self.student.student.user.first_name}"

class StudentFee(models.Model):
    student_year = models.ForeignKey("student.StudentYearLevel", on_delete=models.CASCADE, related_name="student_fees")
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.PROTECT, related_name="student_fees")
    month = models.PositiveSmallIntegerField(choices=[(i, calendar.month_name[i]) for i in range(1, 13)],null=True, blank=True)
    school_year = models.ForeignKey(SchoolYear,on_delete=models.CASCADE)
    due_date = models.DateField(null=True, blank=True)
    original_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    applied_discount = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'),('partial', 'Partial'),('paid', 'Paid'),], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    receipt_number = models.CharField(max_length=50, editable=False, blank=True, auto_created=True)

    def __str__(self):
        return f"{self.student_year.student.user.first_name} - {self.fee_structure.fee_type} - paid amount {self.paid_amount} - due amount {self.due_amount} - {self.status}  - {self.school_year.year_name}  - month {self.month}"

    class Meta:
        db_table = "student_fee"
        unique_together = ['student_year', 'fee_structure', 'month', 'school_year']


class FeePayment(models.Model):
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('online', 'Online'),
        ('cheque', 'Cheque'),
        ('qr payment', 'QR Payment')
    ]

    student_fee = models.ForeignKey(StudentFee, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHODS)
    status = models.CharField(max_length=50, choices=PAYMENT_STATUS, default='pending')
    payment_date = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey("authentication.User", on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    receipt_number = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    cheque_number = models.CharField(max_length=50, blank=True, null=True)#, unique=True)
    icici_merchant_txn_no = models.CharField(max_length=50,null=True,blank=True)
    icici_txn_id = models.CharField(max_length=50, null=True, blank=True)
    icici_payment_id = models.CharField(max_length=50, null=True, blank=True)
    icici_status_code = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = "fee_payment"

    def __str__(self):
        return f"Payment #{self.id} - ₹{self.amount} - {self.payment_method} - {self.student_fee.student_year.student.user.first_name} {self.student_fee.student_year.student.user.last_name}"
    

class OfficeStaffManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)
    
    def all_including_inactive(self):
        return super().get_queryset()

class OfficeStaff(models.Model):
    user = models.OneToOneField("authentication.User", on_delete=models.SET_NULL, null=True)
    phone_no = models.CharField(max_length=15,null=True, blank=True)
    gender = models.CharField(max_length=10,null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    joining_date = models.DateField(auto_now_add=True)
    student = models.ManyToManyField("student.Student", blank=True, related_name="managed_by_staff")
    teacher = models.ManyToManyField("teacher.Teacher", blank=True, related_name="managed_by_staff")
    admissions = models.ManyToManyField(Admission, blank=True, related_name="handled_by_staff")
    is_active = models.BooleanField(default=True)
    adhaar_no = models.BigIntegerField(null=True,blank=True,unique=True)    # added as of 09Sep25
    pan_no = models.CharField(max_length=20,null=True,blank=True,unique=True)   # added as of 09Sep25
    qualification = models.CharField(max_length=250,null=True,blank=True)

    objects = OfficeStaffManager()

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.department})"

    class Meta:
        verbose_name = "Office Staff"
        verbose_name_plural = "Office Staff"
        db_table = "OfficeStaff"
        indexes = [models.Index(fields=['is_active'])]
        
        

class DocumentType(models.Model):
    name = models.CharField(max_length=100)
    

    def __str__(self):
        return self.name

    class Meta:
        db_table = "DocumentType"
        
        
class DocumentManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)
    
    def all_including_inactive(self):
        return super().get_queryset()        

class Document(models.Model):
    document_types = models.ManyToManyField(DocumentType)
    identities = models.CharField(max_length=200, blank=True, null=True)#, unique=True)
    
    student = models.ForeignKey("student.Student", on_delete=models.SET_NULL, null=True, blank=True)
    teacher = models.ForeignKey("teacher.Teacher", on_delete=models.SET_NULL, null=True, blank=True)
    guardian = models.ForeignKey("student.Guardian", on_delete=models.SET_NULL, null=True, blank=True)
    office_staff = models.ForeignKey(OfficeStaff, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)  

    objects = DocumentManager()
        
    def __str__(self):
        entity = self.student or self.teacher or self.guardian or self.office_staff
        doc_types = ", ".join([dt.name for dt in self.document_types.all()]) if self.document_types.exists() else "NoType"
        return f"{doc_types} - {entity}"

    class Meta:
        db_table = "Document"
        indexes = [models.Index(fields=['is_active'])]
        
class File(models.Model):
    file = models.FileField(upload_to=Document_folder) 
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='files', null=True)

    def __str__(self):
        return f"File {self.id} - {self.file.name}"

    class Meta:
        db_table = "File"

    

# -----------------------Exam module


class ExamType(models.Model):
    name = models.CharField(max_length=100, unique=True)#

    def __str__(self):
        return self.name


class ExamPaper(models.Model):
    exam_type = models.ForeignKey(ExamType,on_delete=models.CASCADE)#
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)#
    year_level = models.ForeignKey(YearLevel,on_delete=models.CASCADE)
    total_marks = models.DecimalField(max_digits=5, decimal_places=2)#
    paper_code = models.CharField(max_length=7,unique=True)#
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True)#
    uploaded_file = models.FileField(upload_to=ExamPaper_folder, blank=True, null=True)#

    class Meta:
        unique_together = ['exam_type', 'subject', 'year_level','term']
    

    def __str__(self):
        return f"{self.year_level} - {self.subject.subject_name} ({self.total_marks})"


class ExamSchedule(models.Model):
    class_name = models.ForeignKey(YearLevel,on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    exam_type = models.ForeignKey(ExamType,on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject,on_delete=models.CASCADE)
    exam_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        unique_together = ['class_name', 'term', 'exam_type', 'subject']
    
    def __str__(self):
        return f"{self.class_name} - {self.subject} ({self.exam_date})"


class StudentMarks(models.Model):
    exam_type = models.ForeignKey(ExamType,on_delete=models.CASCADE)#FA1
    subject = models.ForeignKey(Subject,on_delete=models.CASCADE)
    term = models.ForeignKey(Term,on_delete=models.CASCADE)#school year
    student = models.ForeignKey(StudentYearLevel,on_delete=models.CASCADE)#student aor class name
    teacher = models.ForeignKey(Teacher,on_delete=models.CASCADE)#teacher name
    marks_obtained = models.DecimalField(max_digits=5, decimal_places=2)
    
    class Meta:
        unique_together = ['student', 'exam_type', 'term','subject']

    def __str__(self):
        return f"{self.student} - {self.exam_type.name} - {self.subject.subject_name}"





"""------------------------------------------RESULT----------(code to push)--------------------------------"""
class ReportCard(models.Model):
    student_level = models.ForeignKey(StudentYearLevel, on_delete=models.CASCADE, null=True, blank=True)
    total_marks = models.IntegerField()    #fetch from sa1+sa2 of all subj
    max_marks = models.IntegerField()      #subj->len*100
    percentage = models.FloatField()
    grade = models.CharField(max_length=50)
    division = models.CharField(max_length=50)
    rank = models.IntegerField(null=True, blank=True)  
    attendance = models.CharField(max_length=10, null=True, blank=True)
    teacher_remark = models.TextField()
    promoted_to_class = models.ForeignKey(StudentYearLevel, on_delete=models.CASCADE, null=True, blank=True, related_name="reportcards_as_promotion")
    supplementary_in = models.CharField(max_length=100, null=True, blank=True)
    school_reopen_date = models.DateField()

    def __str__(self):
        student = self.student_level.student.user
        return f"{student.first_name} {student.last_name} - {self.student_level.year.year_name} - {self.student_level.level.level_name}"
    

class SubjectScore(models.Model):
    report_card = models.ForeignKey(ReportCard, on_delete=models.CASCADE, related_name='subject_scores')
    marks_obtained = models.ForeignKey(StudentMarks, on_delete=models.CASCADE, null=True, blank=True, related_name='subject_scores')
    def __str__(self):
        return f"{self.marks_obtained} -{self.marks_obtained.subject.subject_name}- {self.report_card.student_level.year.year_name} - {self.report_card.student_level.level.level_name}"
    

class ReportCardDocument(models.Model):
    report_card = models.ForeignKey(ReportCard, on_delete=models.CASCADE, related_name='documents')
    documents = models.ForeignKey(Document, on_delete=models.CASCADE,null=True, blank=True, related_name='report_card_documents')


class NonScholasticGradeTermWise(models.Model):
    non_scholastic_subject = models.ForeignKey(Subject, on_delete=models.CASCADE,null=True, blank=True ,related_name='term_grades')
    report_card = models.ForeignKey(ReportCard, on_delete=models.CASCADE, null=True, blank=True,related_name='non_scholastic_grades')
    term = models.ForeignKey("Term", on_delete=models.CASCADE)
    grade = models.CharField(max_length=5)
    class Meta:
        unique_together = ('report_card','non_scholastic_subject','term','grade')
    def __str__(self):
        return f"{self.non_scholastic_subject.subject_name} - {self.term.term_number} - {self.report_card.student_level.student.user.first_name}"


class PersonalSocialQuality(models.Model):
    quality_name = models.CharField(max_length=100)
    def __str__(self):
        return self.quality_name


class PersonalSocialQualityTermWise(models.Model):
    personal_quality = models.ForeignKey(PersonalSocialQuality, on_delete=models.CASCADE, related_name='term_grades')
    report_card = models.ForeignKey(ReportCard, on_delete=models.CASCADE,null=True, blank=True, related_name='personal_qualities')
    term = models.ForeignKey("Term", on_delete=models.CASCADE)
    grade = models.CharField(max_length=5)

    class Meta:
        unique_together = ('report_card', 'personal_quality', 'term', 'grade')
    
    def __str__(self):
        return f"{self.personal_quality.quality_name} - {self.term.term_number} - {self.report_card.student_level.student.user.first_name}-{self.report_card.student_level.year.year_name} - {self.report_card.student_level.level.level_name}"



#-------------------
# Expense Models 
#------------------- 


class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('Cash', 'Cash'), ('Cheque', 'Cheque'), ('Online', 'Online')
    ]
    STATUS_CHOICES = [
        ('Pending', 'Pending'), ('Success', 'Success'), ('Failed', 'Failed')
    ]

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    remarks = models.TextField(max_length=225,blank=True, null=True)
    payment_date = models.DateTimeField()

    cheque_number = models.CharField(max_length=50, blank=True, null=True, unique=True)
   
    # RazorpayX
    payout_id = models.CharField(max_length=100, blank=True, null=True)
    fund_account_id = models.CharField(max_length=100, blank=True, null=True)
    contact_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.payment_method} - ₹{self.amount} ({self.status})"



class ExpenseCategory(models.Model): 
    name = models.CharField(max_length=100, unique=True)
    # description = models.TextField(blank=True, null=True)

    def __str__(self): 
        return self.name 
    
class SchoolExpense(models.Model): 
    school_year = models.ForeignKey(SchoolYear, on_delete=models.CASCADE)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='expenses')
    description = models.TextField(max_length=225,blank=True, null=True)
    approved_by = models.ForeignKey("authentication.User", on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_expenses')
    created_by = models.ForeignKey("authentication.User", on_delete=models.SET_NULL, null=True, blank=True, related_name='created_expenses') 
    created_at = models.DateTimeField(auto_now_add=True)
    payment = models.OneToOneField(Payment,on_delete=models.SET_NULL,null=True,blank=True)

    # def __str__(self): 
    #     return f"{self.category.name} - ₹{self.amount} on {self.expense_date}" 
    def __str__(self):
        payment_amount = self.payment.amount if self.payment else "No Payment"
        return f"{self.category.name} - ₹{payment_amount}"


class Employee(models.Model):
    user = models.OneToOneField("authentication.User", on_delete=models.CASCADE)
    base_salary = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.user.get_full_name()} - base_salary {self.base_salary}"

class EmployeeSalary(models.Model):
    MONTH_CHOICES = [
        ("July", "July"), ("August", "August"), ("September", "September"),
        ("October", "October"), ("November", "November"), ("December", "December"),
        ("January", "January"), ("February", "February"), ("March", "March"),
        ("April", "April"), ("May", "May"), ("June", "June"),
    ]

    user = models.ForeignKey(Employee, on_delete=models.CASCADE)  
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2)  # base salary
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0)  
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)  # after deductions or bonus
    month = models.CharField(max_length=20, choices=MONTH_CHOICES)
    school_year = models.ForeignKey(SchoolYear, on_delete=models.CASCADE)
    paid_by = models.ForeignKey("authentication.User", on_delete=models.SET_NULL, null=True, blank=True) #jisne salary issue ki
    remarks = models.TextField(max_length=225,null=True, blank=True)
    created_at = models.DateTimeField()
    payment = models.OneToOneField(Payment,on_delete=models.SET_NULL,null=True,blank=True)


    def __str__(self):
        return f"{self.user.user.first_name} {self.month}  {self.net_amount}"
    class Meta:
        unique_together = ['user', 'month', 'school_year']

# --------------------------------------------income---------------------------------------------

class IncomeCategory(models.Model): 
    name = models.CharField(max_length=100, unique=True)# 

    def __str__(self): 
        return self.name 
    
class SchoolIncome(models.Model): 
    PAYMENT_METHOD_CHOICES = [ 
        ('cash', 'Cash'), 
        ('cheque', 'Cheque'), 
        ('online', 'Online'),] 
    STATUS_CHOICES = [ 
        ('pending', 'Pending'), 
        ('confirmed', 'Confirmed'), ] 
    MONTH_CHOICES = [
        ("July", "July"), ("August", "August"), ("September", "September"),
        ("October", "October"), ("November", "November"), ("December", "December"),
        ("January", "January"), ("February", "February"), ("March", "March"),
        ("April", "April"), ("May", "May"), ("June", "June"),
    ]
    month = models.CharField(max_length=20, choices=MONTH_CHOICES)
    category = models.ForeignKey(IncomeCategory, on_delete=models.PROTECT, related_name='incomes')# 
    amount = models.DecimalField(max_digits=12, decimal_places=2)# 
    description = models.TextField(max_length=225,blank=True, null=True)# 
    income_date = models.DateField()# 
    school_year = models.ForeignKey(SchoolYear, on_delete=models.PROTECT)  # Added as of 20Aug25
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash') 
    attachment = models.FileField(upload_to=income_attachments, blank=True, null=True) 
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending') 
    created_by = models.ForeignKey("authentication.User", on_delete=models.SET_NULL, null=True, blank=True, related_name='created_incomes') 
    created_at = models.DateTimeField(auto_now_add=True)# 
    
    def __str__(self): 
        return f"{self.category.name} + ₹{self.amount} on {self.income_date}"
    
    class Meta:
        unique_together = ['category', 'month', 'school_year']
        

class SchoolTurnOver(models.Model):

    school_year = models.OneToOneField(SchoolYear, on_delete=models.CASCADE)

    carry_forward = models.JSONField(default=dict, blank=True)#store last year balance
    total_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_expense = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_turnover = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    financial_outcome = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    financial_status = models.CharField(
        max_length=10,
        choices=[("Profit", "Profit"), ("Loss", "Loss"), ("Break-even", "Break-even")],
        default="Break-even"
    )
    calculated_at = models.DateTimeField(auto_now_add=True)

    verified_by = models.ForeignKey("authentication.User", on_delete=models.SET_NULL, null=True, blank=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    is_locked = models.BooleanField(default=False)

    def __str__(self):
        return f"Yearly Turnover: {self.school_year}"
    