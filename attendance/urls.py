from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'student-attendance', StudentAttendanceView, basename='StudentAttendanceViewSet')
router.register(r'api/report', AttendanceReportViewSet, basename='attendance-report')
router.register(r'director-dashboard', DirectorAttendanceDashboard, basename='attendance-text-summary')
router.register(r'teacher-dashboard', TeacherAttendanceDashboard, basename='teacher-student-attendance')
router.register(r'student-dashboard', StudentOwnAttendanceViewSet, basename='student-own-attendance')
router.register(r'guardian/attendance', GuardianChildrenAttendanceViewSet, basename='guardian-attendance')
# router.register(r'attendance/mark-holidays', BulkHolidayAttendanceViewSet, basename='mark-holiday'),
router.register('events', SchoolEventViewSet, basename='event')
router.register(r'holidays',HolidayViewSet,basename='holidays')
router.register("office-staff-attendance", OfficeStaffAttendanceView, basename="office-staff-attendance")
router.register("teacher-attendance", TeacherAttendanceView, basename="teacher-attendance")


urlpatterns = [
    path('', include(router.urls)),
    path('teacher-classes/<int:teacher_id>/', TeacherYearLevelList.as_view(), name='teacher-classes'),
    path('holidays/import', FetchIndianHolidaysView.as_view()),
    path('calendar/', MonthlyCalendarView.as_view(), name='monthly-calendar'),
    path('send-whatsapp/', SendWhatsAppView.as_view(), name='send_whatsapp')
]