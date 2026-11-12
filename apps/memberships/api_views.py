from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Plan, Membership, Payment
from .serializers import PlanSerializer, MembershipSerializer, PaymentSerializer
from apps.accounts.permissions import IsAdminRole, IsReceptionRole, IsOwnerOrStaff

class PlanViewSet(viewsets.ModelViewSet):
    """
    CRUD de Planes comerciales.
    - list/retrieve: público (solo planes activos para no-staff).
    - create/update/destroy: solo Administrador.
    """
    serializer_class = PlanSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active', 'is_featured']
    search_fields = ['name', 'description']

    def get_queryset(self):
        user = self.request.user
        if user and user.is_authenticated and (user.is_staff or getattr(user, 'role', None) == 'ADMIN'):
            return Plan.objects.all().order_by('order', 'monthly_price')
        return Plan.objects.filter(is_active=True).order_by('order', 'monthly_price')

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [IsAdminRole()]


class MembershipViewSet(viewsets.ModelViewSet):
    """
    Membresías:
    - list/retrieve: staff/recepción todas; socio común solo las suyas.
    - create/update/partial_update/destroy: reservado a Administradores.
    """
    serializer_class = MembershipSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'plan']
    search_fields = ['member__username', 'member__first_name', 'member__last_name', 'member__profile__rut']
    ordering_fields = ['start_date', 'end_date', 'created_at']

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Membership.objects.none()
        if user.is_staff or getattr(user, 'role', None) in ['ADMIN', 'RECEPTION']:
            return Membership.objects.all().select_related('member', 'plan')
        return Membership.objects.filter(member=user).select_related('member', 'plan')

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated(), IsOwnerOrStaff()]
        return [IsAdminRole()]


class PaymentViewSet(viewsets.ModelViewSet):
    """
    Pagos:
    - list/retrieve: personal staff audita todos; socios solo su historial propio.
    - create: Administradores y Recepción (para registro de pagos manuales).
    - update/partial_update/destroy: restringido solo a Administradores.
    """
    serializer_class = PaymentSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'concept', 'method']
    search_fields = ['reference', 'member__username', 'member__first_name', 'member__last_name', 'member__profile__rut']
    ordering_fields = ['paid_at', 'amount']

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Payment.objects.none()
        if user.is_staff or getattr(user, 'role', None) in ['ADMIN', 'RECEPTION']:
            return Payment.objects.all().select_related('member', 'membership')
        return Payment.objects.filter(member=user).select_related('member', 'membership')

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated(), IsOwnerOrStaff()]
        if self.action == 'create':
            return [IsReceptionRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        serializer.save(registered_by=self.request.user)
