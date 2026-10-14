from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.response import Response
from rest_framework import permissions

class RoleBasedExamPermission(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        role_names = [role.name.lower() for role in user.role.all()]
        action = view.action
        api_section = getattr(view, 'api_section', None)

        access_rules = {
            'exam_type': {
                'director': 'full',
                'teacher': 'view',
                'student': 'none',
                'office staff': 'full',
                'others': 'none'
            },
            'exam_paper': {
                'director': 'full',
                'teacher': 'full',
                'student': 'none',
                'office staff': 'view',
                'others': 'none'
            },
            'exam_schedule': {
                'director': 'full',
                'teacher': 'full',
                'student': 'view_own',
                'guardian': 'view',
                'office staff': 'partial',
                'others': 'none'
            },

            'student_marks': {
                'director': 'full',
                'teacher': 'view_own_create',
                'student': 'none',
                'office staff': 'view_own_create',
                'others': 'none'
            }
        }

        if not api_section:
            return False

        for role in role_names:
            role = role.lower()
            access_level = access_rules.get(api_section, {}).get(role, 'none')

            if access_level == 'none':
                continue
            elif access_level == 'view' and request.method in SAFE_METHODS:
                return True
            elif access_level == 'partial' and request.method in ['GET', 'POST', 'PUT']:
                return True
            elif access_level == 'view_own' and request.method == 'GET':
                return True
            elif access_level == 'view_own_create' and request.method in ['GET', 'POST', 'PUT']:
                return True
            elif access_level == 'full':
                return True

        return False



class RoleBasedPermission(BasePermission):  # role based result permission
    """
    For report card and related views, allow access based on user roles.
    """

    def has_permission(self, request, view):
        print("Checking permissions for user:", request.user)

        user_roles = request.user.role.all().values_list('name', flat=True)

        # Allow all GETs for Director and Office Staff
        if request.method in SAFE_METHODS:
            if "director" in user_roles or "office_staff" in user_roles:
                return True
            elif "teacher" in user_roles:
                return True
            elif "student" in user_roles or "guardian" in user_roles:
                return True
            return False

        # Allow POST and PATCH for Director and assigned Teacher
        elif request.method in ['POST', 'PATCH', 'PUT', 'DELETE']:
            if "director" in user_roles:
                return True
            elif "teacher" in user_roles:
                return True
            return False

        # Deny everything else by default
        return False


class IsDirector(BasePermission):
    """
    Allows access only to users with the 'Director' role.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role.filter(name="Director").exists()
    

# --------------------- Expense 
class ExpensePermission(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        roles = [role.name.lower() for role in user.role.all()]
        api_section = getattr(view, "api_section", None)

        # Teacher → sirf read-only access
        # if "teacher" in roles and api_section == "employee_salary":
        #     return view.action in ["list", "retrieve"]

        # Director & Office Staff → full CRUD
        if any(r in roles for r in ["director", "office staff"]):
            return True

        return False

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class EmployeePermission(permissions.BasePermission):
    
    # Director -> Full access Office Staff -> Read-only Others -> No access
    

    def has_permission(self, request, view):
        user = request.user

        if not user.is_authenticated:
            return False

        # Director -> always allow
        if user.role.filter(name__iexact="director").exists():
            return True

        # Office staff -> sirf GET (read-only)
        if user.role.filter(name__iexact="office staff").exists():
            return request.method in permissions.SAFE_METHODS

        return False
# RBA for termination and reactivation of the user
class RoleBasedUserManagementPermission(BasePermission):
    """
    Permission class for user deactivation / reactivation
    """
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        role_names = [role.name.lower().replace("_", " ").strip() for role in user.role.all()]

        allowed_roles = ['director', 'admin', 'office staff']

        for role in role_names:
            if role in allowed_roles:
                return True

        return False
    





from rest_framework.permissions import BasePermission, SAFE_METHODS
from teacher.models import Teacher, TeacherYearLevel

class RoleBasedPermissionteacheryearlevel(BasePermission):
    """
    Director / Office Staff → full CRUD + full queryset
    Teacher → only GET/HEAD/OPTIONS + their own data
    Others → deny
    """

    def has_permission(self, request, view):
        user = request.user
        
        # Check if the user is authenticated
        if not user.is_authenticated:
            return False  # Deny access if the user is not authenticated

        role_names = [role.name.lower() for role in user.role.all()]

        # Director & Office Staff: all methods allowed
        if 'director' in role_names or 'office staff' in role_names:
            return True

        # Teacher: only safe methods
        if 'teacher' in role_names:
            return request.method in SAFE_METHODS

        # Other roles: deny
        return False

    def filter_queryset(self, request, queryset, view):
        """
        Role-based queryset filtering
        """
        user = request.user
        
        # Check if the user is authenticated
        if not user.is_authenticated:
            return queryset.none()  # Deny access if the user is not authenticated

        role_names = [role.name.lower() for role in user.role.all()]

        if 'director' in role_names or 'office staff' in role_names:
            return queryset

        elif 'teacher' in role_names:
            try:
                teacher = Teacher.objects.get(user=user)
                return queryset.filter(teacher=teacher)
            except Teacher.DoesNotExist:
                return queryset.none()

        return queryset.none()



# class FeeRecordPermission(BasePermission):
#     """
#     Director / Office Staff → full CRUD
#     Teacher → only fee records of their class students (read-only)
#     Student → only their own fee records (GET + POST)
#     Guardian → only their children fee records (GET + POST)
#     """
#     def has_permission(self, request, view):
#         user = request.user
#         if not user.is_authenticated:
#             return False

#         # Director or Staff → FULL ACCESS
#         if hasattr(user, "director") or hasattr(user, "officestaff") or user.is_staff or user.is_superuser:
#             return True

#         # Teacher → only SAFE methods
#         if hasattr(user, "teacher"):
#             return request.method in ("GET", "HEAD", "OPTIONS")

#         # Student → GET + POST
#         if hasattr(user, "student"):
#             return request.method in ("GET", "POST")

#         # Guardian → GET + POST
#         if hasattr(user, "guardian"):
#             return request.method in ("GET", "POST")

#         return False

#     def has_object_permission(self, request, view, obj):
#         user = request.user

#         # Director / Staff
#         if hasattr(user, "director") or hasattr(user, "officestaff") or user.is_staff or user.is_superuser:
#             return True

#         # Teacher → only students in their YearLevel
#         if hasattr(user, "teacher"):
#             teacher_year_levels = user.teacher.teacheryearlevel_set.values_list("year_level_id", flat=True)
#             return obj.student.student_year_levels.filter(level_id__in=teacher_year_levels).exists()

#         # Student → only self
#         if hasattr(user, "student"):
#             return obj.student_id == user.student.id

#         # Guardian → only children
#         if hasattr(user, "guardian"):
#             children_ids = user.guardian.students.values_list("id", flat=True)
#             return obj.student_id in children_ids

#         return False

# class FeeRecordPermission(BasePermission):
#     """
#     Director / Office Staff → full CRUD
#     Teacher → only fee records of their class students (read-only)
#     Student → only their own fee records (GET + POST)
#     Guardian → only their children fee records (GET + POST)
#     """
#     def has_permission(self, request, view):
#         user = request.user
#         if not user.is_authenticated:
#             return False

#         # Director or Staff → FULL ACCESS
#         if hasattr(user, "director") or hasattr(user, "officestaff") or user.is_staff or user.is_superuser:
#             return True

#         # Teacher → only SAFE methods
#         if hasattr(user, "teacher"):
#             return request.method in ("GET", "HEAD", "OPTIONS")

#         # Student → GET + POST
#         if hasattr(user, "student"):
#             return request.method in ("GET", "POST")

#         # Guardian → GET + POST
#         if hasattr(user, "guardian"):
#             return request.method in ("GET", "POST")

#         return False

class FeeRecordPermission(BasePermission):
    """
    Director / Office Staff → full CRUD
    Student → GET + POST (only self records)
    Guardian → GET + POST (only children records)
    Teacher → only GET (their assigned students)
    """

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        #  Director / Staff
        if hasattr(user, "role"):
            role_names = [role.name.lower() for role in user.role.all()]
        else:
            role_names = []

        if "director" in role_names or "staff" in role_names or user.is_staff or user.is_superuser:
            return True

        # Student
        if hasattr(user, "student"):
            return request.method in ["GET", "POST"]

        #  Guardian (detect via relation, not role)
        if hasattr(user, "guardian_relation"):   
            return request.method in ["GET", "POST"]

        #  Teacher
        if hasattr(user, "teacher"):
            return request.method == "GET"

        return False


    def has_object_permission(self, request, view, obj):
        user = request.user

        # Director / Staff
        if hasattr(user, "director") or hasattr(user, "officestaff") or user.is_staff or user.is_superuser:
            return True

        # Teacher → only students in their YearLevel
        if hasattr(user, "teacher"):
            teacher_year_levels = user.teacher.teacheryearlevel_set.values_list("year_level_id", flat=True)
            return obj.student.student_year_levels.filter(level_id__in=teacher_year_levels).exists()

        # Student → only self
        if hasattr(user, "student"):
            return obj.student_id == user.student.id

        # Guardian → only children
        if hasattr(user, "guardian_relation"):
            children_ids = user.guardian_relation.studentguardian.values_list("student_id", flat=True)
            return obj.student_id in children_ids

        return False



class IsDirectororOfficeStaff(BasePermission):
    """
    Allows access only to users with the 'office_staff'and'director' role.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role.filter(name="director").exists() or request.user.role.filter(name="office_staff").exists()
    

# from rest_framework.permissions import BasePermission

# class ReportCardPermission(BasePermission):
#     """Custom permission for Report Card operations based on roles"""

#     def has_permission(self, request, view):
#         user = request.user
#         if not user.is_authenticated:
#             return False

#         role_names = [role.name.lower() for role in user.role.all()]
#         action = getattr(view, 'action', None)

#         # Access rules for each view action
#         access_rules = {
#             'list': ['director', 'office staff', 'teacher'],
#             'retrieve': ['director', 'office staff', 'teacher', 'student', 'guardian'],
#             'create': ['director', 'office staff', 'teacher'],
#             'update': ['director', 'office staff', 'teacher'],
#             'partial_update': ['director', 'office staff', 'teacher'],
#             'destroy': ['director'],
#             'generate_report_card': ['director', 'office staff'],
#             'bulk_generate': ['director', 'office staff'],
#             'print_format': ['director', 'office staff', 'teacher', 'student', 'guardian'],
#         }

#         allowed_roles = access_rules.get(action, [])
#         return any(role in allowed_roles for role in role_names)

#     def has_object_permission(self, request, view, obj):
#         user = request.user
#         role_names = [role.name.lower() for role in user.role.all()]

#         # Director and Office Staff can access all report cards
#         if 'director' in role_names or 'office staff' in role_names:
#             return True

#         # Teacher can only access report cards of students they teach
#         if 'teacher' in role_names:
#             from teacher.models import Teacher  # adjust import if needed
#             try:
#                 teacher = Teacher.objects.get(user=user)
#             except Teacher.DoesNotExist:
#                 return False

#             teacher_levels = teacher.year_levels.values_list('id', flat=True)
#             return obj.student_level.level_id in teacher_levels

#         # Student can access only their own report card
#         if 'student' in role_names:
#             from student.models import Student
#             try:
#                 student = Student.objects.get(user=user)
#             except Student.DoesNotExist:
#                 return False

#             return obj.student_level.student_id == student.id

#         # Guardian can access only their children's report cards
#         if 'guardian' in role_names:
#             from student.models import StudentGuardian
#             try:
#                 guardian = StudentGuardian.objects.get(user=user)
#             except StudentGuardian.DoesNotExist:
#                 return False

#             children_ids = guardian.student.values_list('student_id', flat=True)
#             return obj.student_level.student_id in children_ids

#         return False
