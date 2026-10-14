from django.contrib import admin
from director.models import *

# Register your models here.

admin.site.register(
    [
        Director,
        Subject,
        Term,
        Period,
        ClassRoom,
        YearLevel,
        SchoolYear,
        ClassRoomType,
        Department,
        ClassPeriod,
        Role,
        Admission,
        BankName,
        BankingDetail,
        File,
        Document,
        DocumentType,
        OfficeStaff,
        City,
        State,
        Country,
        Address,
        ExamType,
        ExamPaper,
        ExamSchedule,
        StudentMarks,
        ReportCard,
        SubjectScore,
        ReportCardDocument,
        NonScholasticGradeTermWise,
        PersonalSocialQuality,
        PersonalSocialQualityTermWise,
        ExpenseCategory,
        SchoolExpense,
        IncomeCategory,
        SchoolIncome,
        EmployeeSalary,
        Employee,
        SchoolTurnOver,
        Payment,
        MasterFee,
        FeeStructure,
        AppliedFeeDiscount,
        StudentFee,
        FeePayment
        # RazorpayPayment

    ]
)
