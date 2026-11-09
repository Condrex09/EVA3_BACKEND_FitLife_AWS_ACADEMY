from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from apps.accounts.models import User, UserRole

class ClassIntensity(models.TextChoices):
    LOW = 'LOW', _('Baja')
    MEDIUM = 'MEDIUM', _('Media')
    HIGH = 'HIGH', _('Alta')

class ClassType(models.Model):
    """
    Disciplina o tipo de clase grupal impartida en FitLife
    (ej. Spinning, Yoga, Funcional, Zumba, HIIT, Pilates).
    """
    name = models.CharField(_('Nombre de la disciplina'), max_length=100, unique=True)
    slug = models.SlugField(_('Identificador URL'), unique=True)
    description = models.TextField(_('Descripción y objetivos del entrenamiento'))
    duration_minutes = models.PositiveIntegerField(_('Duración en minutos'), default=50)
    intensity = models.CharField(
        _('Nivel de intensidad'),
        max_length=10,
        choices=ClassIntensity.choices,
        default=ClassIntensity.MEDIUM
    )
    icon_or_image = models.CharField(
        _('Ícono o imagen descriptiva'),
        max_length=255,
        default='fa-dumbbell',
        help_text=_('Clase CSS de FontAwesome o URL de imagen de la disciplina.')
    )
    is_active = models.BooleanField(_('Activo en el gimnasio'), default=True)

    class Meta:
        verbose_name = _('Tipo de Clase')
        verbose_name_plural = _('Tipos de Clases')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.duration_minutes} min - {self.get_intensity_display()})"


class SessionStatus(models.TextChoices):
    SCHEDULED = 'SCHEDULED', _('Programada')
    CANCELLED = 'CANCELLED', _('Cancelada')
    DONE = 'DONE', _('Finalizada')


class ClassSession(models.Model):
    """
    Sesión específica de una clase grupal con fecha, hora, sala y capacidad máxima.
    """
    class_type = models.ForeignKey(
        ClassType,
        on_delete=models.PROTECT,
        related_name='sessions',
        verbose_name=_('Disciplina')
    )
    instructor_name = models.CharField(_('Nombre del Instructor(a)'), max_length=120)
    room = models.CharField(_('Sala / Espacio'), max_length=80, default='Sala Principal')
    start_datetime = models.DateTimeField(_('Fecha y hora de inicio'), db_index=True)
    end_datetime = models.DateTimeField(_('Fecha y hora de término'))
    capacity = models.PositiveIntegerField(_('Cupos máximos'), default=20)
    status = models.CharField(
        _('Estado de la sesión'),
        max_length=15,
        choices=SessionStatus.choices,
        default=SessionStatus.SCHEDULED,
        db_index=True
    )

    class Meta:
        verbose_name = _('Sesión de Clase')
        verbose_name_plural = _('Sesiones de Clases')
        ordering = ['start_datetime']

    def __str__(self):
        start_str = timezone.localtime(self.start_datetime).strftime('%d/%m %H:%M')
        return f"{self.class_type.name} - {start_str} ({self.instructor_name})"

    def clean(self):
        super().clean()
        if self.start_datetime and self.end_datetime and self.end_datetime <= self.start_datetime:
            raise ValidationError({'end_datetime': _('La hora de término debe ser posterior al inicio.')})

    @property
    def confirmed_count(self) -> int:
        return self.bookings.filter(status=BookingStatus.CONFIRMED).count()

    @property
    def waitlist_count(self) -> int:
        return self.bookings.filter(status=BookingStatus.WAITLIST).count()

    @property
    def available_spots(self) -> int:
        return max(0, self.capacity - self.confirmed_count)

    @property
    def is_full(self) -> bool:
        return self.available_spots == 0

    @property
    def can_be_booked(self) -> bool:
        return self.status == SessionStatus.SCHEDULED and self.start_datetime > timezone.now()


class BookingStatus(models.TextChoices):
    CONFIRMED = 'CONFIRMED', _('Confirmada')
    WAITLIST = 'WAITLIST', _('Lista de Espera')
    CANCELLED = 'CANCELLED', _('Cancelada')
    ATTENDED = 'ATTENDED', _('Asistió')
    NO_SHOW = 'NO_SHOW', _('No Asistió')


class Booking(models.Model):
    """
    Reserva de un socio para una sesión de clase grupal.
    Soporta lista de espera con posición ordenada y promoción automática al liberarse cupo.
    """
    session = models.ForeignKey(
        ClassSession,
        on_delete=models.CASCADE,
        related_name='bookings',
        verbose_name=_('Sesión de clase')
    )
    member = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='class_bookings',
        limit_choices_to={'role': UserRole.MEMBER},
        verbose_name=_('Socio')
    )
    status = models.CharField(
        _('Estado de reserva'),
        max_length=15,
        choices=BookingStatus.choices,
        default=BookingStatus.CONFIRMED,
        db_index=True
    )
    waitlist_position = models.PositiveIntegerField(
        _('Posición en lista de espera'),
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(_('Fecha de reserva'), auto_now_add=True)
    cancelled_at = models.DateTimeField(_('Fecha de cancelación'), null=True, blank=True)

    class Meta:
        verbose_name = _('Reserva de Clase')
        verbose_name_plural = _('Reservas de Clases')
        ordering = ['session', 'status', 'waitlist_position', 'created_at']

    def __str__(self):
        return f"Reserva #{self.id}: {self.member.get_full_name() or self.member.username} en {self.session.class_type.name} [{self.get_status_display()}]"

    def clean(self):
        super().clean()
        if self.status in [BookingStatus.CONFIRMED, BookingStatus.WAITLIST]:
            # Evitar doble reserva activa en la misma sesión
            existing = Booking.objects.filter(
                session=self.session,
                member=self.member,
                status__in=[BookingStatus.CONFIRMED, BookingStatus.WAITLIST]
            )
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(_('Ya tienes una reserva activa o en lista de espera para esta sesión.'))

