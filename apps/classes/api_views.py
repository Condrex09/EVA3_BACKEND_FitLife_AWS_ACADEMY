from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError, PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from .models import ClassType, ClassSession, Booking
from .serializers import ClassTypeSerializer, ClassSessionSerializer, BookingSerializer
from .services import book_class_session, cancel_booking
from apps.accounts.permissions import IsAdminRole, IsOwnerOrStaff

class ClassTypeViewSet(viewsets.ModelViewSet):
    """
    Catálogo de disciplinas de clases grupales.
    Lectura pública; creación/edición solo para administradores.
    """
    queryset = ClassType.objects.all().order_by('name')
    serializer_class = ClassTypeSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['intensity', 'is_active']
    search_fields = ['name', 'description']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [IsAdminRole()]

class ClassSessionViewSet(viewsets.ModelViewSet):
    """
    Sesiones de clases grupales programadas.
    Lectura pública para revisar horarios; gestión reservada a administradores.
    """
    queryset = ClassSession.objects.all().select_related('class_type').order_by('start_datetime')
    serializer_class = ClassSessionSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['class_type', 'status', 'room']
    search_fields = ['class_type__name', 'instructor_name', 'room']
    ordering_fields = ['start_datetime', 'capacity']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [IsAdminRole()]

class BookingViewSet(viewsets.ModelViewSet):
    """
    Reservas de clases grupales con lista de espera y concurrencia segura.
    - http_method_names: solo ['get', 'post', 'head', 'options'] (sin PUT, PATCH ni DELETE).
    - Cancelaciones exclusivamente a través de POST /api/bookings/{id}/cancel/.
    - El socio siempre reserva a su propio nombre mediante book_class_session.
    """
    http_method_names = ['get', 'post', 'head', 'options']
    serializer_class = BookingSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'session']
    search_fields = ['member__username', 'member__first_name', 'member__last_name', 'session__class_type__name']
    ordering_fields = ['created_at']

    def get_permissions(self):
        return [permissions.IsAuthenticated(), IsOwnerOrStaff()]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Booking.objects.none()
        if user.is_staff or getattr(user, 'role', None) in ['ADMIN', 'RECEPTION']:
            return Booking.objects.all().select_related('session', 'session__class_type', 'member')
        return Booking.objects.filter(member=user).select_related('session', 'session__class_type', 'member')

    def create(self, request, *args, **kwargs):
        session_id = request.data.get('session_id') or request.data.get('session')
        if not session_id:
            return Response({'error': 'El campo session_id es requerido.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            booking, is_confirmed, msg = book_class_session(request.user, session_id)
            serializer = self.get_serializer(booking)
            resp_status = status.HTTP_201_CREATED if is_confirmed else status.HTTP_202_ACCEPTED
            return Response({'message': msg, 'booking': serializer.data}, status=resp_status)
        except ValidationError as e:
            return Response({'error': str(e.message if hasattr(e, 'message') else e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        try:
            booking = cancel_booking(pk, requesting_user=request.user)
            serializer = self.get_serializer(booking)
            return Response({'message': 'Reserva cancelada exitosamente.', 'booking': serializer.data}, status=status.HTTP_200_OK)
        except (ValidationError, PermissionDenied) as e:
            return Response({'error': str(e.message if hasattr(e, 'message') else e)}, status=status.HTTP_400_BAD_REQUEST)
