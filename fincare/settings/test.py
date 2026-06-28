"""FinCare — pytest / CI test settings."""

import os

# Ensure a working SECRET_KEY exists before importing base
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key-do-not-use-in-prod-1234567890")
os.environ.setdefault("DJANGO_DEBUG", "False")
os.environ.setdefault(
    "DATABASE_URL", "postgres://fincare:fincare_ci_password@localhost:5432/fincare_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/1")

from .base import *  # noqa: F403

DEBUG = False

# Speed up password hashing in tests
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Run Celery tasks eagerly (synchronous) in tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# In-memory cache for tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "fincare-test",
    }
}

# Disable throttling in tests
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = ()  # noqa: F405

# Silence email
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
