"""Users API: the current user's own profile."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers import MeSerializer


class MeView(APIView):
    """GET-only — identity, roles, and accessible entities for the caller."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data)
