from email.mime import base
from django.urls import path,include
from .views import *
from director.views import Director_Dashboard_Summary


from rest_framework.routers import DefaultRouter



router = DefaultRouter()

router.register(r'country', CountryView)
router.register(r'states', StateView)
router.register(r'city', CityView)
router.register(r'addresses', AddressView)
router.register(r'Period', PeriodView)
router.register(r'classPeriod', ClassPeriodView)
router.register(r'director', DirectorView)
router.register(r'banking_details', BankingDetailView)
router.register(r'bank_name', BankNameView)

router.register(r'terms', TermView)
router.register(r'admission',AdmissionView)
router.register(r'officestaff',OfficeStaffView)
router.register(r'DocumentType',DocumentTypeView)

router.register(r'File',FileView),
router.register(r'Document',DocumentView,basename='document'),
router.register(r'transfer-certificates', TransferCertificateDocumentView, basename='transfer-certificates'),
router.register(r'inactive-documents', InactiveDocumentView, basename='inactive-documents'),
router.register(r'subject',subjectView),

router.register(r'Exam-Type',ExamTypeView)
router.register(r'Exam-Paper',ExamPaperView)
router.register(r'Exam-Schedule',ExamScheduleView)
router.register(r'Student-Marks',StudentMarksView,basename='student-marks')

router.register(r'personal-social-quality', PersonalSocialQualityView, basename='personal-social-quality')
router.register(r'personal-social-grades', PersonalSocialGradeViewSet, basename='personal-social-grades')
router.register(r'non-scholastic-grades', NonScholasticGradeViewSet, basename='non-scholastic')
router.register(r'report-cards', ReportCardViewSet, basename='report-cards')

router.register(r'income-category', IncomeCategoryView, basename='income-category')
router.register(r'school-income', SchoolIncomeViewSet, basename='school-income')
router.register(r'Expense-Category', ExpenseCategoryView)
router.register(r'School-Expense', SchoolExpenseView)
router.register(r'Employee',EmployeeView,basename=Employee)
router.register(r'Employee-salary',EmployeeSalaryView)
router.register(r'school-turnover',SchoolTurnOverViewSet,basename='school-turnover')
router.register(r'payment',PaymentView)
router.register(r'student-promotion',StudentPromotionViewSet,basename='student-promotion')


router.register(r'masterfees', MasterFeeViewSet)
router.register(r'feestructures', FeeStructureViewSet)
router.register(r'studentfees', StudentFeeView,basename='student fee')
router.register(r'appliedfeediscounts', AppliedFeeDiscountViewSet)
router.register(r'FeePayment', FeePaymentView)

urlpatterns = [
    path('download-file/', DownloadFileView.as_view()), 
    path("year-levels/", YearLevelView),
    path("year-level/<int:id>/", YearLevelView),
    
    path("school-years/", SchoolYearView),
    path("school-year/<int:pk>/", SchoolYearView),
    
    path("departments/", DepartmentView),
    path("department/<int:pk>/", DepartmentView),
    
    path("classroom-types/", ClassRoomTypeView),
    path("classroom-type/<int:pk>/", ClassRoomTypeView),
    
    path("classrooms/", ClassRoomView),          
    path("classrooms/<int:pk>/", ClassRoomView),  
    
    path("roles/", RoleView, name="roleDetails"),
    path("role/<int:pk>/", RoleView, name="roleDetails"),
    
    path("director-dashboard/", Director_Dashboard_Summary),
    path("new-admission/", NewAdmissionsList),
    path("teacher-dashboard/<int:id>/", teacher_dashboard),
    path("guardian-dashboard/<int:id>/", guardian_dashboard),
    path("student_dashboard/<int:id>/", student_dashboard),
    path('office-staff-dashboard/', office_staff_dashboard),
    path("director/fee-summary/", director_fee_summary),
    path('livelihood_filter/', livelihood_distribution),
    path('periods/', assigned_periods),
    path("fetch_upload_doc/",document_fetch_dashboard),
    path('', include(router.urls)),

    
    # As of 25June25 at 12:35
    path('student-category-dashboard/', student_category, name='student-category'),
    path('income-distribution-dashboard/', guardian_income_distribution, name='guardian-income-distribution'), 
    # path('income-distribution-dashboard-student/', guardian_income_distribution_with_student, name='guardian-income-distribution-student'), 
    path("fee-dashboard/", fee_dashboard, name="fee-dashboard-summary"),    # complete dashboard
    # Termination process api below
    path("deactivate-user/", deactivate_user, name="deactivate-user"),
    path("reactivate-user/", reactivate_user, name="reactivate-user"),
    path("inactive-user/", list_inactive_users, name="inactive-user"),
    path("notify-defaulters/", DefaulterNotifyView.as_view(), name="notify-defaulters"),
    path("student-fee-dashboard/", student_fee_dashboard, name="student-fee-dashboard-summary"),

    path("icici/return/", icici_return, name="icici-return"),
    path('GetTCdata/', get_transfer_certificate_data, name='generate-tc'),
]


