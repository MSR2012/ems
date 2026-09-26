"""Map domain errors to structured DRF error responses."""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from shared_kernel.domain import DomainError, InvalidStateTransition, NotFoundError


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response
    if isinstance(exc, NotFoundError):
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    if isinstance(exc, InvalidStateTransition):
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
    errors = getattr(exc, "errors", None)
    if isinstance(exc, DomainError) and isinstance(errors, dict):
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, DomainError):
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return None
