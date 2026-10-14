"""
Dedicated Test Settings Module for sms_new_django_test.
Imports production settings and overrides test-only configurations.
DO NOT USE IN PRODUCTION.
"""

import os
from unittest.mock import MagicMock
import sys

# Mock optional packages if not installed in current environment
for mod in ['twilio', 'twilio.rest']:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# Default fallback environment variables for test execution if not set in environment
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-test-database-only-12345')
os.environ.setdefault('DEBUG', 'True')
os.environ.setdefault('DB_NAME', 'sms_new_django_test')
os.environ.setdefault('DB_USER', 'root')
os.environ.setdefault('DB_PASSWORD', 'mysql')
os.environ.setdefault('DB_HOST', '127.0.0.1')
os.environ.setdefault('DB_PORT', '3306')
os.environ.setdefault('ALLOWED_HOSTS', 'localhost,127.0.0.1')
os.environ.setdefault('CSRF_TRUSTED_ORIGINS', 'http://localhost:8000')
os.environ.setdefault('STATIC_URL', '/static/')
os.environ.setdefault('STATIC_ROOT', r'D:\SMS-TEXONT\SMS-AI\backend\NewProgressive-Backend-Production-main\static')
os.environ.setdefault('MEDIA_URL', '/media/')
os.environ.setdefault('MEDIA_ROOT', r'D:\SMS-TEXONT\SMS-AI\backend\NewProgressive-Backend-Production-main\media')
os.environ.setdefault('ICICI_MERCHANT_ID', 'DUMMY')
os.environ.setdefault('ICICI_AGGREGATOR_ID', 'DUMMY')
os.environ.setdefault('ICICI_SECRET_KEY', 'DUMMY')
os.environ.setdefault('ICICI_INITIATE_SALE_URL', 'https://example.com/initiate')
os.environ.setdefault('ICICI_COMMAND_URL', 'https://example.com/command')
os.environ.setdefault('ICICI_SETTLEMENT_DETAILS_URL', 'https://example.com/settlement')

from .settings import *

# Explicitly isolate test database
DATABASES['default']['NAME'] = 'sms_new_django_test'

# Safety assertion: guarantee that active database is strictly sms_new_django_test
assert DATABASES['default']['NAME'] == 'sms_new_django_test', (
    f"FATAL: Test settings must point to sms_new_django_test, got {DATABASES['default']['NAME']}"
)

# Test-Environment-Only Password Hasher Configuration
# Set PASSWORD_HASHERS to only PBKDF2 and BCrypt
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptPasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]
