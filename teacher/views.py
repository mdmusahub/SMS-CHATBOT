from urllib import request
from django.shortcuts import render

# Create your views here.
from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response

from attendance.models import Attendance, SchoolHoliday

from .models import Teacher,TeacherYearLevel
from .serializers import *
# from .serializers import TeacherSerializer
from rest_framework import filters
from rest_framework.filters import SearchFilter
from rest_framework.decorators import action
from director.models import *
from django.db.models import Prefetch
from rest_framework.permissions import AllowAny, IsAuthenticated,BasePermission
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from director.views import send_whatsapp_message 
# from permission import RoleBasedPermission
from attendance.views import Holiday
from director.utils import send_email_notification
from django.db import transaction


from collections import defaultdict
from datetime import datetime
from rest_framework.views import APIView
from rest_framework import status
from django.utils import timezone


class IsDirector(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (
            request.user.is_staff or request.user.is_superuser
        )



class TeacherView(viewsets.ModelViewSet):
    queryset = Teacher.objects.filter(is_active=True)
    serializer_class = TeacherSerializer


    filter_backends = [filters.SearchFilter]
    search_fields = ['user__email', 'user__first_name', 'phone_no']
    
    # ***************with out JWT******************
    # def get_permissions(self):
    #     if self.action in ['assign_teacher_details', 'get_all_teacher_assignments']:
    #         return [IsAuthenticated(), IsDirector()]
    #     elif self.action in ['list', 'create', 'retrieve','update', 'partial_update']:
    #         return [AllowAny()]
    #     return [IsAuthenticated()]

    


    
    @action(detail=False, methods=['post'], url_path='assign-teacher-details')
    def assign_teacher_details(self, request):
        teacher_id = request.data.get("teacher_id")
        yearlevel_id = request.data.get("yearlevel_id")
        subject_ids = request.data.get("subject_ids", [])
        period_ids = request.data.get("period_ids", [])
        term_id = request.data.get("term_id")
        classroom_id = request.data.get("classroom_id")


        errors = []
        assigned = []
        to_create = []

        # ---- basic validations ----
        if not teacher_id:
            return Response({"error": "teacher_id is required."}, status=400)

        if not yearlevel_id:
            return Response({"error": "yearlevel_id is required."}, status=400)

        if not subject_ids:
            return Response({"error": "At least one subject_id is required."}, status=400)

        if not period_ids:
            return Response({"error": "At least one period_id is required."}, status=400)

        if len(subject_ids) != len(period_ids):
            return Response(
                {"error": "subject_ids and period_ids length must be equal."},
                status=400
            )
        
        if not term_id:
            return Response({"error": "term_id is required."}, status=400)

        if not classroom_id:
            return Response({"error": "classroom_id is required."}, status=400)

        term = Term.objects.filter(id=term_id).first()
        if not term:
            return Response({"error": "Invalid term_id."}, status=404)

        classroom = ClassRoom.objects.filter(id=classroom_id).first()
        if not classroom:
            return Response({"error": "Invalid classroom_id."}, status=404)


        # ---- fetch main objects ----
        teacher = Teacher.objects.filter(id=teacher_id).first()
        if not teacher:
            return Response({"error": "Invalid teacher_id."}, status=404)

        yearlevel = YearLevel.objects.filter(id=yearlevel_id).first()
        if not yearlevel:
            return Response({"error": "Invalid yearlevel_id."}, status=404)

        subjects = list(Subject.objects.filter(id__in=subject_ids))
        if len(subjects) != len(subject_ids):
            return Response({"error": "One or more invalid subject_ids."}, status=400)

        periods = list(Period.objects.filter(id__in=period_ids))
        if len(periods) != len(period_ids):
            return Response({"error": "One or more invalid period_ids."}, status=400)

        # ---- load limit check ----
        if ClassPeriod.objects.filter(teacher=teacher).count() + len(subjects) > 6:
            return Response(
                {"error": "Teacher cannot be assigned more than 6 periods."},
                status=400
            )

        # ---- main logic ----
        for subject, period in zip(subjects, periods):

            # duplicate check (class + period)
            # ---- teacher time conflict check ----
            if ClassPeriod.objects.filter(
                year_level=yearlevel,
                term=term,
                start_time__start_period_time=period.start_period_time,
                end_time__end_period_time=period.end_period_time
            ).exists():
                errors.append(
                    f"{yearlevel.level_name} already has a class scheduled "
                    f"on {period.name} ({period.start_period_time}-{period.end_period_time})."
                )
                continue

            if ClassPeriod.objects.filter(
                classroom=classroom,
                term=term,
            ).filter(
                start_time__start_period_time=period.start_period_time,
                end_time__end_period_time=period.end_period_time
            ).exists():
                errors.append(
                    f"Classroom {classroom.room_name} is already occupied "
                    f"on {period.name} ({period.start_period_time}-{period.end_period_time})."
                )
                continue

            if ClassPeriod.objects.filter(teacher=teacher).filter(
                start_time__start_period_time=period.start_period_time,
                end_time__end_period_time=period.end_period_time
            ).exists():
                errors.append(
                    f"Teacher {teacher.user.first_name} {teacher.user.last_name} "
                    f"is already assigned to another class on {period.name} "
                    f"({period.start_period_time}-{period.end_period_time})."
                )
                continue

            if ClassPeriod.objects.filter(year_level=yearlevel, term=term, start_time_id=period.id).exists():
                return Response({"error": f"{yearlevel.level_name} already has a class assigned for {period.name}."}
                                ,status=400)

            to_create.append(ClassPeriod(
                teacher=teacher,
                subject=subject,
                year_level=yearlevel,
                start_time=period,
                end_time=period,
                term=term,
                classroom=classroom,
                name=f"{subject.subject_name} - {period.name}"
            ))

            assigned.append({
                "subject": subject.subject_name,
                "period": period.name
            })

        # ---- final checks ----
        if errors:
            return Response({"errors": errors}, status=400)

        if not to_create:
            return Response(
                {"error": "No assignments could be created."},
                status=400
            )

        # ---- save ----
        with transaction.atomic():
            ClassPeriod.objects.bulk_create(to_create)

        return Response({
            "message": "Teacher assigned successfully.",
            "teacher": f"{teacher.user.first_name} {teacher.user.last_name}",
            "year_level": yearlevel.level_name,
            "assigned_subjects_periods": assigned
        }, status=200)
   
   
    
    @action(detail=False, methods=['get'], url_path='all-teacher-assignments')
    def get_all_teacher_assignments(self, request):
        from django.db.models import Prefetch
    
        teachers = Teacher.objects.filter(is_active=True).prefetch_related(
            'year_levels',
            Prefetch(
                'assigned_periods',
                queryset=ClassPeriod.objects.select_related(
                    'subject', 'start_time', 'end_time', 'classroom', 'classroom__room_type'
                ).order_by('start_time__start_period_time')
            )
        ).select_related('user')
    
        response_data = []
    
        for teacher in teachers:
            # Step 1: Build yearlevel map
            yearlevel_map = {
                yl.id: {
                    "year_level_id": yl.id,
                    "year_level_name": yl.level_name,
                    "periods": []
                }
                for yl in teacher.year_levels.all()
            }
            # if teacher got no year level, make a fallback bucket
            if not yearlevel_map:
                yearlevel_map["unassigned"] = {
                    "year_level_id": None,
                    "year_level_name": "Unassigned class",
                    "periods": []
                }
            year_level_ids = list(yearlevel_map.keys())
    
            # Step 2: Assign each period in sorted order (round-robin year_levels)
            index = 0
            for period in teacher.assigned_periods.all():
                assigned_year_level_id = year_level_ids[index % len(year_level_ids)]
                yearlevel_map[assigned_year_level_id]["periods"].append({
                    'period_id': period.id,
                    'period_name': period.name,
                    'start_time': period.start_time.start_period_time.strftime("%H:%M") if period.start_time else None,
                    'end_time': period.end_time.end_period_time.strftime("%H:%M") if period.end_time else None,
                    'subject_id': period.subject.id if period.subject else None,
                    'subject_name': period.subject.subject_name if period.subject else None,
                    'class_id': period.classroom.id if period.classroom else None,
                    'class_name': period.classroom.room_name if period.classroom else None,
                    'class_type': period.classroom.room_type.name if period.classroom and period.classroom.room_type else None,
                    'year_level_id': period.year_level_id,
                    'year_level_name': period.year_level.level_name if period.year_level else None
                })
                index += 1
    
            # Step 3: Build teacher assignment response
            teacher_name = teacher.user.get_full_name() if teacher.user else str(teacher)
            response_data.append({
                'teacher_id': teacher.id,
                'teacher_name': teacher_name,
                'total_assigned_periods': teacher.assigned_periods.count(),
                'max_periods_allowed': 6,
                'assignments': list(yearlevel_map.values())
            })
    
        return Response(response_data, status=status.HTTP_200_OK)
    
    

    






    
    
    # ********************Jwt get/PUT***************
    @action(detail=False, methods=['get', 'put', 'patch'], url_path='teacher_my_profile', permission_classes=[IsAuthenticated])
    def teacher_my_profile(self, request):
        user = request.user

        try:
            teacher = Teacher.objects.get(user=user)
        except Teacher.DoesNotExist:
            return Response({"error": "Teacher profile not found for this user."}, status=status.HTTP_404_NOT_FOUND)

        if request.method in ['PUT', 'PATCH']:
            partial = request.method == 'PATCH'
            serializer = self.get_serializer(teacher, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response({"success": "Teacher profile updated successfully", "data": serializer.data}, status=status.HTTP_200_OK)

        serializer = self.get_serializer(teacher)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    

from .serializers import TeacherYearLevelSerializer
from director.permission import RoleBasedPermissionteacheryearlevel

class TeacherYearLevelView(viewsets.ModelViewSet):
    serializer_class = TeacherYearLevelSerializer
    queryset = TeacherYearLevel.objects.filter(teacher__is_active=True)
    permission_classes = [ RoleBasedPermissionteacheryearlevel]

    def get_queryset(self):
        # Permission class ke filter_queryset() ka use karo
        return self.permission_classes[0]().filter_queryset(self.request, super().get_queryset(), self)

    def get(self, request, *args, **kwargs):
        # Check if the token is present in the request
        if not request.META.get('HTTP_AUTHORIZATION'):
            return Response({"detail": "Token not given"}, status=status.HTTP_401_UNAUTHORIZED)
        
        # If token is present, proceed with the normal get method
        return super().get(request, *args, **kwargs)





class AllTeachersWithYearLevelsAPIView(APIView):
    def get(self, request):
        date_value = request.GET.get('date_value')
        try:
            target_date = datetime.strptime(date_value, "%Y-%m-%d").date() if date_value else timezone.now().date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        filter_status = request.GET.get('status', 'all').lower()
        if filter_status not in ['present', 'absent', 'all']:
            return Response({"error": "Invalid status filter"}, status=status.HTTP_400_BAD_REQUEST)

        teacher_id = request.GET.get('teacher_id')
        teachers = Teacher.objects.filter(is_active=True).select_related('user')

        if teacher_id:
            teachers = teachers.filter(id=teacher_id)
            if not teachers.exists():
                return Response({"error": "Teacher not found"}, status=status.HTTP_404_NOT_FOUND)

        result = []

        for teacher in teachers:
            attendance = Attendance.objects.filter(teacher=teacher,marked_at=target_date).first()
            attendance_status = (attendance.get_status_display().lower()if attendance else "not marked")

            if filter_status != 'all':
                if attendance_status == "not marked":
                    continue
                if attendance_status != filter_status:
                    continue

            #  Fetch all periods assigned to this teacher
            periods = ClassPeriod.objects.filter(teacher=teacher).select_related(
                'subject', 'year_level', 'start_time'
            ).order_by('year_level__id', 'start_time')

            # Group periods by year_level
            grouped = defaultdict(list)
            for p in periods:
                grouped[p.year_level].append({
                    "id": p.id,
                    "name": getattr(p.start_time, "name", p.start_time.strftime("%H:%M") if hasattr(p.start_time, "strftime") else None),
                    "subject": p.subject.subject_name if p.subject else None
                })

            year_level_data = [
                {
                    "id": yl.id,
                    "level_name": yl.level_name,
                    "periods": grouped[yl]
                }
                for yl in grouped.keys()
            ]

            result.append({
                'id': teacher.id,
                'first_name': teacher.user.first_name if teacher.user else "",
                'last_name': teacher.user.last_name if teacher.user else "",
                'email': teacher.user.email if teacher.user else "",
                'phone_no': teacher.phone_no,
                'year_levels': year_level_data,
                'attendance': {'date': str(target_date), 'status': attendance_status},
            })

        return Response({"count": len(result), "teachers": result}, status=status.HTTP_200_OK)



class AbsentTeacherFreeReplacementAPIView(APIView):
    def get(self, request):
        date_value = request.GET.get("date_value")
        teacher_id = request.GET.get("teacher_id")

        # ---- date handling ----
        try:
            target_date = (
                datetime.strptime(date_value, "%Y-%m-%d").date()
                if date_value else timezone.now().date()
            )
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ---- attendance sets ----
        absent_ids = set(
            Attendance.objects.filter(
                marked_at=target_date,
                status="A"
            ).values_list("teacher_id", flat=True)
        )

        leave_ids = set(
            Attendance.objects.filter(
                marked_at=target_date,
                status="L"
            ).values_list("teacher_id", flat=True)
        )

        present_ids = set(
            Attendance.objects.filter(
                marked_at=target_date,
                status="P"
            ).values_list("teacher_id", flat=True)
        )

        # ---- inactive = absent + leave ----
        inactive_ids = absent_ids | leave_ids

        # ---- fetch inactive teachers having periods ----
        inactive_teachers_qs = Teacher.objects.filter(
            id__in=inactive_ids,
            assigned_periods__isnull=False,
            is_active=True
        ).distinct().select_related("user")

        if teacher_id:
            inactive_teachers_qs = inactive_teachers_qs.filter(id=teacher_id)

        if not inactive_teachers_qs.exists():
            return Response({"absent_teachers": []}, status=status.HTTP_200_OK)

        result = []

        for teacher in inactive_teachers_qs:
            teacher_status = "leave" if teacher.id in leave_ids else "absent"

            # ---- periods of inactive teacher ----
            periods = (
                ClassPeriod.objects
                .filter(teacher=teacher)
                .select_related("subject", "start_time", "year_level")
                .order_by("start_time")
            )

            period_data = []

            for p in periods:
                # ---- teachers already busy in same time slot ----
                busy_teacher_ids = set(
                    ClassPeriod.objects.filter(
                        start_time=p.start_time
                    ).values_list("teacher_id", flat=True)
                )

                # ---- free teachers = present - busy - inactive ----
                candidate_ids = present_ids - busy_teacher_ids - inactive_ids

                # ---- same class teachers ----
                same_class_teacher_ids = set(
                    ClassPeriod.objects.filter(
                        year_level=p.year_level
                    ).values_list("teacher_id", flat=True)
                )

                same_class_free_ids = candidate_ids & same_class_teacher_ids
                other_class_free_ids = candidate_ids - same_class_free_ids

                same_class_teachers_qs = (
                    Teacher.objects.filter(id__in=same_class_free_ids, is_active=True)
                    .select_related("user")
                    .order_by("user__first_name", "user__last_name")
                )

                other_teachers_qs = (
                    Teacher.objects.filter(id__in=other_class_free_ids, is_active=True)
                    .select_related("user")
                    .order_by("user__first_name", "user__last_name")
                )

                same_class_free_teachers = [
                    {
                        "id": t.id,
                        "first_name": t.user.first_name if t.user else "",
                        "last_name": t.user.last_name if t.user else "",
                        "email": t.user.email if t.user else "",
                    }
                    for t in same_class_teachers_qs
                ]

                other_class_free_teachers = [
                    {
                        "id": t.id,
                        "first_name": t.user.first_name if t.user else "",
                        "last_name": t.user.last_name if t.user else "",
                        "email": t.user.email if t.user else "",
                    }
                    for t in other_teachers_qs
                ]

                all_free_teachers = (
                    same_class_free_teachers + other_class_free_teachers
                )

                sub_assignment = (
                    SubstituteAssignment.objects
                    .filter(
                        absent_teacher=teacher,
                        period=str(p.id),   
                        date=target_date
                    )
                    .select_related("substitute_teacher__user")
                    .first()
                )

                substitute_teacher_data = None

                if sub_assignment:
                    sub_teacher = sub_assignment.substitute_teacher
                    substitute_teacher_data = {
                        "id": sub_teacher.id,
                        "name": f"{sub_teacher.user.first_name} {sub_teacher.user.last_name}".strip() if sub_teacher.user else "",
                        "email": sub_teacher.user.email if sub_teacher.user else "",
                    }


                period_data.append({
                    "period_id": p.id,
                    "period_name": getattr(p.start_time, "name", str(p.start_time)),
                    "subject": p.subject.subject_name if p.subject else None,
                    "year_level": p.year_level.level_name if p.year_level else None,
                    "same_class_free_teachers": same_class_free_teachers,
                    "other_class_free_teachers": other_class_free_teachers,
                    "all_free_teachers": all_free_teachers,
                })

            teacher_name = f"{teacher.user.first_name} {teacher.user.last_name}".strip() if teacher.user else str(teacher)
            result.append({
                "absent_teacher": {
                    "id": teacher.id,
                    "name": teacher_name,
                    "email": teacher.user.email if teacher.user else "",
                    "status": teacher_status,
                    "substitute_teacher": substitute_teacher_data,
                },
                "periods": period_data
            })

        return Response({"absent_teachers": result}, status=status.HTTP_200_OK)



class SubstituteAssignmentView(APIView):
    def get(self, request):
        assignments = SubstituteAssignment.objects.all()
        serializer = SubstituteAssignmentSerializer(assignments, many=True)
        return Response(serializer.data)

    def post(self, request):
        data = request.data

        # normalize input
        if isinstance(data, dict):
            data = [data]

        serializer = SubstituteAssignmentSerializer(data=data, many=True)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        assignments = serializer.save()

        # notifications
        def notify(assignment):
            subject = "Substitute Teacher Assignment"
            message = (
                f"Dear Teacher,\n\n"
                f"On {assignment.date}, during {assignment.period},\n"
                f"{assignment.absent_teacher} is absent.\n"
                f"Substitute assigned: {assignment.substitute_teacher}.\n\n"
                f"Regards,\nSchool Admin"
            )

            if assignment.absent_teacher.user.email:
                send_email_notification(
                    assignment.absent_teacher.user.email, subject, message
                )

            if assignment.substitute_teacher.user.email:
                send_email_notification(
                    assignment.substitute_teacher.user.email, subject, message
                )

            send_whatsapp_message(message)

        for assignment in assignments:
            notify(assignment)

        return Response(
            {
                "assignments": SubstituteAssignmentSerializer(assignments, many=True).data,
                "message": "Substitute assignment(s) created successfully",
            },
            status=status.HTTP_201_CREATED
        )
