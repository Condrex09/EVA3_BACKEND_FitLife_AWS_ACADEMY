from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from apps.accounts.models import User

class AccessDirection(models.TextChoices):
    IN = 'IN', _('Ingreso (Entrada)')
    OUT = 'OUT', _('Egreso (Salida)')

class AccessResult(models.TextChoices):
    ALLOWED = 'ALLOWED', _('Permitido')
    DENIED = 'DENIED', _('Denegado')

class DenyReason(models.TextChoices):
    EXPIRED = 'EXPIRED', _('Membresía vencida')
    FROZEN = 'FROZEN', _('Membresía congelada')
    NO_MEMBERSHIP = 'NO_MEMBERSHIP', _('Sin membresía activa')
    INVALID_QR = 'INVALID_QR', _('Código QR inválido o no registrado')
    ALREADY_INSIDE = 'ALREADY_INSIDE', _('El socio ya figura dentro del recinto')
    CAPACITY_FULL = 'CAPACITY_FULL', _('Aforo máximo de la sede alcanzado')

class FacilitySetting(models.Model):
    """
    Configuración global de la sede (Singleton).
    Define los límites de aforo y umbrales de alerta para el dashboard en tiempo real.
    """
    facility_name = models.CharField(_('Nombre de la sede'), max_length=120, default='Sede Central FitLife')
    max_capacity = models.PositiveIntegerField(
        _('Capacidad máxima de personas'),
        default=120,
        help_text=_('Aforo total permitido por normativa sanitaria y de seguridad.')
    )
    warning_threshold_pct = models.PositiveIntegerField(
        _('Umbral Amarillo / Advertencia (%)'),
        default=60,
        help_text=_('Porcentaje a partir del cual se activa la alerta amarilla.')
    )
    danger_threshold_pct = models.PositiveIntegerField(
        _('Umbral Rojo / Peligro (%)'),
        default=85,
        help_text=_('Porcentaje a partir del cual se activa la alerta roja de sobrecupo.')
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Ajuste de Aforo y Sede')
        verbose_name_plural = _('Ajustes de Aforo y Sede')

    def __str__(self):
        return f"{self.facility_name} (Capacidad: {self.max_capacity} pers.)"

    def save(self, *args, **kwargs):
        # Garantizar comportamiento Singleton: solo un registro con ID 1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'facility_name': 'Sede Central FitLife',
                'max_capacity': 120,
                'warning_threshold_pct': 60,
                'danger_threshold_pct': 85
            }
        )
        return obj


class AccessLog(models.Model):
    """
    Bitácora de validación de pases QR.
    Registra cada intento de entrada o salida, sea permitido o denegado,
    para auditoría y cálculo de aforo instantáneo.
    """
    member = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='access_logs',
        verbose_name=_('Socio')
    )
    scanned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scans_conducted',
        verbose_name=_('Operador / Recepcionista')
    )
    direction = models.CharField(
        _('Dirección'),
        max_length=5,
        choices=AccessDirection.choices,
        default=AccessDirection.IN
    )
    result = models.CharField(
        _('Resultado del acceso'),
        max_length=10,
        choices=AccessResult.choices,
        db_index=True
    )
    deny_reason = models.CharField(
        _('Motivo de denegación'),
        max_length=20,
        choices=DenyReason.choices,
        null=True,
        blank=True
    )
    timestamp = models.DateTimeField(
        _('Fecha y hora'),
        default=timezone.now,
        db_index=True
    )

    class Meta:
        verbose_name = _('Registro de Acceso')
        verbose_name_plural = _('Registros de Accesos')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['member', 'timestamp']),
            models.Index(fields=['result', 'direction', 'timestamp']),
        ]

    def __str__(self):
        member_desc = self.member.get_full_name() if self.member else "Desconocido"
        return f"[{self.timestamp.strftime('%H:%M:%S')}] {self.get_direction_display()} - {member_desc}: {self.get_result_display()}"

