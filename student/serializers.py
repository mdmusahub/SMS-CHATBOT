from rest_framework import serializers

from authentication.models import User
from director.models import Address, City, Country, Role, ClassPeriod, State
# from director.serializers import BankingDetailsSerializer
from .models import GuardianType, Student, StudentGuardian,StudentYearLevel
from director.models import ClassPeriod, YearLevel



from django.db import IntegrityError
from django.core.exceptions import MultipleObjectsReturned

from .models import Guardian
from director.models import BankingDetail
from django.contrib.auth import get_user_model
from director.models import DocumentType, Document, Address, Admission,File,SchoolYear


class GuardianTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuardianType
        fields = "__all__"
        




# ***********************new*********************
from django.core.validators import RegexValidator

class StudentSerializer(serializers.ModelSerializer):
    # User fields (write-only)
    first_name = serializers.CharField(max_length=100, write_only=True)
    middle_name = serializers.CharField(max_length=100, write_only=True, required=False, allow_blank=True)
    # last_name = serializers.CharField(max_length=100, write_only=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(max_length=100, write_only=True, required=False)
    user_profile = serializers.ImageField(required=False, allow_null=True, write_only=True)

    # Student model fields
    father_name = serializers.CharField(required=False, allow_null=True)
    mother_name = serializers.CharField(required=False, allow_null=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(
        choices=[('Male','Male'),('Female','Female'),('Other','Other')],
        required=False,
        error_messages={"invalid_choice": "Gender must be Male, Female, or Other."}
    )    
    religion = serializers.CharField(required=False, allow_null=True)
    category = serializers.ChoiceField(
        choices=[('SC', 'Scheduled Caste'), ('ST', 'Scheduled Tribe'), ('OBC', 'Other Backward Class'), ('GEN', 'General')],
        default='GEN'
    )
    height = serializers.FloatField(required=False, allow_null=True)
    weight = serializers.FloatField(required=False, allow_null=True)
    blood_group = serializers.CharField(required=False, allow_null=True)
    number_of_siblings = serializers.IntegerField(required=False,allow_null=True,min_value=0,max_value=15,
                                                  error_messages={"max_value": "Max 15 siblings allowed","invalid": "Enter a valid number."})
    roll_number = serializers.CharField(required=False, allow_null=True) 
    contact_number = serializers.CharField(
        required=False,
        allow_blank=True,
        validators=[
            RegexValidator(
                regex=r'^\+?(\d[\s-]?){10,15}$',
                message="Enter a valid contact number (10-15 digits, optional + at start)."
            )
        ]
    )
    scholar_number = serializers.CharField(required=False,allow_null=True)  
    aadhaar_number = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=20)
    FMID_number = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=20)
    apaar_number = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=14)
    PEN_number = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=20)
    BPL_number = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=20)
    SSSMID = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=20)

    # department_id = serializers.SerializerMethodField()
    # department_name = serializers.SerializerMethodField()

    # Classes many-to-many
    classes = serializers.PrimaryKeyRelatedField(queryset=ClassPeriod.objects.all(), many=True,required=False,allow_empty=True,default=[])

    class Meta:
        model = Student
        fields = ['id',
            'first_name', 'middle_name', 'last_name', 'email', 'password', 'user_profile',
            'father_name', 'mother_name', 'date_of_birth', 'gender', 'religion', 'category',#"department_id", "department_name",
            'height', 'weight', 'blood_group', 'number_of_siblings', 'roll_number','contact_number','scholar_number',
            'aadhaar_number','FMID_number','apaar_number','PEN_number','BPL_number','SSSMID','classes','is_active'
        ]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        user = instance.user
        rep.update({
            'first_name': user.first_name,
            'middle_name': user.middle_name,
            'last_name': user.last_name,
            'email': user.email,
            'user_profile': user.user_profile.url if user.user_profile else None,
        })
        return rep
    
    def _get_latest_admission(self, student):
        """Return the latest Admission for this student"""
        return Admission.objects.all_including_inactive().filter(student=student).order_by("-id").first()

    # def get_department_id(self, obj):
    #     admission = self._get_latest_admission(obj)
    #     return admission.department.id if admission and admission.department else None

    # def get_department_name(self, obj):
    #     admission = self._get_latest_admission(obj)
    #     return admission.department.department_name if admission and admission.department else None    


    def create(self, validated_data):
        user_data = {
            'first_name': validated_data.pop('first_name'),
            'middle_name': validated_data.pop('middle_name', ''),
            'last_name': validated_data.pop('last_name'),
            'email': validated_data.pop('email'),
            'password': validated_data.pop('password', None),
            'user_profile': validated_data.pop('user_profile', None),
        }
        classes_data = validated_data.pop('classes',[])
            # Normalize class IDs to integers
        if isinstance(classes_data, list):
            try:
                classes_data = [int(c) for c in classes_data]
            except (ValueError, TypeError):
                raise serializers.ValidationError({"classes": "Class IDs must be integers."})
        elif isinstance(classes_data, str):
            if classes_data.isdigit():
                classes_data = [int(classes_data)]
            else:
                raise serializers.ValidationError({"classes": "Invalid class ID format."})

        if User.objects.filter(email=user_data['email']).exists():
            raise serializers.ValidationError("User with this email already exists.")

        user = User.objects.create_user(

            email=user_data['email'],
            first_name=user_data['first_name'],
            last_name=user_data['last_name'],
            password=user_data['password'],
        )
        user.middle_name = user_data['middle_name']
        if user_data['user_profile']:
            user.user_profile = user_data['user_profile']
        user.save()

        # # ===== Generate scholar_number here =====
        # last_student = Student.objects.order_by('-id').first()
        
        # if last_student and last_student.scholar_number and last_student.scholar_number.isdigit():
        #     next_number = int(last_student.scholar_number) + 1
        # else:
        #     next_number = 1
        # validated_data['scholar_number'] = str(next_number).zfill(4)

        
        student = Student.objects.create(user=user, **validated_data)
        # student.classes.set(classes_data)

        # Only call .set() if the list is not empty
        if classes_data:
            student.classes.set(classes_data)

        return student

    def update(self, instance, validated_data):
        user = instance.user

        if user is None:
            raise serializers.ValidationError(
                "Cannot update: this student has no linked user account."
            )

        user_fields = ['first_name', 'middle_name', 'last_name', 'email', 'user_profile']
        for field in user_fields:
            if field in validated_data:
                setattr(user, field, validated_data.pop(field))
        if 'password' in validated_data:
            user.set_password(validated_data.pop('password'))
        user.save()

        if 'classes' in validated_data:
            instance.classes.set(validated_data.pop('classes'))

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance



class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name"]


class GuardianSerializer(serializers.ModelSerializer):
    # --- User Info (all optional) ---
    first_name = serializers.CharField(max_length=50, required=False, allow_blank=True)
    middle_name = serializers.CharField(max_length=50, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=50, required=False, allow_blank=True)
    password = serializers.CharField(max_length=50, required=False, write_only=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    user_profile = serializers.ImageField(required=False, allow_null=True)

    # --- Guardian Fields ---
    phone_no = serializers.CharField(
        required=False,
        allow_blank=True,
        validators=[
            RegexValidator(
                regex=r'^\+?(\d[\s-]?){10,15}$',
                message="Enter a valid phone number (10-15 digits, optional + at start)."
            )
        ]
    )
    annual_income = serializers.IntegerField(required=False, allow_null=True)
    means_of_livelihood = serializers.ChoiceField(
        choices=[('Govt', 'Government'), ('Non-Govt', 'Non-Government')],
        required=False,
        default='Govt'
    )
    qualification = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=300)
    occupation = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=300)
    designation = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=300)

    class Meta:
        model = Guardian
        exclude = ["user"]

    # ---------------- CREATE ----------------
    def create(self, validated_data):
        # Pop user-related fields safely
        user_data = {
            'first_name': validated_data.pop('first_name', ''),
            'middle_name': validated_data.pop('middle_name', ''),
            'last_name': validated_data.pop('last_name', ''),
            'email': validated_data.pop('email', None),
            'password': validated_data.pop('password', None),
            'user_profile': validated_data.pop('user_profile', None),
        }

        if not user_data['email']:
            raise serializers.ValidationError("Email is required to create guardian.")

        # Remove empty values from validated_data to avoid duplicates
        validated_data.pop('user_profile', None)

        # Check if user exists
        user = User.objects.filter(email__iexact=user_data['email']).first()
        if not user:
            # Default password if not provided
            if not user_data['password']:
                user_data['password'] = "Temp@1234"

            user = User.objects.create_user(
                email=user_data['email'],
                first_name=user_data['first_name'],
                middle_name=user_data['middle_name'],
                last_name=user_data['last_name'],
                password=user_data['password'],
                user_profile=user_data['user_profile'],
            )
            role, _ = Role.objects.get_or_create(name='guardian')
            user.role.add(role)

        # Create Guardian
        guardian = Guardian.objects.create(user=user, **validated_data)
        return guardian

    # ---------------- UPDATE ----------------
    def update(self, instance, validated_data):
        user = instance.user

        if user is None:
            raise serializers.ValidationError(
                "Cannot update: this guardian has no linked user account."
            )

        # Update user info if given
        for field in ['first_name', 'middle_name', 'last_name', 'email']:
            if field in validated_data:
                setattr(user, field, validated_data[field])

        # Update password if given
        if 'password' in validated_data and validated_data['password']:
            user.set_password(validated_data['password'])

        # Update profile image if given
        if 'user_profile' in validated_data:
            profile = validated_data.get('user_profile')
            if profile in [None, '']:
                if user.user_profile:
                    user.user_profile.delete(save=False)
                user.user_profile = None
            else:
                user.user_profile = profile

        user.save()

        # Update guardian fields
        for field in ['phone_no', 'annual_income', 'means_of_livelihood', 'qualification', 'occupation', 'designation']:
            if field in validated_data:
                setattr(instance, field, validated_data[field])

        instance.save()
        return instance

    # ---------------- REPRESENTATION ----------------
    def to_representation(self, instance):
        user = instance.user  # may be None if guardian wasn't created
        
        rep = {
            "id": instance.id,
            "first_name": user.first_name if user else None,
            "middle_name": user.middle_name if user else None,
            "last_name": user.last_name if user else None,
            "email": user.email if user else None,
            "phone_no": instance.phone_no,
            "annual_income": instance.annual_income,
            "means_of_livelihood": instance.means_of_livelihood,
            "qualification": instance.qualification,
            "occupation": instance.occupation,
            "designation": instance.designation,
            "user_profile": user.user_profile.url if user and user.user_profile else None,
            "is_active": instance.is_active
        }
        
        return rep


## As of 29May25 at 02:30 PM
class StudentYearLevelSerializer(serializers.ModelSerializer):
    # student_name = serializers.SerializerMethodField(read_only=True)
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    level_name = serializers.CharField(source='level.level_name', read_only=True)
    year_name = serializers.CharField(source='year.year_name', read_only=True)
    student_id = serializers.IntegerField(source='student.id', read_only=True)  # added as of 24June25 at 04:13 PM
    student_email = serializers.CharField(source='student.user.email', read_only=True)
    scholar_number = serializers.CharField(source='student.scholar_number', read_only=True) # added as of 14Oct25
    section = serializers.SerializerMethodField(read_only=True)
    HOUSE_CHOICES = [
        ("RED", "Red"),
        # ("BLUE", "Blue"),
        ("GREEN", "Green"),
        ("YELLOW", "Yellow"),
    ]
    house = serializers.ChoiceField(choices=HOUSE_CHOICES, required=False, allow_null=True,)

    # department_id = serializers.SerializerMethodField()
    # department_name = serializers.SerializerMethodField()
    student_is_active = serializers.BooleanField(
        source='student.is_active',
        read_only=True
    )
    class Meta:
        model = StudentYearLevel
        fields = ['id', 'student', 'level', 'year','student_id', 'student_name','student_email',
                  'scholar_number','level_name','section','year_name','house',"student_is_active"]
        extra_kwargs = {
            'student': {'write_only': True},
            'level': {'write_only': True},
            'year': {'write_only': True},
        }

   
    def get_section(self, obj):
        # Try to find an Admission for this student that matches the same year_level and school_year
        try:
            admission = Admission.objects.all_including_inactive().filter(student=obj.student, year_level=obj.level, school_year=obj.year).first()
            if admission and admission.class_section:
                return admission.class_section
        except Exception:
            pass
        return None
    
    # ---------------- DEPARTMENT ----------------
    def _get_latest_admission(self, student):
        return Admission.objects.all_including_inactive().filter(student=student).order_by("-id").first()


User = get_user_model()

class AdmissionFullSerializer(serializers.Serializer):
    # --- Student fields ---
    first_name = serializers.CharField()
    middle_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    father_name = serializers.CharField(required=False, allow_blank=True)
    mother_name = serializers.CharField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False)
    gender = serializers.ChoiceField(choices=[('Male','Male'),('Female','Female'),('Other','Other')])
    blood_group = serializers.CharField(required=False, allow_blank=True)
    roll_number = serializers.CharField(required=False, allow_blank=True)

    # --- Guardian fields ---
    guardian_first_name = serializers.CharField()
    guardian_last_name = serializers.CharField()
    guardian_email = serializers.EmailField()
    guardian_password = serializers.CharField(write_only=True)
    guardian_phone_no = serializers.CharField(required=False, allow_blank=True)
    annual_income = serializers.IntegerField(required=False, allow_null=True)

    # --- Admission ---
    admission_date = serializers.DateField(required=False)
    rte_number = serializers.CharField(required=False, allow_blank=True)
    enrollment_no = serializers.CharField(required=False, allow_blank=True)
    emergency_contact_no = serializers.CharField(required=False, allow_blank=True)
    previous_school_name = serializers.CharField(required=False, allow_blank=True)
    total_marks = serializers.IntegerField(default=0)
    obtain_marks = serializers.IntegerField(default=0)

    # --- Address ---
    house_no = serializers.CharField(required=False, allow_blank=True)
    address_line = serializers.CharField(required=False, allow_blank=True)
    country = serializers.IntegerField(required=False, allow_null=True)
    state = serializers.IntegerField(required=False, allow_null=True)
    city = serializers.IntegerField(required=False, allow_null=True)

    # --- Banking ---
    account_no = serializers.CharField(required=False, allow_blank=True)
    ifsc_code = serializers.CharField(required=False, allow_blank=True)
    holder_name = serializers.CharField(required=False, allow_blank=True)

    # --- Documents ---
    documents = serializers.ListField(required=False)

    # --- Year & School ---
    year_level = serializers.SlugRelatedField(
        slug_field='level_name',
        queryset=YearLevel.objects.all(),
        required=True
    )
    school_year = serializers.SlugRelatedField(
        slug_field='year_name',
        queryset=SchoolYear.objects.all(),
        required=True
    )

    def create(self, validated_data):
        documents_data = validated_data.pop('documents', [])
        guardian_data = {
            'first_name': validated_data.pop('guardian_first_name'),
            'last_name': validated_data.pop('guardian_last_name'),
            'email': validated_data.pop('guardian_email'),
            'password': validated_data.pop('guardian_password'),
            'phone_no': validated_data.pop('guardian_phone_no', ''),
            'annual_income': validated_data.pop('annual_income', None),
        }

        year_level = validated_data.pop('year_level')
        school_year = validated_data.pop('school_year')

        # --- 1. Create Student user ---
        student_user, created = User.objects.get_or_create(
            email=validated_data['email'],
            defaults={
                'first_name': validated_data['first_name'],
                'last_name': validated_data['last_name'],
            }
        )
        if created:
            student_user.set_password(validated_data['password'])
            student_user.save()
        else:
            raise serializers.ValidationError("Student with this email already exists.")

        student = Student.objects.create(
            user=student_user,
            father_name=validated_data.get('father_name', ''),
            mother_name=validated_data.get('mother_name', ''),
            date_of_birth=validated_data.get('date_of_birth'),
            gender=validated_data.get('gender'),
            blood_group=validated_data.get('blood_group', ''),
            roll_number=validated_data.get('roll_number', '')
        )

        # --- 2. Create Guardian user ---
        guardian_user, created = User.objects.get_or_create(
            email=guardian_data['email'],
            defaults={
                'first_name': guardian_data['first_name'],
                'last_name': guardian_data['last_name'],
            }
        )
        if created:
            guardian_user.set_password(guardian_data['password'])
            guardian_user.save()
        else:
            raise serializers.ValidationError("Guardian with this email already exists.")

        guardian, _ = Guardian.objects.get_or_create(
            user=guardian_user,
            defaults={
                'phone_no': guardian_data['phone_no'],
                'annual_income': guardian_data['annual_income']
            }
        )

        # --- 3. Create Address ---
        if any([validated_data.get('house_no'), validated_data.get('address_line'), validated_data.get('country'),
                validated_data.get('state'), validated_data.get('city')]):
            Address.objects.create(
                user=student_user,
                house_no=validated_data.get('house_no', ''),
                address_line=validated_data.get('address_line', ''),
                country_id=validated_data.get('country'),
                state_id=validated_data.get('state'),
                city_id=validated_data.get('city')
            )

        # --- 4. Create Banking ---
        BankingDetail.objects.create(
            user=student_user,
            account_no=validated_data.get('account_no', ''),
            ifsc_code=validated_data.get('ifsc_code', ''),
            holder_name=validated_data.get('holder_name', '')
        )

        # --- 5. Calculate previous percentage ---
        obtain_marks = validated_data.get('obtain_marks', 0)
        total_marks = validated_data.get('total_marks', 0)
        previous_percentage = (obtain_marks / total_marks * 100) if total_marks > 0 else 0

        # --- 6. Create Admission ---
        admission = Admission.objects.create(
            student=student,
            guardian=guardian,
            rte_number=validated_data.get('rte_number', ''),
            enrollment_no=validated_data.get('enrollment_no', ''),
            emergency_contact_no=validated_data.get('emergency_contact_no', ''),
            previous_school_name=validated_data.get('previous_school_name', 'N/A'),
            total_marks=total_marks,
            obtain_marks=obtain_marks,
            previous_percentage=previous_percentage,
            year_level=year_level,
            school_year=school_year
        )

        # --- 7. Create StudentYearLevel mapping ---
        StudentYearLevel.objects.update_or_create(
            student=student,
            level=year_level,
            year=school_year
        )

        # --- 8. Create Documents & Files ---
        for doc_data in documents_data:
            doc = Document.objects.create(
                identities=doc_data.get('identities', ''),
                student=student
            )
            doc.document_types.set(doc_data.get('document_types', []))
            for file_data in doc_data.get('files', []):
                File.objects.create(document=doc, file=file_data['file'])

        return admission