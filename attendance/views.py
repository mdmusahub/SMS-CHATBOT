from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import  *
from .serializers import *
from django.utils.dateformat import format as date_format
from datetime import date,datetime, timedelta
from django.db.models import Count, Q
from rest_framework.viewsets import ViewSet
from teacher.models import TeacherYearLevel
from student.models import Guardian,StudentGuardian, StudentYearLevel, Student
from django.shortcuts import get_object_or_404
import holidays
from director.views import send_whatsapp_message
from calendar import monthrange

#payload for MultipleAttendance
# {
#     "teacher": 1,
#     "year_level": 6,
#     "marked_at": "2025-09-24",
#     "P": [1],
#     "A": [104, 105],
#     "L": [106]
# }

class StudentAttendanceView(ModelViewSet):
    queryset = Attendance.objects.filter(student__isnull=False)
    serializer_class = StudentAttendanceSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data

        teacher = Teacher.objects.get(id=validated_data["teacher_id"])
        year_level_id = validated_data["year_level_id"]
        marked_at = validated_data.get("marked_at", date.today())

        allowed_statuses = {"P", "A", "L"}
        created_records = []
        absent_leave_students = []

        for status_code in allowed_statuses:
            for sid in validated_data.get(status_code, []):
                if not Student.objects.filter(id=sid, is_active=True).exists():
                    return Response(
                        {"error": f"Active student not found (ID: {sid})"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                student = Student.objects.get(id=sid, is_active=True)

                attendance = Attendance.objects.create(
                    student=student,
                    status=status_code,
                    marked_at=marked_at,
                    teacher=teacher,
                    year_level_id=year_level_id
                )

                created_records.append(attendance)

                if status_code in ["A", "L"]:
                    absent_leave_students.append(student)

        # WhatsApp Notification
        for student in absent_leave_students:
            student_name = f"{student.user.first_name} {student.user.last_name}"

            msg = (
                f"Dear Parent,\n\n"
                f"{student_name} was marked as Absent "
                f"on {marked_at.strftime('%d-%m-%Y')}.\n"
                f"Kindly ensure regular attendance.\n\n"
                f"Regards,\nSchool Management"
            )

            send_whatsapp_message(msg)

        return Response(
            StudentAttendanceSerializer(created_records, many=True).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        instance = self.get_object()  # gets by pk

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=True  # allows PATCH behavior
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def destroy(self, request, pk=None):
        instance = self.get_object()
        instance.delete()
        return Response(
            {"message": "Attendance deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )



class AttendanceReportViewSet(ReadOnlyModelViewSet):
    serializer_class = StudentAttendanceSerializer

    def get_queryset(self):
        queryset = Attendance.objects.select_related('student', 'year_level')

        class_name = self.request.query_params.get('class')
        month = self.request.query_params.get('month')
        year = self.request.query_params.get('year')
        guardian_id = self.request.query_params.get('guardian_id')
        student_id = self.request.query_params.get('student_id')

        # Filter by guardian_id
        if guardian_id:
            student_ids = StudentGuardian.objects.filter(
                guardian_id=guardian_id
            ).values_list('student_id', flat=True)
            queryset = queryset.filter(student_id__in=student_ids)

        # Filter by student_id (overrides guardian filter if both given)
        if student_id:
            queryset = queryset.filter(student_id=student_id)

        # Filter by class name
        if class_name:
            queryset = queryset.filter(year_level__level_name__iexact=class_name)

        # Filter by month and year
        if month and year:
            try:
                month = int(month)
                year = int(year)
                queryset = queryset.filter(
                    marked_at__month=month,
                    marked_at__year=year
                )
            except ValueError:
                return Attendance.objects.none()

        return queryset.order_by('student', 'marked_at')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        student_attendance_map = {}

        for record in queryset:
            student_id = record.student.id
            student_name = str(record.student)
            date_obj = record.marked_at
            # Format: 2/7/25 (Tuesday)
            date_str = date_format(date_obj, "j/n/y") + f" ({date_obj.strftime('%A')})"

            if student_id not in student_attendance_map:
                student_attendance_map[student_id] = {"Student name": student_name}

            student_attendance_map[student_id][date_str] = record.status

        final_data = list(student_attendance_map.values())
        return Response(final_data)

class DirectorAttendanceDashboard(ViewSet):
    def list(self, request):
        date_str = request.query_params.get("date")
        try:
            if date_str:
                marked_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            else:
                marked_date = date.today()              
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        # Step 2: Get attendance summary
        total_students = Student.objects.filter(is_active=True).count()
        present_today = Attendance.objects.filter(marked_at=marked_date, status='P').count()
        overall_percentage = (present_today / total_students * 100) if total_students else 0

        today = date.today()

        current_year = SchoolYear.objects.filter(
            start_date__lte=today,
            end_date__gte=today
        ).first()

        # Step 3: Class-wise breakdown
        class_wise_data = []
        all_classes = YearLevel.objects.all()

        for cls in all_classes:
            # Total students in this class (for current school year ideally)
            total_students_in_class = Student.objects.filter(
                is_active=True,
                student_year_levels__level=cls,
                student_year_levels__year=current_year
            ).distinct().count()

            # Present students in this class
            present_students = Attendance.objects.filter(
                marked_at=marked_date,
                status='P',
                student__student_year_levels__level=cls,
                student__student_year_levels__year=current_year
            ).distinct().count()

            percentage = (
                present_students / total_students_in_class * 100
                if total_students_in_class else 0
            )

            class_wise_data.append({
                "class_name": cls.level_name,
                "present": present_students,
                "total": total_students_in_class,
                "percentage": f"{percentage:.1f}%"
            })


        return Response({
            "date": marked_date.strftime("%Y-%m-%d"),
            "session":f"{current_year.start_date.year}-{current_year.end_date.year}",
            "overall_attendance": {
                "present": present_today,
                "total": total_students,
                "percentage": f"{overall_percentage:.1f}%"
            },
            "class_wise_attendance": class_wise_data
        })


class TeacherAttendanceDashboard(ViewSet):
    def list(self, request):
        # Get month & year from query params (or use today's values)
        today = date.today()
        month = int(request.query_params.get("month", today.month))
        year = int(request.query_params.get("year", today.year))

        class_name = request.query_params.get("class_name")

        student_levels = StudentYearLevel.objects.filter(student__is_active=True)

        if class_name:
            student_levels = student_levels.filter(level__level_name__iexact=class_name)

        result = []

        for syl in student_levels:
            if not syl.student:
                continue
            attendance_qs = Attendance.objects.filter(student=syl.student)

            # Monthly summary (filtered)
            monthly = attendance_qs.filter(marked_at__year=year, marked_at__month=month)
            m_present = monthly.filter(status='P').count()
            m_absent = monthly.filter(status='A').count()
            m_leave = monthly.filter(status='L').count()
            m_total = monthly.count()
            m_percentage = (m_present / m_total * 100) if m_total else 0.0

            # Yearly summary (filtered)
            yearly = attendance_qs.filter(marked_at__year=year)
            y_present = yearly.filter(status='P').count()
            y_absent = yearly.filter(status='A').count()
            y_leave = yearly.filter(status='L').count()
            y_total = yearly.count()
            y_percentage = (y_present / y_total * 100) if y_total else 0.0

            student_name = f"{syl.student.user.first_name} {syl.student.user.last_name}" if syl.student.user else "N/A"
            class_name_val = syl.level.level_name if syl.level else "N/A"

            result.append({
                "student_name": student_name,
                "class_name": class_name_val,
                "filter_month": month,
                "filter_year": year,
                "monthly_percentage": round(m_percentage, 1),
                "yearly_percentage": round(y_percentage, 1),
                "monthly_summary": {
                    "present": m_present,
                    "absent": m_absent,
                    "leave": m_leave,
                    "total_days": m_total
                },
                "yearly_summary": {
                    "present": y_present,
                    "absent": y_absent,
                    "leave": y_leave,
                    "total_days": y_total
                }
            })

        return Response(result)


class StudentOwnAttendanceViewSet(ViewSet):
    def list(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"detail": "Login required. Or use /student-dashboard/<student_id>/."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # assumes Student has a OneToOne to User named "user"
        student = get_object_or_404(Student, user=request.user)
        return self.retrieve(request, pk=student.id)
    
    def retrieve(self, request, pk=None):
        today = date.today()

        date_str = request.query_params.get("date")
        month = int(request.query_params.get("month", today.month))
        year = int(request.query_params.get("year", today.year))

        # ---- date parsing ----
        try:
            selected_date = (
                datetime.strptime(date_str, "%Y-%m-%d").date()
                if date_str else None
            )
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."},
                status=400
            )

        # ---- student ----
        student = get_object_or_404(Student, id=pk)
        attendance_qs = Attendance.objects.filter(student=student)

        # ---- latest class ----
        latest_attendance = attendance_qs.order_by("-marked_at").first()
        year_level_name = (
            latest_attendance.year_level.level_name
            if latest_attendance and latest_attendance.year_level
            else "N/A"
        )

        # ==================================================
        # DATE-WISE VIEW (if date is passed)
        # ==================================================
        if selected_date:
            day_qs = attendance_qs.filter(marked_at=selected_date)

            return Response({
                "student_name": f"{student.user.first_name} {student.user.last_name}",
                "year_level": year_level_name,
                "filter_date": selected_date.strftime("%Y-%m-%d"),
                "attendance": {
                    "present": day_qs.filter(status="P").count(),
                    "absent": day_qs.filter(status="A").count(),
                    "leave": day_qs.filter(status="L").count(),
                    "total": day_qs.count(),
                }
            })

        # ==================================================
        # MONTHLY SUMMARY
        # ==================================================
        monthly = attendance_qs.filter(marked_at__year=year, marked_at__month=month)
        m_present = monthly.filter(status='P').count()
        m_absent = monthly.filter(status='A').count()
        m_leave = monthly.filter(status='L').count()
        m_total = monthly.count()
        m_percentage = (m_present / m_total * 100) if m_total else 0.0

        # ==================================================
        # YEARLY SUMMARY
        # ==================================================
        yearly = attendance_qs.filter(marked_at__year=year)
        y_present = yearly.filter(status='P').count()
        y_absent = yearly.filter(status='A').count()
        y_leave = yearly.filter(status='L').count()
        y_total = yearly.count()
        y_percentage = (y_present / y_total * 100) if y_total else 0.0

        return Response({
            "student_name": f"{student.user.first_name} {student.user.last_name}",
            "year_level": year_level_name,
            "filter_month": month,
            "filter_year": year,
            "monthly_percentage": round(m_percentage, 1),
            "yearly_percentage": round(y_percentage, 1),
            "monthly_summary": {
                "present": m_present,
                "absent": m_absent,
                "leave": m_leave,
                "total_days": m_total
            },
            "yearly_summary": {
                "present": y_present,
                "absent": y_absent,
                "leave": y_leave,
                "total_days": y_total
            }
        })




class GuardianChildrenAttendanceViewSet(ViewSet):
    def list(self, request):
        guardian_id = request.query_params.get("guardian_id")
        if not guardian_id:
            return Response({"error": "guardian_id is required"}, status=400)

        try:
            guardian = Guardian.objects.get(id=guardian_id)
        except Guardian.DoesNotExist:
            return Response({"error": "Guardian not found"}, status=404)

        # Get optional month and year from query params
        today = date.today()
        month = int(request.query_params.get("month", today.month))
        year = int(request.query_params.get("year", today.year))

        student_links = StudentGuardian.objects.filter(guardian=guardian, student__is_active=True)
        children = [link.student for link in student_links if link.student]

        response_data = []

        for student in children:
            try:
                year_level = StudentYearLevel.objects.get(student=student)
            except StudentYearLevel.DoesNotExist:
                continue

            # Monthly
            monthly_qs = Attendance.objects.filter(
                student=student,
                marked_at__year=year,
                marked_at__month=month
            )
            m_total = monthly_qs.count()
            m_present = monthly_qs.filter(status='P').count()
            m_absent = monthly_qs.filter(status='A').count()
            m_leave = monthly_qs.filter(status='L').count()
            m_percent = round((m_present / m_total) * 100, 1) if m_total else 0.0

            # Yearly
            yearly_qs = Attendance.objects.filter(
                student=student,
                marked_at__year=year
            )
            y_total = yearly_qs.count()
            y_present = yearly_qs.filter(status='P').count()
            y_absent = yearly_qs.filter(status='A').count()
            y_leave = yearly_qs.filter(status='L').count()
            y_percent = round((y_present / y_total) * 100, 1) if y_total else 0.0

            student_name = f"{student.user.first_name} {student.user.last_name}" if student.user else "N/A"
            response_data.append({
                'student_name': student_name,
                'class_name': year_level.level.level_name if year_level and year_level.level else "N/A",
                'monthly_summary': {
                    "month": month,
                    "present": m_present,
                    "absent": m_absent,
                    "leave": m_leave,
                    "total_days": m_total,
                    "percentage": f"{m_percent}%"
                },
                'yearly_summary': {
                    "year": year,
                    "present": y_present,
                    "absent": y_absent,
                    "leave": y_leave,
                    "total_days": y_total,
                    "percentage": f"{y_percent}%"
                }
            })

        return Response({
            "guardian_id": guardian.id,
            "filter_month": month,
            "filter_year": year,
            "total_children": len(response_data),
            "children": response_data
        })
   
    
    
class TeacherYearLevelList(APIView):
    def get(self, request, teacher_id):
        levels = TeacherYearLevel.objects.filter(teacher_id=teacher_id).select_related('year_level')
        data = [
            {
                "teacher_year_level_id": l.id,  # This is the ID of the relation record
                "year_level_id": l.year_level.id,
                "year_level_name": str(l.year_level)
            }
            for l in levels
        ]
        return Response(data)

        #------------- was creating numerous entries-------24/09/25--------------


class FetchIndianHolidaysView(APIView):

    def get(self, request, *args, **kwargs):
        year = request.query_params.get('year')

        if not year or not str(year).isdigit():
            return Response({'error': 'Please provide a valid year (e.g., ?year=2025)'}, status=400)

        year = int(year)
        holidays_qs = SchoolHoliday.objects.filter(date__year=year).order_by('date')
        serializer = SchoolHolidaySerializer(holidays_qs, many=True)

        return Response({
            "year": year,
            "total": holidays_qs.count(),
            "holidays": serializer.data
        }, status=200)

    def post(self, request, *args, **kwargs):
        year = request.data.get('year')

        if not year or not str(year).isdigit():
            return Response(
                {'error': 'Please provide a valid year (e.g., { "year": 2025 })'},
                status=status.HTTP_400_BAD_REQUEST
            )

        year = int(year)
        india_holidays = holidays.India(years=year)
        created, skipped = 0, 0

        for date, name in india_holidays.items():
            if not SchoolHoliday.objects.filter(date=date).exists():
                SchoolHoliday.objects.create(
                    title=name,
                    date=date,
                    description=name
                )
                created += 1
            else:
                skipped += 1

        return Response({
            "message": f"{created} holidays added, {skipped} already existed.",
            "year": year
        }, status=status.HTTP_201_CREATED)
        
class SchoolEventViewSet(ModelViewSet):
    queryset = SchoolEvent.objects.all().order_by('start_date')
    serializer_class = SchoolEventSerializer

    def perform_create(self, serializer):
        # Save the new event
        event = serializer.save()



        # Prepare message
        message_text = (
            f"📅 New School Event: {event.title}\n"
            f"🗓 From {event.start_date} to {event.end_date}\n"
            f"📍 Location: {event.location if hasattr(event, 'location') else 'School Campus'}\n"
            f"Details: {event.description if hasattr(event, 'description') else 'No additional details'}"
        )


        send_whatsapp_message(message_text)

    
class MonthlyCalendarView(APIView):
    def get(self, request, *args, **kwargs):
        month = request.query_params.get('month')
        year = request.query_params.get('year')

        if not month or not year or not month.isdigit() or not year.isdigit():
            return Response(
                {"error": "Please provide valid month and year. Example: ?month=10&year=2025"},
                status=status.HTTP_400_BAD_REQUEST
            )

        month = int(month)
        year = int(year)

        # School holidays (single-day)
        school_holidays = SchoolHoliday.objects.filter(
            date__month=month, date__year=year
        ).order_by('date')
        school_holiday_data = SchoolHolidaySerializer(school_holidays, many=True).data

        # Multi-day holidays overlapping this month
        start_of_month = f"{year}-{month:02d}-01"
        end_of_month = f"{year}-{month:02d}-{monthrange(year, month)[1]}"
        holidays = Holiday.objects.filter(
            Q(start_date__lte=end_of_month) & Q(end_date__gte=start_of_month)
        ).order_by('-start_date')
        holiday_data = HolidaySerializer(holidays, many=True).data

        # School events
        events = SchoolEvent.objects.filter(
            start_date__year=year,
            start_date__month=month
        ).order_by('start_date')
        event_data = SchoolEventSerializer(events, many=True).data

        return Response({
            "year": year,
            "month": month,
            "school_holidays": school_holiday_data,
            "custom_holidays": holiday_data,
            "events": event_data
        }, status=status.HTTP_200_OK)
        
##-------------------------Whatsapp Message---------------------------
from twilio.rest import Client

class SendWhatsAppView(APIView):
    def post(self, request):
        account_sid = 'AC75f0880296f2c1377b2ca30442bbd3e1'
        auth_token = '01dfff8731923c8e91e47b469f533fd5'
        twilio_whatsapp_number = 'whatsapp:+14155238886'

        client = Client(account_sid, auth_token)

        verified_numbers = [
            '+918102637122',
            '+918109145639'
            #'+919111499689'
        ]

        message_text = " This message is sent from Mecaps SMS Dev Team."

        sent_messages = []

        for number in verified_numbers:
            try:
                message = client.messages.create(
                    from_=twilio_whatsapp_number,
                    body=message_text,
                    to=f'whatsapp:{number}'
                )
                sent_messages.append({
                    "to": number,
                    "sid": message.sid,
                    "status": "sent"
                })
            except Exception as e:
                sent_messages.append({
                    "to": number,
                    "error": str(e),
                    "status": "failed"
                })

        return Response({"results": sent_messages}, status=status.HTTP_200_OK)


class HolidayViewSet(ModelViewSet):
    queryset = Holiday.objects.all().order_by("-start_date")
    serializer_class = HolidaySerializer




class OfficeStaffAttendanceView(ModelViewSet):
    queryset = Attendance.objects.filter(
        office_staff__isnull=False,
        student__isnull=True,
        teacher__isnull=True
    )

    serializer_class = OfficeStaffAttendanceSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data

        marked_at = validated_data["marked_at"]
        present_ids = validated_data.get("P", [])
        absent_ids = validated_data.get("A", [])
        leave_ids = validated_data.get("L", [])

        created_records = []

        for status_code, staff_ids in {
            "P": present_ids,
            "A": absent_ids,
            "L": leave_ids,
        }.items():

            for sid in staff_ids:
                attendance = Attendance.objects.create(
                    office_staff_id=sid,
                    status=status_code,
                    marked_at=marked_at
                )

                created_records.append(attendance)

        return Response(
            {
                "message": "Office staff attendance marked successfully.",
                "count": len(created_records)
            },
            status=status.HTTP_201_CREATED
        )

    def update(self, request, pk=None):
        instance = self.get_object()  # gets by pk

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=True  # allows PATCH behavior
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def destroy(self, request, pk=None):
        instance = self.get_object()
        instance.delete()
        return Response(
            {"message": "Attendance deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )




class TeacherAttendanceView(ModelViewSet):
    queryset = Attendance.objects.filter(
        teacher__isnull=False,
        student__isnull=True,
        office_staff__isnull=True
    )
    serializer_class = TeacherAttendanceSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data

        marked_at = validated_data["marked_at"]
        present_ids = validated_data.get("P", [])
        absent_ids = validated_data.get("A", [])
        leave_ids = validated_data.get("L", [])

        created_records = []

        for status_code, teacher_ids in {
            "P": present_ids,
            "A": absent_ids,
            "L": leave_ids,
        }.items():

            for tid in teacher_ids:
                attendance = Attendance.objects.create(
                    teacher_id=tid,
                    status=status_code,
                    marked_at=marked_at
                )

                created_records.append(attendance)

        return Response(
            {
                "message": "Teacher attendance marked successfully.",
                "count": len(created_records)
            },
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        instance = self.get_object()  # gets by pk

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=True  # allows PATCH behavior
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def destroy(self, request, pk=None):
        instance = self.get_object()
        instance.delete()
        return Response(
            {"message": "Attendance deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )




