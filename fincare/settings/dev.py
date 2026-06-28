"""FinCare - local development settings."""
from .base import *  # noqa: F401,F403

DEBUG = True

# INSTALLED_APPS and MIDDLEWARE come from the star import above
INSTALLED_APPS = list(INSTALLED_APPS) + [  # noqa: F405
    "debug_toolbar",
    "silk",
]

MIDDLEWARE = (
    ["debug_toolbar.middleware.DebugToolbarMiddleware"]
    + list(MIDDLEWARE)  # noqa: F405
    + ["silk.middleware.SilkyMiddleware"]
)

INTERNAL_IPS = ["127.0.0.1", "localhost"]

# Dev cookies served over HTTP - never enable secure in dev
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
