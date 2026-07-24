"""FinCare - local development settings."""

from .base import *  # noqa: F403

DEBUG = True

# Accept the compose service host so the Next.js dev API proxy (web:8000) works.
ALLOWED_HOSTS = [*ALLOWED_HOSTS, "web"]  # noqa: F405

# INSTALLED_APPS and MIDDLEWARE come from the star import above
INSTALLED_APPS = [*INSTALLED_APPS, "debug_toolbar", "silk"]  # noqa: F405

MIDDLEWARE = [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    *MIDDLEWARE,  # noqa: F405
    "silk.middleware.SilkyMiddleware",
]

INTERNAL_IPS = ["127.0.0.1", "localhost"]

# Dev cookies served over HTTP - never enable secure in dev
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
