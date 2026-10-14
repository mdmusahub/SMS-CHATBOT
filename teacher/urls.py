from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . views import *


router = DefaultRouter()
router.register(r'teacher', TeacherView)
router.register(r'teacheryearlevel', TeacherYearLevelView, basename='teacheryearlevel')

urlpatterns = [
    path('', include(router.urls)),
    path('all-teachers/', AllTeachersWithYearLevelsAPIView.as_view()),
    path('substitute-assign/', SubstituteAssignmentView.as_view()),
    path('absent-teacher/', AbsentTeacherFreeReplacementAPIView.as_view()),
]