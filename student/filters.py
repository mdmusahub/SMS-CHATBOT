
import django_filters as df
from .models import Student

class StudentFilter(df.FilterSet):
    gender         = df.CharFilter(lookup_expr="iexact")
    religion       = df.CharFilter(lookup_expr="iexact")
    category       = df.CharFilter(lookup_expr="iexact")          
    blood_group    = df.CharFilter(lookup_expr="iexact")
    scholar_number = df.CharFilter(lookup_expr="icontains")
    roll_number    = df.CharFilter(lookup_expr="icontains")
    contact_number = df.CharFilter(lookup_expr="icontains")
    aadhaar_number = df.CharFilter(lookup_expr="icontains")
    FMID_number = df.CharFilter(lookup_expr="icontains")
    apaar_number = df.CharFilter(lookup_expr="icontains")
    PEN_number = df.CharFilter(lookup_expr="icontains")
    BPL_number = df.CharFilter(lookup_expr="icontains")
    SSSMID = df.CharFilter(lookup_expr="icontains")

    # Range filters
    min_height     = df.NumberFilter(field_name="height", lookup_expr="gte")
    max_height     = df.NumberFilter(field_name="height", lookup_expr="lte")
    min_weight     = df.NumberFilter(field_name="weight", lookup_expr="gte")
    max_weight     = df.NumberFilter(field_name="weight", lookup_expr="lte")
    dob_after      = df.DateFilter(field_name="date_of_birth", lookup_expr="gte")
    dob_before     = df.DateFilter(field_name="date_of_birth", lookup_expr="lte")

    # Name search
    name           = df.CharFilter(method="filter_by_name")

    def filter_by_name(self, qs, _, value):
        return (qs.filter(user__first_name__icontains=value) | 
               qs.filter(user__last_name__icontains=value))

    class Meta:
        model  = Student
        fields = [
            "gender",
            "religion",
            "category",
            "blood_group",
            "scholar_number",
            "roll_number",
            "contact_number",
            "aadhaar_number",
            "FMID_number",
            "apaar_number",
            "PEN_number",
            "BPL_number",
            "SSSMID",
        ]
