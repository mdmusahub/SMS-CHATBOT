from django.db import models
from authentication.models import User

# from director.models import YearLevel


# Create your models here.

class TeacherManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)
    
    def all_including_inactive(self):
        return super().get_queryset()
    
class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.DO_NOTHING)
    phone_no = models.CharField(max_length=15,null=True,blank=True)
    gender = models.CharField(max_length=10,null=True,blank=True)
    adhaar_no = models.BigIntegerField(null=True,blank=True,unique=True)
    pan_no = models.CharField(max_length=20,null=True,blank=True,unique=True)
    qualification = models.CharField(max_length=250,null=True,blank=True)
    joining_date = models.DateField(auto_now_add=True,null=True,blank=True)  #added as of 19Sep25 at 03:00 PM
    is_active = models.BooleanField(default=True)
    cadre = models.CharField(max_length=10, null=True, blank=True)
    subject = models.ForeignKey(
        'director.Subject',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='subject_id',
        related_name='teachers',
    )

    year_levels = models.ManyToManyField('director.YearLevel', through='TeacherYearLevel')
    
    objects = TeacherManager()
    def __str__(self):
        return f'{self.user.first_name}  {self.user.last_name}'
    class Meta:
        db_table = "teacher"
        indexes = [models.Index(fields=['is_active'])]
    
class TeacherYearLevel(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    year_level = models.ForeignKey('director.YearLevel', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('teacher', 'year_level')

    def __str__(self):  
        return f"{self.teacher} - {self.year_level}"   






class SubstituteAssignment(models.Model):
    absent_teacher = models.ForeignKey(Teacher, related_name='absent_assignments', on_delete=models.CASCADE)
    substitute_teacher = models.ForeignKey(Teacher, related_name='substitute_assignments', on_delete=models.CASCADE)
    year_level = models.ForeignKey('director.YearLevel', on_delete=models.CASCADE)
    period = models.CharField(max_length=100)
    date = models.DateField(auto_now_add=True)


class TeacherAttendance(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    date = models.DateField()
    status = models.CharField(
        max_length=10,
        choices=[('present', 'Present'), ('absent', 'Absent'), ('leave', 'Leave')],
    )

    class Meta:
        unique_together = ('teacher', 'date')