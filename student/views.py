from argparse import Action
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response

from director.models import *
from director.models import Address, Admission, BankingDetail, Role, YearLevel
from director.serializers import BankingDetailsSerializer

from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from authentication.models import UserStatusLog

from .models import GuardianType, Student, StudentYearLevel, StudentGuardian
from .serializers import *
from rest_framework import status
from rest_framework import filters
from rest_framework.response import Response
from .serializers import GuardianSerializer
from .models import Guardian
from director.models import Role
from rest_framework.filters import SearchFilter
from rest_framework import viewsets, permissions
from .pagination import CreatePagination
from datetime import date  
from rest_framework.decorators import action 
from rest_framework.permissions import IsAuthenticated,AllowAny



@api_view(["GET", "POST", "PUT", "DELETE"])
def GuardianTypeView(request, pk=None):
    if request.method == "GET":
        if pk is not None:
            try:
                guardian_type = GuardianType.objects.get(id=pk)
                serializer = GuardianTypeSerializer(guardian_type, many=False)
                return Response(serializer.data, status.HTTP_200_OK)

            except GuardianType.DoesNotExist:
                return Response(
                    {"message": "Data Not Found"}, status.HTTP_404_NOT_FOUND
                )
            except Exception as e:
                return Response(
                    {"message": "Something went wrong"},
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        else:
            guardian_types = GuardianType.objects.all()
            serializer = GuardianTypeSerializer(guardian_types, many=True)
            return Response(serializer.data, status.HTTP_200_OK)

    elif request.method == "POST":
        json_data = request.data

        if json_data.get("name", None) is None:
            return Response({"message": "Invalid Data"}, status.HTTP_400_BAD_REQUEST)

        json_data["name"] = json_data["name"].lower()
        serializer = GuardianTypeSerializer(data=json_data)

        if serializer.is_valid():

            if GuardianType.objects.filter(name=json_data["name"]).exists():
                return Response(
                    {"message": "Guardian type Already Exists"},
                    status.HTTP_400_BAD_REQUEST,
                )

            serializer.save()
            return Response(
                {"message": "GuardianType Added Successfully"}, status.HTTP_201_CREATED
            )
        return Response({"message": "Invalid Data"}, status.HTTP_400_BAD_REQUEST)

    elif request.method == "PUT":

        if request.data.get("name", None) is None:
            return Response({"message": "Invalid Data"}, status.HTTP_400_BAD_REQUEST)

        request.data["name"] = request.data["name"].lower()

        try:
            guardian_type = GuardianType.objects.get(id=pk)
            serializer = GuardianTypeSerializer(
                instance=guardian_type, data=request.data, partial=True
            )

            if serializer.is_valid():

                if GuardianType.objects.filter(name=request.data["name"]).exists():
                    return Response(
                        {"message": "Guardian type Already Exists"},
                        status.HTTP_400_BAD_REQUEST,
                    )

                serializer.save()
                return Response(
                    {"message": "GuardianType updated Successfully"},
                    status.HTTP_200_OK,
                )

            return Response({"message": "Invalid Data"}, status.HTTP_400_BAD_REQUEST)

        except GuardianType.DoesNotExist:
            return Response({"message": "Data Not Found"}, status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response(
                {"message": "something went wrong"},
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    elif request.method == "DELETE":

        if pk is None:
            return Response(
                {"message": "Id is Required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            get = GuardianType.objects.get(id=pk)
            get.delete()
            return Response(
                {"message": "GuardianType Delete Successfully"}, status.HTTP_200_OK
            )
        except GuardianType.DoesNotExist:
            return Response({"message": "Data Not Found"}, status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"message": "Something went wrong"},
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# 
from django_filters.rest_framework import DjangoFilterBackend  
# from .filters import Filter
class StudentView(ModelViewSet):
    queryset = Student.objects.filter(is_active=True)
    serializer_class = StudentSerializer
    # pagination_class = CreatePagination
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # filterset_class = StudentFilter

    search_fields = [
        'user__email', 
        'user__first_name'
        "student__first_name",
        "student__last_name",
        "guardian__first_name",
        "guardian__last_name",
        "tc_letter",
        "enrollment_no",
        "previous_school_name",
    ]

    ordering_fields = [
        "user__first_name",
        "height",
        "weight",
        "date_of_birth",
        "scholar_number",
    ]
    
    def get_permissions(self):
        """Public access for list/retrieve; JWT required for others."""
        if self.action in ['list', 'retrieve','create','update', 'partial_update']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user_instance = instance.user
        student_role = Role.objects.get(name='student')

        
        user_instance.role.remove(student_role)
        other_roles = user_instance.role.exclude(name='student')
        if other_roles.exists():
                self.perform_destroy(instance)
                return Response({"success": "Student profile deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
        else:
                
                instance.delete()
                self.perform_destroy(user_instance)
                return Response({"success": "Student profile and related user deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
       


    def calculate_age(self, birth_date):
        today = date.today()
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    @action(detail=False, methods=['get'], url_path='by-year-level-id/(?P<year_level_id>[^/.]+)')
    def by_year_level_id(self, request, year_level_id=None):    
        student_year_levels = StudentYearLevel.objects.filter(level_id=year_level_id, student__is_active=True)
        
        if not student_year_levels.exists():
            return Response({"message": "No students found for the specified year level"}, status=status.HTTP_404_NOT_FOUND)

        students_data = []

        for sy in student_year_levels:
            student = sy.student
            if not student:
                continue
            user = student.user
            address_obj = Address.objects.filter(user=user).first() if user else None

            full_address = (
                f"{address_obj.house_no}, {address_obj.address_line}, {address_obj.city.name}, "
                f"{address_obj.state.name}, {address_obj.country.name}, Area Code: {address_obj.area_code}"
                if address_obj and address_obj.city and address_obj.state and address_obj.country else "N/A"
            )

            students_data.append({
                "student_name": f"{user.first_name} {user.last_name}" if user else "N/A",
                "age": self.calculate_age(student.date_of_birth) if student.date_of_birth else "N/A",
                "gender": student.gender or "N/A",
                "mobile_number": getattr(user, 'phone', "N/A") if user else "N/A",
                "address": full_address,
                "year_level": sy.level.level_name if sy.level else "N/A",
                "school_year": sy.year.year_name if sy.year else "N/A"
            })

        return Response(students_data, status=status.HTTP_200_OK)
    
    # *************************JWTlogin student**************************
    
    @action(detail=False, methods=['get', 'put', 'patch'], url_path='student_my_profile', permission_classes=[IsAuthenticated])
    def student_my_profile(self, request):
        user = request.user

        try:
            student = Student.objects.get(user=user)
        except Student.DoesNotExist:
            return Response({"error": "No student profile found for this user."}, status=status.HTTP_404_NOT_FOUND)

        if request.method in ['PUT', 'PATCH']:
            partial = request.method == 'PATCH'
            serializer = self.get_serializer(student, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response({"success": "Student profile updated successfully", "data": serializer.data}, status=status.HTTP_200_OK)

        serializer = self.get_serializer(student)
        return Response(serializer.data, status=status.HTTP_200_OK)


    @action(detail=False, methods=['get'], url_path='student_details')
    def get_student_details(self, request):
        student_id = request.query_params.get('student_id')
        start_date = request.query_params.get('start_date')  # expected format: YYYY-MM-DD
        end_date = request.query_params.get('end_date')      # expected format: YYYY-MM-DD

        # If specific student id is given
        if student_id:
            student = Student.objects.filter(id=student_id, is_active=True).first()
            if not student:
                return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)
            students = [student]
        else:
            students = Student.objects.filter(is_active=True)

            # Apply date range filter on admission_date if provided
            if start_date and end_date:
                admission_ids = Admission.objects.filter(
                    admission_date__range=[start_date, end_date]
                ).values_list('student_id', flat=True)
                students = students.filter(id__in=admission_ids)
            elif start_date:
                admission_ids = Admission.objects.filter(
                    admission_date__gte=start_date
                ).values_list('student_id', flat=True)
                students = students.filter(id__in=admission_ids)
            elif end_date:
                admission_ids = Admission.objects.filter(
                    admission_date__lte=end_date
                ).values_list('student_id', flat=True)
                students = students.filter(id__in=admission_ids)

        # Apply pagination only if explicitly requested
        page = None

        limit = request.query_params.get("limit")
        offset = request.query_params.get("offset")

        if not student_id and (limit is not None or offset is not None):
            paginator = CreatePagination()
            page = paginator.paginate_queryset(students, request, view=self)
            if page is not None:
                students = page

        data = []
        for student in students:
            user = getattr(student, 'user', None)
            address_obj = Address.objects.filter(user=user).first()
            full_address = (
                f"{address_obj.house_no}, {address_obj.address_line}, {address_obj.city.name}, "
                f"{address_obj.state.name}, {address_obj.country.name}, Area Code: {address_obj.area_code}"
                if address_obj else "N/A"
            )

            admission = Admission.objects.filter(student=student).first()
            guardian_name = "N/A"

            if admission:
                if admission.guardian and admission.guardian.user:
                    guardian_name = admission.guardian.user.get_full_name()
                elif student.father_name:
                    guardian_name = student.father_name
                elif student.mother_name:
                    guardian_name = student.mother_name

            def get_banking_detail(self, student):
                banking = BankingDetail.objects.filter(user=user).first()
                return BankingDetailsSerializer(banking).data if banking else None

            def annual_income(self, student):
                guardian = Guardian.objects.filter(studentguardian__student=student).first()
                return guardian.annual_income if guardian else "N/A"

            def get_school_year(self, admission):
                if not admission or not admission.student:
                    return "N/A"
                student_year = StudentYearLevel.objects.filter(student=admission.student).first()
                return student_year.year.year_name if student_year and student_year.year else "N/A"
            
            def get_year_level(self, admission):
                if not admission or not admission.student:
                    return "N/A"
                student_year = StudentYearLevel.objects.filter(student=admission.student).first()
                return student_year.level.level_name if student_year and student_year.level else "N/A"
    
            data.append({
                "admission_id": admission.id,
                "student_id": student.id,
                "student_name": f"{user.first_name} {user.last_name}" if user else "N/A",
                "age": self.calculate_age(student.date_of_birth) if student.date_of_birth else "N/A",
                "gender": student.gender or "N/A",
                "contact_number": student.contact_number or "N/A",
                "email": user.email or "N/A",
                "date_of_birth": student.date_of_birth or "N/A",
                "religion": student.religion or "N/A",
                "father_name": student.father_name or "N/A",
                "mother_name": student.mother_name or "N/A",
                "guardian_name": guardian_name,
                "full_address": full_address,
                "class": get_year_level(self, admission) or "N/A",
                "class_section":admission.class_section  if admission and admission.class_section else "N/A",
                "scholar number": student.scholar_number or "N/A",
                "aadhaar_number": student.aadhaar_number or "N/A",
                "FMID_number": student.FMID_number or "N/A",
                "Apaar_number": student.apaar_number or "N/A",
                "PEN_number": student.PEN_number or "N/A",
                "BPL_number": student.BPL_number or "N/A",
                "SSSMID": student.SSSMID or "N/A",
                "enrollment_no": getattr(admission, "enrollment_no", "N/A"),
                "bank details": get_banking_detail(self, student) or "N/A",
                "no. of siblings": getattr(student, "number_of_siblings", "N/A"),
                "annual income": annual_income(self, student) or "N/A",
                "guardian's contact no.":  admission.guardian.phone_no if admission and admission.guardian else "N/A",
                "is_active": student.is_active,
                "is_rte": admission.is_rte if admission else "N/A",
                "rte number": admission.rte_number if admission else "N/A",
                "school year": get_school_year(self, admission) or "N/A",
                "category": getattr(student, "category", "N/A"),
                "admission_date": admission.admission_date if admission else "N/A",
            })

        # If a single student was requested, return one dict
        if student_id:
            return Response(data[0], status=status.HTTP_200_OK)

        # If paginated, return paginated response; else return plain list
        if page is not None:
            return paginator.get_paginated_response(data)
        return Response(data, status=status.HTTP_200_OK)


class GuardianProfileView(viewsets.ModelViewSet):
    queryset = Guardian.objects.all()
    serializer_class = GuardianSerializer
    filter_backends = [SearchFilter]
    search_fields = ['user__email','user__first_name','user__guardian_relation__phone_no']
    pagination_class = CreatePagination
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve','create','update', 'partial_update']:
            return [AllowAny()]  # Public access
        return [IsAuthenticated()]  # JWT required for update, my-profile, delete

  
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user_instance = instance.user
        
        try:
            role = Role.objects.get(name='guardian')
        except Role.DoesNotExist:
            return Response({"error": "Guardian role does not exist"}, status=status.HTTP_404_NOT_FOUND)

        if user_instance.role.exclude(name='guardian').exists():
            user_instance.role.remove(role)
            instance.delete()

            return Response({"message": "Role removed successfully from user and deletd data from gaurdian"}, status=status.HTTP_200_OK)
        else:
            try:
                self.perform_destroy(instance)
                user_instance.delete()
                return Response({"message": "Successfully deleted"}, status=status.HTTP_204_NO_CONTENT)
            except Exception as e:
                return Response ({"error": "Deletion unsuccessful: Error deleting user"})
            
            
    # **********************Jwt***************    
    @action(detail=False, methods=['get', 'put', 'patch'], url_path='guardian_my_profile')
    def guardian_my_profile(self, request):
        user = request.user
      

        try:
            guardian = Guardian.objects.get(user=user)
        except Guardian.DoesNotExist:
            return Response({"error": "Guardian profile not found for this user."}, status=status.HTTP_404_NOT_FOUND)

        if request.method in ['PUT', 'PATCH']:
            partial = request.method == 'PATCH'
            serializer = self.get_serializer(guardian, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response({"success": "Guardian profile updated successfully", "data": serializer.data}, status=status.HTTP_200_OK)

        serializer = self.get_serializer(guardian)
        return Response(serializer.data, status=status.HTTP_200_OK)

# As of 19June25 at 12:46 PM
from django_filters.rest_framework import DjangoFilterBackend

class StudentYearLevelView(viewsets.ModelViewSet):
    queryset = StudentYearLevel.objects.filter(student__is_active=True)
    serializer_class = StudentYearLevelSerializer

    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['level__id','year__year_name','student__gender']  #,'student__admission__department__id', 'year__year_name']  #  GET /student-year-levels/?level__id=2
    search_fields = ['level__level_name','year__year_name']   #, 'student__admission__department__name', 'year__year_name']  #  GET /student-year-levels/?search=Nursery
    
    # combine search endpoint GET /student-year-levels/?level__id=2&search=Nursery


# Added as of 18jul25 at 03:04 PM

class StudentGuardianView(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = StudentSerializer  # We only want to show Student info

    def get_queryset(self):
        user = self.request.user
        guardian = get_object_or_404(Guardian, user=user)  # safer than direct access

        student_ids = StudentGuardian.objects.filter(
            guardian=guardian
        ).values_list('student_id', flat=True)

        return Student.objects.filter(id__in=student_ids, is_active=True)
    
    
class AdmissionFullViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"], url_path="bulk_data")
    def create_full_admission(self, request):
        serializer = AdmissionFullSerializer(data=request.data)
        if serializer.is_valid():
            admission = serializer.save()
            return Response(
                {"message": "Admission created successfully", "admission_id": admission.id},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class StudentActiveViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.filter(is_active=True)
    serializer_class = StudentSerializer
    @action(detail=False, methods=['patch'], url_path='bulk-deactivate')
    def bulk_deactivate(self, request):
        try:
            student_ids = request.data.get("student_ids", [])
            reason = request.data.get("reason", "")

            if not student_ids:
                return Response(
                    {"error": "student_ids is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            with transaction.atomic():

                students = Student.objects.all_including_inactive().filter(id__in=student_ids)

                if not students.exists():
                    return Response(
                        {"error": "No valid students found."},
                        status=status.HTTP_404_NOT_FOUND
                    )

                deactivated_students = []

                for instance in students:

                    if not instance.is_active:
                        continue

                    user = instance.user

                    # 1. Deactivate User
                    if user:
                        user.is_active = False
                        user.deactivation_reason = reason
                        user.deactivation_date = timezone.now()
                        user.reactivation_date = None
                        user.save()

                    # 2. Deactivate Student
                    instance.is_active = False
                    instance.save()

                    # 3. Deactivate StudentYearLevel
                    # StudentYearLevel.objects.filter(student=instance).update(is_active=False)

                    # # 4. Clear classes
                    # instance.classes.clear()

                    # 5. Deactivate Admissions
                    Admission.objects.all_including_inactive().filter(student=instance).update(is_active=False)

                    # 6. Deactivate Documents
                    Document.objects.all_including_inactive().filter(student=instance).update(is_active=False)

                    # 7. Deactivate Address
                    if user:
                        Address.objects.all_including_inactive().filter(user=user).update(is_active=False)

                    # 8. Deactivate BankingDetail
                    if user:
                        BankingDetail.objects.all_including_inactive().filter(user=user).update(is_active=False)

                    # 9. Log it
                    if user:
                        UserStatusLog.objects.create(
                            user=user,
                            status='TERMINATED',
                            reason=reason
                        )

                    deactivated_students.append(instance.id)

                return Response({
                    "message": "Students successfully deactivated.",
                    "student_ids": deactivated_students
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    @action(detail=False, methods=['get'], url_path='inactive-students')
    def inactive_students(self, request):
        try:
            from django.db.models import Q

            students = Student.objects.all_including_inactive().select_related(
                "user"
            ).filter(is_active=False)

            tc_student_ids = set(
                Document.objects.all_including_inactive().filter(
                    Q(document_types__name__icontains='transfer') |
                    Q(document_types__name__iexact='tc'),
                    student__in=students
                ).values_list('student_id', flat=True)
            )

            data = [
                {
                    "id": student.id,
                    "name": str(student),
                    "is_active": student.is_active,
                    "reason": student.user.deactivation_reason if student.user else None,
                    "deactivation_date": student.user.deactivation_date if student.user else None,
                    "has_tc": student.id in tc_student_ids
                }
                for student in students
            ]

            return Response({
                "count": students.count(),
                "results": data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    @action(detail=False, methods=['patch'], url_path='bulk-reactivate')
    def bulk_reactivate(self, request):
        try:
            student_ids = request.data.get("student_ids", [])
            reason = request.data.get("reason", "")
            # class_period_ids = request.data.get("class_period_ids", [])
            year_id = request.data.get("year_id")
            level_id = request.data.get("level_id")

            if not student_ids:
                return Response(
                    {"error": "student_ids is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            with transaction.atomic():

                students = Student.objects.all_including_inactive().filter(id__in=student_ids)

                if not students.exists():
                    return Response(
                        {"error": "No valid students found."},
                        status=status.HTTP_404_NOT_FOUND
                    )

                # valid_class_periods = ClassPeriod.objects.filter(
                #     id__in=class_period_ids
                # )

                level = None
                year = None

                if year_id and level_id:
                    try:
                        level = YearLevel.objects.get(id=level_id)
                        year = SchoolYear.objects.get(id=year_id)
                    except ObjectDoesNotExist:
                        return Response(
                            {"error": "Invalid year or level ID."},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                reactivated_students = []

                for instance in students:

                    if instance.is_active:
                        continue

                    user = instance.user

                    # 1. Reactivate User
                    if user:
                        user.is_active = True
                        user.deactivation_reason = None
                        user.reactivation_date = timezone.now()
                        user.save()

                    # 2. Reactivate Student
                    instance.is_active = True
                    instance.save()

                    # 3. Reactivate Admissions
                    Admission.objects.all_including_inactive().filter(student=instance).update(is_active=True)

                    # 4. Reactivate Documents
                    Document.objects.all_including_inactive().filter(student=instance).update(is_active=True)

                    # 5. Reactivate Address
                    if user:
                        Address.objects.all_including_inactive().filter(user=user).update(is_active=True)

                    # 6. Reactivate BankingDetail
                    if user:
                        BankingDetail.objects.all_including_inactive().filter(user=user).update(is_active=True)

                    # # 7. Reassign classes
                    # if valid_class_periods.exists():
                    #     instance.classes.set(valid_class_periods)

                    # 8. Reactivate StudentYearLevel
                    if year and level:
                        StudentYearLevel.objects.get_or_create(
                            student=instance,
                            level=level,
                            year=year
                        )

                    # 9. Log it
                    if user:
                        UserStatusLog.objects.create(
                            user=user,
                            status='REACTIVATED',
                            reason=reason
                        )

                    reactivated_students.append(instance.id)

                return Response({
                    "message": "Students successfully reactivated.",
                    "student_ids": reactivated_students
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

