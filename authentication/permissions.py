# authentication/permissions.py
from rest_framework.permissions import BasePermission

class LoggedInUsersPermissions(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
            
        user_roles = request.user.role.all()
        user_role_names = [role.name.lower() for role in user_roles]
        
        # Only allow directors and office staff
        return "director" in user_role_names or "office staff" in user_role_names