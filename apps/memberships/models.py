import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from apps.accounts.models import User, UserRole

class Plan(models.Model):
    """
    Plan de suscripción de FitLife (ej. FitLife Black, FitLife Plus, FitLife Básico).
    """
    name = models.CharField(_('Nombre del plan'), max_length=100)
    slug = models.SlugField(_('Identificador URL (slug)'), unique=True)
    description = models.TextField(_('Descripción comercial'))
    monthly_price = models.PositiveIntegerField(_('Precio mensual (CLP)'), help_text=_('Valor en pesos chilenos.'))
    enrollment_price = models.PositiveIntegerField(_('Costo de matrícula / inscripción (CLP)'), default=0)
    duration_days = models.PositiveIntegerField(_('Duración en días'), default=30)
    loyalty_months = models.PositiveIntegerField(_('Meses de fidelidad'), default=0, help_text=_('0 para sin fidelidad.'))
    benefits = models.JSONField(
        _('Lista de beneficios'),
        default=list,
        blank=True,
        help_text=_('Array JSON con frases descriptivas de beneficios.')
    )
    is_featured = models.BooleanField(_('Destacado en portada'), default=False)
    is_active = models.BooleanField(_('Activo para venta'), default=True)
    order = models.PositiveIntegerField(_('Orden de visualización'), default=0)

    class Meta:
        verbose_name = _('Plan')
        verbose_name_plural = _('Planes')
        ordering = ['order', 'monthly_price']

    def __str__(self):
        return f"{self.name} (${self.monthly_price:,} CLP/mes)"


class MembershipStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', _('Activa')
    EXPIRED = 'EXPIRED', _('Vencida')
    FROZEN = 'FROZEN', _('Congelada')


class Membership(models.Model):
    """
    Membresía asignada a un socio.
    Regla: Un socio solo puede tener UNA membresía con estado ACTIVE o FROZEN a la vez.
    """
    member = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='memberships',
        limit_choices_to={'role': UserRole.MEMBER},
        verbose_name=_('Socio')
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name='memberships',
        verbose_name=_('Plan')
    )
    start_date = models.DateField(_('Fecha de inicio'))
    end_date = models.DateField(_('Fecha de término'))
    status = models.CharField(
        _('Estado de membresía'),
        max_length=20,
        choices=MembershipStatus.choices,
        default=MembershipStatus.ACTIVE,
        db_index=True
    )
    frozen_from = models.DateField(_('Congelada desde'), null=True, blank=True)
    frozen_until = models.DateField(_('Congelada hasta'), null=True, blank=True)
    created_at = models.DateTimeField(_('Fecha de creación'), auto_now_add=True)

    class Meta:
        verbose_name = _('Membresía')
        verbose_name_plural = _('Membresías')
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['member'],
                condition=models.Q(status__in=['ACTIVE', 'FROZEN']),
                name='unique_current_membership_per_member'
            )
        ]

    def __str__(self):
        return f"Membresía {self.plan.name} - {self.member.get_full_name() or self.member.username} ({self.get_status_display()})"

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': _('La fecha de término no puede ser anterior a la de inicio.')})

        # Regla: solo una membresía ACTIVE o FROZEN por socio simultáneamente
        if self.status in [MembershipStatus.ACTIVE, MembershipStatus.FROZEN]:
            existing = Membership.objects.filter(
                member=self.member,
                status__in=[MembershipStatus.ACTIVE, MembershipStatus.FROZEN]
            )
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(_('El socio ya posee una membresía activa o congelada vigente.'))

    @property
    def is_valid_now(self) -> bool:
        today = timezone.localdate()
        return self.status == MembershipStatus.ACTIVE and self.end_date >= today

    @property
    def days_remaining(self) -> int:
        today = timezone.localdate()
        if self.end_date >= today:
            return (self.end_date - today).days
        return 0


class PaymentConcept(models.TextChoices):
    ENROLLMENT = 'ENROLLMENT', _('Inscripción')
    MONTHLY = 'MONTHLY', _('Mensualidad')
    RENEWAL = 'RENEWAL', _('Renovación')


class PaymentMethod(models.TextChoices):
    SIMULATED_CARD = 'SIMULATED_CARD', _('Tarjeta de Crédito/Débito (Simulada)')
    CASH = 'CASH', _('Efectivo')
    TRANSFER = 'TRANSFER', _('Transferencia Bancaria')


class PaymentStatus(models.TextChoices):
    APPROVED = 'APPROVED', _('Aprobado')
    REJECTED = 'REJECTED', _('Rechazado')
    PENDING = 'PENDING', _('Pendiente')


class Payment(models.Model):
    """
    Registro histórico de transacciones financieras y pagos de membresías.
    """
    membership = models.ForeignKey(
        Membership,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name=_('Membresía vinculada')
    )
    member = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payments',
        limit_choices_to={'role': UserRole.MEMBER},
        verbose_name=_('Socio')
    )
    amount = models.PositiveIntegerField(_('Monto pagado (CLP)'))
    concept = models.CharField(
        _('Concepto'),
        max_length=20,
        choices=PaymentConcept.choices,
        default=PaymentConcept.MONTHLY
    )
    method = models.CharField(
        _('Método de pago'),
        max_length=25,
        choices=PaymentMethod.choices,
        default=PaymentMethod.SIMULATED_CARD
    )
    status = models.CharField(
        _('Estado del pago'),
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.APPROVED,
        db_index=True
    )
    reference = models.CharField(
        _('Código de referencia'),
        max_length=50,
        unique=True,
        db_index=True
    )
    paid_at = models.DateTimeField(_('Fecha y hora del pago'), auto_now_add=True)

    class Meta:
        verbose_name = _('Pago')
        verbose_name_plural = _('Pagos')
        ordering = ['-paid_at']

    def __str__(self):
        return f"{self.reference} - ${self.amount:,} CLP ({self.get_status_display()}) - {self.member.username}"

    @classmethod
    def generate_reference(cls, prefix="PAY") -> str:
        unique_id = uuid.uuid4().hex[:10].upper()
        return f"{prefix}-{unique_id}"

