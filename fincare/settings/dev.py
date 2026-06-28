"""FinCare — local development settings."""
from .base import *  # noqa: F401,F403
from .base import INSTALLED_APPS, MIDDLEWARE

DEBUG = True

# Console-printable secret OK in dev only
INSTALLED_APPS = INSTALLED_APPS + [
    "debug_toolbar",
    "silk",
]

MIDDLEWARE = (
    ["debug_toolbar.middleware.DebugToolbarMiddleware"]
    + MIDDLEWARE
    + ["silk.middleware.SilkyMiddleware"]
)

INTERNAL_IPS = ["127.0.0.1", "localhost"]

# Don't enforce strict CSRF in dev
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# More verbose SQL logs in dev when LOG_LEVEL=DEBUG
LOGGING_DEV_DB_LEVEL = "DEBUG" if DEBUG else "WARNING"
