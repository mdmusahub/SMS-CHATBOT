from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser, PermissionsMixin
from django.contrib.auth.base_user import BaseUserManager
from django.core.validators import validate_email
from django.core.exceptions import ValidationError



class CustomUserManager(BaseUserManager):
    """Define a model manager for User model with no username field."""
    # Added for termination
    # this will also remove the user from the admin user view
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)
    
    def all_including_inactive(self):
        return super().get_queryset()
    # *********************
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError("The given email must be set")

        try:
            validate_email(email)
        except ValidationError as e:
            raise ValueError("please enter a valid email")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        if password is None:
            raise ValueError("Password must not be none")
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser, PermissionsMixin):
    username = None
    first_name = models.CharField(max_length=100, null=False)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, null=False)
    password = models.CharField(max_length=100, null=False)
    email = models.EmailField(unique=True, null=False)
    user_profile = models.FileField(upload_to='profile_pics/')
    # *********************
    is_active = models.BooleanField(default=True)  # Track active/terminated status
    deactivation_reason = models.TextField(blank=True, null=True)  # Reason for deactivation
    deactivation_date = models.DateTimeField(blank=True, null=True)  # Date of deactivation
    reactivation_date = models.DateTimeField(blank=True, null=True)  # Date of reactivation
    # *********************
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = CustomUserManager()

    role = models.ManyToManyField("director.Role", blank=True, related_name="user")

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        db_table = "User"
        indexes = [models.Index(fields=['is_active'])]  # Index for performance  (just returns the active users)

    def __str__(self):
        return self.email


# added for tracking user status 
class UserStatusLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=[('TERMINATED', 'Terminated'), ('REACTIVATED', 'Reactivated')])
    reason = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "UserStatusLog"
        verbose_name = "User Status Log"
        verbose_name_plural = "User Status Logs"

    def __str__(self):
        return f"{self.user.email} - {self.status} at {self.timestamp}"



class ErrorLog(models.Model):
    user = models.ForeignKey("User", null=True, blank=True, on_delete=models.SET_NULL)
    endpoint = models.CharField(max_length=255)
    method = models.CharField(max_length=10)
    status_code = models.IntegerField()
    error_type = models.CharField(max_length=100)
    error_message = models.TextField()
    traceback_info = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.error_type} at {self.endpoint}"
