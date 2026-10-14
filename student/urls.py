from .views import *
from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
# router.register(r'studentYearLevel', StudentYearLevelView)
router.register(r'students', StudentView)

router.register(r'guardian', GuardianProfileView)

router.register(r'studentyearlevels', StudentYearLevelView,basename='studentyearlevelss')   # As of 29May25 at 02:30 PM
router.register(r'studentguardian', StudentGuardianView, basename='student-guardian')  # Added as of 18jul25 at 03:10 PM
router.register(r'admission-full', AdmissionFullViewSet, basename='admission-full')
router.register(r'graduate', StudentActiveViewSet, basename='graduate')


urlpatterns = [
    path("guardian-types/", GuardianTypeView, name="guardian-type"),
    path("guardian-type/<int:pk>/", GuardianTypeView, name="guardian-type-details"),
      path('', include(router.urls)), 
]


