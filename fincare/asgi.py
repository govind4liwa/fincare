"""ASGI entry point for FinCare."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fincare.settings.prod")

application = get_asgi_application()
