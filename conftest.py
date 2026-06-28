"""Top-level pytest configuration."""

import os

# pytest-django reads DJANGO_SETTINGS_MODULE; also set in pyproject.toml
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fincare.settings.test")
