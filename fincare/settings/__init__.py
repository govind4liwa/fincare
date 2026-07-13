"""
FinCare settings package.

DJANGO_SETTINGS_MODULE selects the environment:
  - fincare.settings.dev   (local development, default)
  - fincare.settings.test  (CI / pytest)
  - fincare.settings.prod  (production)

Each environment imports from base.py and overrides only what differs.
"""
