import traceback
from .models import ErrorLog

class GlobalErrorLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = None
        try:
            response = self.get_response(request)
        except Exception as exc:
            # Agar server error aaye, use bhi log karo
            self.log_error(request, exc, 500)
            raise  # error ko dobara raise karna zaroori hai

        # Agar response 4xx ya 5xx hai, use bhi log karo
        if response.status_code >= 400:
            self.log_error(request, None, response.status_code, response)

        return response
    
    def log_error(self, request, exc=None, status_code=500, response=None):
        try:
            user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
            error_type = exc.__class__.__name__ if exc else "HTTPError"
            error_message = str(exc) if exc else (response.content.decode() if response else "Unknown error")
            traceback_info = "".join(traceback.format_exception(None, exc, exc.__traceback__)) if exc else ""

            ErrorLog.objects.create(
                user=user,
                endpoint=request.path,
                method=request.method,
                status_code=status_code,
                error_type=error_type,
                error_message=error_message,
                traceback_info=traceback_info
            )
            print(f"Logged error {status_code} at {request.path}")
        except Exception as e:
            print(f"Failed to log error: {e}")
