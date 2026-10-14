from django.contrib import admin
from .models import *

from .models import ErrorLog
admin.site.register(User)
admin.site.register(UserStatusLog)


@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ['endpoint', 'method', 'error_type', 'status_code', 'timestamp']
    search_fields = ['error_message', 'endpoint', 'user__email']

