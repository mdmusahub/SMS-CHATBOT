from django.db import models
from director.models import *
from student.models import Student
from teacher.models import *
from django.db.models import Q
from django.core.exceptions import ValidationError


class Holiday(models.Model):
    title = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        if self.start_date == self.end_date:
            return f"{self.title} ({self.start_date})"
        return f"{self.title} ({self.start_date} to {self.end_date})"


class Attendance(models.Model):
    STATUS_CHOICES = [('P', 'Present'), ('A', 'Absent'), ('L', 'Leave')]

    student = models.ForeignKey(Student,on_delete=models.CASCADE,null=True,blank=True)
    teacher = models.ForeignKey(Teacher,on_delete=models.CASCADE,null=True,blank=True)
    office_staff = models.ForeignKey(OfficeStaff,on_delete=models.CASCADE,null=True,blank=True)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES)
    marked_at = models.DateField()
    year_level = models.ForeignKey(YearLevel, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        if self.student:
            role = "student"
            person = self.student
        elif self.teacher:
            role = "teacher"
            person = self.teacher
        else:
            role = "office staff"
            person = self.office_staff

        return f"{role}: {person} - {self.marked_at} - {self.get_status_display()}"


    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'marked_at'],
                condition=Q(student__isnull=False),
                name='unique_student_attendance'
            ),
            models.UniqueConstraint(
                fields=['teacher', 'marked_at'],
                condition=Q(teacher__isnull=False) & Q(student__isnull=True),
                name='unique_teacher_attendance'
            ),
            models.UniqueConstraint(
                fields=['office_staff', 'marked_at'],
                condition=Q(office_staff__isnull=False),
                name='unique_staff_attendance'
            ),
        ]


class SchoolHoliday(models.Model):
    title = models.CharField(max_length=100)
    date = models.DateField()
    description = models.TextField(blank=True, null=True)
    

    def __str__(self):
        return f"{self.title} {self.date}  {self.description}"
   
class SchoolEvent(models.Model):
    title = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.title} ({self.start_date} to {self.end_date})"

