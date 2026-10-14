# yourapp/exception_handlers.py

from rest_framework.views import exception_handler
from .models import ErrorLog
import traceback

def custom_exception_handler(exc, context):
    print("Custom Exception Handler Triggered")  # ✅ Entry point
    response = exception_handler(exc, context)
    request = context.get("request")

    if request:
        print("Request object found")
        try:
            user = request.user if request.user.is_authenticated else None
            endpoint = request.path
            method = request.method
            status_code = response.status_code if response else 500
            error_type = exc.__class__.__name__
            error_message = str(exc)
            # traceback_info = "".join(traceback.format_exception(None, exc, exc.__traceback__))
            traceback_info = "".join(
                traceback.format_exception(type(exc), exc, getattr(exc, '__traceback__', None))
            )


            print("Attempting to save error log to database...")
            ErrorLog.objects.create(
                user=user,
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                error_type=error_type,
                error_message=error_message,
                traceback_info=traceback_info
            )
            print("Error log saved successfully")
        except Exception as e:
            print("Failed to save error log:", str(e))
    else:
        print("Request object not found in context")

    return response
