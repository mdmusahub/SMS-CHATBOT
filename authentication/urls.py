from django.urls import path,include
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView,TokenRefreshView
from .views import *


from rest_framework.routers import DefaultRouter
from .views import  ErrorLogViewSet, UserStatusLogView

router = DefaultRouter()
router.register(r'error-logs', ErrorLogViewSet, basename='error-logs')
router.register(r'user-logs', UserStatusLogView, basename='userstatus-log')
# router.register(r'loggedin-users', LoggedInUsersView, basename='loggedin-users')


urlpatterns = [
    # path("users/", views.UserView, name="custom_user_list"),
    path('users/', UserView.as_view(), name='user-registration'),
    # path("user/<int:pk>/", views.UserView, name="custom_user_detail"),
    path("change_password/", views.ChangePasswordView),
    path("login/", views.LoginView),
    path("logout/", views.LogOutView),
    path('refresh/',TokenRefreshView.as_view(),name='token_refresh'),
    path("otp/", views.SendOtpView),
    path("reset_password/", views.ForgotPasswordView),
    path('', include(router.urls)), 
    
    path('loggedin-users/', LoggedInUsersAPIView.as_view(), name='loggedin-users'),

]





