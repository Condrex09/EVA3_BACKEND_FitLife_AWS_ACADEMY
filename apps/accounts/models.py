import uuid
import io
import base64
import qrcode
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from .validators import validate_rut, format_rut, clean_rut

class UserRole(models.TextChoices):
    ADMIN = 'ADMIN', _('Administrador')
    RECEPTION = 'RECEPTION', _('Recepción')
    MEMBER = 'MEMBER', _('Socio')

class User(AbstractUser):
    """
    Usuario personalizado para FitLife con roles definidos y email único.
    """
    email = models.EmailField(_('correo electrónico'), unique=True)
    role = models.CharField(
        _('rol'),
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.MEMBER,
        db_index=True,
        help_text=_('Define las atribuciones operativas dentro de FitLife.')
    )

    class Meta:
        verbose_name = _('Usuario')
        verbose_name_plural = _('Usuarios')
        ordering = ['-date_joined']

    def __str__(self):
        full_name = self.get_full_name()
        return f"{full_name} ({self.username}) [{self.get_role_display()}]" if full_name else f"{self.username} [{self.get_role_display()}]"

    @property
    def is_admin_role(self) -> bool:
        return self.role == UserRole.ADMIN or self.is_superuser

    @property
    def is_reception(self) -> bool:
        return self.role in [UserRole.RECEPTION, UserRole.ADMIN]

    @property
    def is_member(self) -> bool:
        return self.role == UserRole.MEMBER


class MemberProfile(models.Model):
    """
    Ficha de socio vinculada uno a uno con el usuario con rol MEMBER.
    Contiene el token único para el pase de acceso QR y antecedentes personales.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name=_('Usuario')
    )
    rut = models.CharField(
        _('RUT'),
        max_length=15,
        unique=True,
        validators=[validate_rut],
        help_text=_('Formato: 12.345.678-5')
    )
    phone = models.CharField(
        _('Teléfono'),
        max_length=25,
        blank=True,
        help_text=_('Ej: +56 9 1234 5678')
    )
    birth_date = models.DateField(
        _('Fecha de nacimiento'),
        null=True,
        blank=True
    )
    emergency_contact = models.CharField(
        _('Contacto de emergencia'),
        max_length=150,
        blank=True,
        help_text=_('Nombre y teléfono de familiar o contacto cercano.')
    )
    qr_token = models.UUIDField(
        _('Token QR de acceso'),
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        help_text=_('Identificador único e infalsificable codificado en el código QR.')
    )
    created_at = models.DateTimeField(
        _('Fecha de registro'),
        auto_now_add=True
    )

    class Meta:
        verbose_name = _('Perfil de Socio')
        verbose_name_plural = _('Perfiles de Socios')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} (RUT: {self.formatted_rut})"

    def clean(self):
        super().clean()
        if self.rut:
            self.rut = clean_rut(self.rut)

    def save(self, *args, **kwargs):
        if self.rut:
            self.rut = clean_rut(self.rut)
        super().save(*args, **kwargs)

    @property
    def formatted_rut(self) -> str:
        return format_rut(self.rut)

    def generate_qr_base64(self) -> str:
        """
        Genera el código QR del socio codificando su qr_token en formato Base64 Data URI
        para ser incrustado directamente en HTML sin guardar imágenes estáticas temporales.
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(str(self.qr_token))
        qr.make(fit=True)
        img = qr.make_image(fill_color="#111111", back_color="#FFFFFF")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{encoded}"

