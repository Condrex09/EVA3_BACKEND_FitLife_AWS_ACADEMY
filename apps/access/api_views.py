from rest_framework.views import APIView
from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import AccessLog
from .serializers import AccessLogSerializer, QRValidationRequestSerializer
from .services import validate_and_record_access, get_facility_occupancy_data
from apps.accounts.permissions import IsReceptionRole

class QRValidationView(APIView):
    """
    Endpoint POST /api/access/validate/
    Valida un código QR escaneado en recepción en milisegundos.
    Registra el intento en AccessLog y responde con el resultado de validación.
    Acceso restringido a Recepción y Administradores.
    """
    permission_classes = [IsReceptionRole]

    def post(self, request):
        serializer = QRValidationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        qr_token = serializer.validated_data['qr_token']
        result = validate_and_record_access(qr_token, scanned_by=request.user)

        http_status = status.HTTP_200_OK if result.get('allowed') else status.HTTP_403_FORBIDDEN
        return Response(result, status=http_status)


class AccessLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Consulta y auditoría de la bitácora de accesos.
    Solo accesible por personal de Recepción y Administradores.
    """
    permission_classes = [IsReceptionRole]
    queryset = AccessLog.objects.all().select_related('member', 'scanned_by').order_by('-timestamp')
    serializer_class = AccessLogSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['result', 'direction', 'deny_reason']
    search_fields = ['member__username', 'member__first_name', 'member__last_name', 'member__profile__rut']
    ordering_fields = ['timestamp']


class FacilityOccupancyView(APIView):
    """
    Endpoint GET /api/aforo/
    Devuelve los datos de aforo detallados en tiempo real (incluye personas dentro y gráfico).
    Reservado para personal de Recepción y Administradores para resguardar la privacidad.
    """
    permission_classes = [IsReceptionRole]

    def get(self, request):
        data = get_facility_occupancy_data()
        return Response(data, status=status.HTTP_200_OK)


class FacilityOccupancySummaryView(APIView):
    """
    Endpoint público GET /api/aforo/resumen/
    Devuelve únicamente métricas agregadas de aforo (conteo, capacidad, porcentaje y semáforo),
    sin exponer nombres, RUTs ni datos privados de los socios.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        data = get_facility_occupancy_data()
        summary = {
            'current_count': data['current_count'],
            'max_capacity': data['max_capacity'],
            'percentage': data['percentage'],
            'status_color': data['status_color'],
            'status_text': data['status_text'],
            'is_full': data['current_count'] >= data['max_capacity'],
        }
        return Response(summary, status=status.HTTP_200_OK)
