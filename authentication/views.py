from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from student.pagination import CreatePagination
from .models import User , UserStatusLog
from .serializers import *
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken, BlacklistMixin
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework import viewsets




class UserView(APIView):
    def post(self, request):
        serializer = UserSerializer(data=request.data, context={'request': request})
        # serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "message": "User created successfully.",
                "user": {
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "roles": [role.name for role in user.role.all()]
                }
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])     #  Added as of 29Aug25 at 12:50 PM
@permission_classes([IsAuthenticated])
def ChangePasswordView(request):
    current_password = request.data.get("current_password")
    change_password = request.data.get("change_password")
    
    # Get the authenticated user from the request
    user = request.user
    
    serialized = ChangePasswordSerializer(data=request.data)

    if serialized.is_valid():
        # Check if the provided current password matches the user's actual password
        if user.check_password(current_password):
            user.set_password(change_password)
            user.save()
            return Response({"Message": "Password changed successfully"})
        
        return Response({"Message": "Invalid current password"}, status=400)
    
    return Response(serialized.errors, status=400)



@api_view(["POST"])
def LoginView(request):
    if request.method == "POST":
        email = request.data.get("email")
        password = request.data.get("password")

        serializer = LoginSerializers(data=request.data, context={'request': request})

        if serializer.is_valid():
            # Check if user exists and is inactive
            try:
                user = User.objects.all_including_inactive().get(email=email)
                if not user.is_active:
                    return Response(
                        {"Message": "Your account is inactive"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except User.DoesNotExist:
                return Response(
                    {"Message": "User no longer exists"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # authenticating only the active users
            user = authenticate(email=email, password=password)
            if user is None:
                return Response(
                    {"Message": "Invalid Credentials"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            #******** This wont work cuz authenticate treat the user.is_active =False as None *********
            # if not user.is_active:
            #     return Response({"Message": "Your account is inactive"}, status=status.HTTP_400_BAD_REQUEST)
                
            refresh = RefreshToken.for_user(user)
            access = str(refresh.access_token)
            refresh_token = str(refresh)

            user_roles = user.role.all()
            role_names = [role.name for role in user_roles]

            # Build full name
            full_name = f"{user.first_name} {user.middle_name or ''} {user.last_name}".strip()

            # Build user_profile URL
            profile_url = None
            if user.user_profile:
                request = request  # from outer scope
                profile_url = request.build_absolute_uri(user.user_profile.url)


            # Assuming only one role per user
            role_name = role_names[0] if role_names else None

            role_id = None
            role_key = None
            year_level_data = None

            if role_name == "teacher":
                try:
                    teacher = Teacher.objects.get(user=user, is_active=True)
                    role_id = teacher.id
                    role_key = "teacher_id"
                except Teacher.DoesNotExist:
                    pass

            elif role_name == "student":
                try:
                    student = Student.objects.get(user=user, is_active=True)
                    role_id = student.id
                    role_key = "student_id"

                    student_year_level = student.student_year_levels.order_by('-year_id').first()

                    if student_year_level and student_year_level.level:
                        year_level_data = {
                            "id": student_year_level.level.id,
                            "name": student_year_level.level.level_name
                        }

                except Student.DoesNotExist:
                    pass

            elif role_name == "guardian":
                try:
                    guardian = Guardian.objects.get(user=user, is_active=True)
                    role_id = guardian.id
                    role_key = "guardian_id"
                except Guardian.DoesNotExist:
                    pass

            elif role_name == "director":
                try:
                    director = Director.objects.get(user=user, is_active=True)
                    role_id = director.id
                    role_key = "director_id"
                except Director.DoesNotExist:
                    pass
            elif role_name=='office staff':
                try:
                  staf=OfficeStaff.objects.get(user=user, is_active=True)
                  role_id=staf.id
                  role_key="staff_id"
                except OfficeStaff.DoesNotExist:
                    pass
            # elif role_name=='Deactivated User':
            #     return Response({"message": "Your account has been deactivated"})


            response_data = {
                    "Message": "User logged in successfully",
                    "access": access,
                    "refresh": refresh_token,
                    "User ID": user.id,
                    "Roles": role_names,
                    "name": full_name,
                    "user_profile": profile_url or None,
                }

            if role_key:
                response_data[role_key] = role_id

            if year_level_data:
                response_data["year_level"] = year_level_data

            return Response(response_data, status=status.HTTP_200_OK)

        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)






@api_view(["POST"])
def LogOutView(request):
    if request.method == "POST":

        serializer = LogoutSerializers(data=request.data)

        if serializer.is_valid():
            refresh_token = serializer.validated_data.get("refresh_token")

            if refresh_token:
                refresh = RefreshToken(refresh_token)
                refresh.blacklist()

                return Response(
                    {"Message": "LogOut Successfuly"}, status=status.HTTP_200_OK
                )

            return Response(
                {"error": "Refresh token not provide"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({"Error": "Invalid data"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def SendOtpView(request):

    email_serialzer = OtpSerializers(data=request.data)

    if email_serialzer.is_valid():
        email = email_serialzer.validated_data["email"]
        otp = get_random_string(length=6, allowed_chars="1234567890")
        cache.set(email, otp, timeout=300)

        if email is not None:
            from django.conf import settings

            send_mail(
                "Reset your Password",
                f"Your Otp for Forgot Password {otp}",
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False,
            )

            return Response(
                {"Message": "Otp Sent to your Email"}, status=status.HTTP_200_OK
            )
        return Response({"Message": "Invalid Email"}, status=status.HTTP_204_NO_CONTENT)

    return Response(email_serialzer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def ForgotPasswordView(request):
    serializer_data = ForgotSerializers(data=request.data)

    if serializer_data.is_valid():
        email = serializer_data.validated_data["email"]
        otp = serializer_data.validated_data["otp"]
        new_password = serializer_data.validated_data["new_password"]

        cached_otp = cache.get(email)

        if cached_otp == otp:
            try:
                user = User.objects.get(email=email)

            except User.DoesNotExist:

                return Response(
                    {"error": "User Not Found"}, status=status.HTTP_404_NOT_FOUND
                )

            user.set_password(new_password)
            user.save()
            cache.delete(email)

            return Response(
                {"Message": "Password changed Successfull"}, status=status.HTTP_200_OK
            )
        return Response({"Message": "Invalid OTP "}, status=status.HTTP_400_BAD_REQUEST)

    return Response(serializer_data.errors, status=status.HTTP_400_BAD_REQUEST)


# ***********************ErroView**********************************
class ErrorLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ErrorLog.objects.all()
    # queryset = ErrorLog.objects.all().order_by('-created_at')
    serializer_class = ErrorLogSerializer
    # permission_classes = [IsAdminUser]

# ************ User Status Log View*******************
class UserStatusLogView(viewsets.ModelViewSet):
    queryset = UserStatusLog.objects.all()
    serializer_class = UserStatusLogSerializer
    pagination_class = CreatePagination

    

# with permissions working fine
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.contrib.auth import get_user_model

from authentication.permissions import LoggedInUsersPermissions

User = get_user_model()

class LoggedInUsersAPIView(APIView):
    permission_classes = [LoggedInUsersPermissions]
    
    def get(self, request):
        """
        Get all logged-in users
        """
        # Get all active sessions
        sessions = Session.objects.filter(expire_date__gte=timezone.now())
        
        logged_in_users = []
        user_ids = set()
        
        for session in sessions:
            session_data = session.get_decoded()
            
            # Check if user is authenticated in this session
            if '_auth_user_id' in session_data:
                user_id = session_data['_auth_user_id']
                
                # Avoid duplicates
                if user_id not in user_ids:
                    user_ids.add(user_id)
                    
                    try:
                        user = User.objects.get(id=user_id, is_active=True)
                        
                        # Get user roles
                        roles = [role.name for role in user.role.all()]
                        
                        # Build full name
                        full_name = f"{user.first_name} {user.middle_name or ''} {user.last_name}".strip()
                        
                        # Build profile URL
                        profile_url = None
                        if user.user_profile:
                            profile_url = request.build_absolute_uri(user.user_profile.url)
                        
                        logged_in_users.append({
                            'id': user.id,
                            'email': user.email,
                            'first_name': user.first_name,
                            'middle_name': user.middle_name,
                            'last_name': user.last_name,
                            'full_name': full_name,
                            'roles': roles,
                            'last_login': user.last_login,
                            'user_profile': profile_url,
                        })
                    except User.DoesNotExist:
                        pass
        
        return Response({
            'count': len(logged_in_users),
            'users': logged_in_users
        }, status=status.HTTP_200_OK)
        
        
        
# without permissions

# User = get_user_model()

# class LoggedInUsersAPIView(APIView):
#     """
#     API to get all currently logged-in users
#     No permission required - accessible to anyone
#     """
    
#     def get(self, request):
#         """
#         Get all logged-in users
#         """
#         # Get all active sessions
#         sessions = Session.objects.filter(expire_date__gte=timezone.now())
        
#         logged_in_users = []
#         user_ids = set()
        
#         for session in sessions:
#             session_data = session.get_decoded()
            
#             # Check if user is authenticated in this session
#             if '_auth_user_id' in session_data:
#                 user_id = session_data['_auth_user_id']
                
#                 # Avoid duplicates
#                 if user_id not in user_ids:
#                     user_ids.add(user_id)
                    
#                     try:
#                         user = User.objects.get(id=user_id, is_active=True)
                        
#                         # Get user roles
#                         roles = [role.name for role in user.role.all()]
                        
#                         # Build full name
#                         full_name = f"{user.first_name} {user.middle_name or ''} {user.last_name}".strip()
                        
#                         # Build profile URL
#                         profile_url = None
#                         if user.user_profile:
#                             profile_url = request.build_absolute_uri(user.user_profile.url)
                        
#                         logged_in_users.append({
#                             'id': user.id,
#                             'email': user.email,
#                             'first_name': user.first_name,
#                             'middle_name': user.middle_name,
#                             'last_name': user.last_name,
#                             'full_name': full_name,
#                             'roles': roles,
#                             'last_login': user.last_login,
#                             'user_profile': profile_url,
#                         })
#                     except User.DoesNotExist:
#                         pass
        
#         return Response({
#             'count': len(logged_in_users),
#             'users': logged_in_users
#         }, status=status.HTTP_200_OK)


# ------- Added as of 03Sep25 at 11:59 PM ------- #
# *********** LoggedInUsersView ******** #

# class LoggedInUsersView(viewsets.ViewSet):
#     permission_classes = [LoggedInUsersPermissions]
    
#     @action(detail=False, methods=['get'], url_path='')
#     def active_users(self, request):
#         """
#         Custom action to get all logged-in users
#         """
#         # Get all active sessions
#         sessions = Session.objects.filter(expire_date__gte=timezone.now())
        
#         logged_in_users = []
#         user_ids = set()
        
#         for session in sessions:
#             session_data = session.get_decoded()
            
#             # Check if user is authenticated in this session
#             if '_auth_user_id' in session_data:
#                 user_id = session_data['_auth_user_id']
                
#                 # Avoid duplicates
#                 if user_id not in user_ids:
#                     user_ids.add(user_id)
                    
#                     try:
#                         user = User.objects.get(id=user_id, is_active=True)
                        
#                         # Get user roles
#                         roles = [role.name for role in user.role.all()]
                        
#                         # Build full name
#                         full_name = f"{user.first_name} {user.middle_name or ''} {user.last_name}".strip()
                        
#                         # Build profile URL
#                         profile_url = None
#                         if user.user_profile:
#                             profile_url = request.build_absolute_uri(user.user_profile.url)
                        
#                         logged_in_users.append({
#                             'id': user.id,
#                             'email': user.email,
#                             'first_name': user.first_name,
#                             'middle_name': user.middle_name,
#                             'last_name': user.last_name,
#                             'full_name': full_name,
#                             'roles': roles,
#                             'last_login': user.last_login,
#                             'user_profile': profile_url,
#                         })
#                     except User.DoesNotExist:
#                         pass
        
#         return Response({
#             'count': len(logged_in_users),
#             'users': logged_in_users
#         }, status=status.HTTP_200_OK)
