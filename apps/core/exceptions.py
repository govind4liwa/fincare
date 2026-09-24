"""DRF exception handling for FinCare.

Translates the accounting-integrity guards raised by the model layer into
HTTP responses, so a blocked delete is a clean 409 rather than a 500.
"""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.core.models import PostedRowProtectedError

logger = logging.getLogger(__name__)


def fincare_exception_handler(exc, context):
    """DRF handler that adds FinCare's accounting-integrity exceptions.

    ``PostedRowProtectedError`` means the caller tried to delete a document that
    has entered the accounting record. That is a conflict with the resource's
    state, not a malformed request, so it maps to 409. The message is our own
    curated text (model, id, and what to do instead) — never raw exception
    internals.
    """
    if isinstance(exc, PostedRowProtectedError):
        logger.info("Blocked delete of a posted row: %s", exc)
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
    return drf_exception_handler(exc, context)
