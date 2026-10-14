import django_filters as df
from .models import Admission



class AdmissionFilter(df.FilterSet):
    school_year = df.CharFilter(field_name="school_year__year_name", lookup_expr="iexact")
    year_level  = df.CharFilter(field_name="year_level__level_name",  lookup_expr="iexact")
    tc_letter   = df.CharFilter(lookup_expr="iexact")
    enrollment_no = df.CharFilter(lookup_expr="icontains")

    # Range filter
    min_percentage = df.NumberFilter(field_name="previous_percentage", lookup_expr="gte")
    max_percentage = df.NumberFilter(field_name="previous_percentage", lookup_expr="lte")
    date_after     = df.DateFilter(field_name="admission_date", lookup_expr="gte")
    date_before    = df.DateFilter(field_name="admission_date", lookup_expr="lte")

    # by name of guardian and student
    student_name  = df.CharFilter(method="filter_by_student_name")
    guardian_name = df.CharFilter(method="filter_by_guardian_name")
    
    
    

    def filter_by_student_name(self, qs, name, value):
        """Match first OR last name of the linked Student’s User record."""
        return qs.filter(
            student__user__first_name__icontains=value
        ) | qs.filter(
            student__user__last_name__icontains=value
        )

    def filter_by_guardian_name(self, qs, name, value):
        """Match first OR last name on Guardian."""
        return qs.filter(
            guardian__user__first_name__icontains=value
        ) | qs.filter(
            guardian__user__last_name__icontains=value
        )

    class Meta:
        model  = Admission
        fields = [
            "enrollment_no",
            "tc_letter",
            "school_year",
            "year_level",
            "student_name",
            "guardian_name",
            "emergency_contact_no",
            "min_percentage",
            "max_percentage",
            "date_after",
            "date_before",
        ]



