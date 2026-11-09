from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from .serializers import UserSerializer
from apps.memberships.models import Membership
from apps.memberships.serializers import MembershipSerializer

class CurrentUserView(APIView):
    """
    Endpoint /api/me/ que entrega el perfil del usuario autenticado,
    sus datos de socio y el estado de su membresía actual.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = UserSerializer(user)
        data = serializer.data

        # Adjuntar membresía más reciente
        latest_membership = Membership.objects.filter(member=user).order_by('-end_date').first()
        if latest_membership:
            data['membership'] = MembershipSerializer(latest_membership).data
        else:
            data['membership'] = None

        return Response(data, status=status.HTTP_200_OK)

