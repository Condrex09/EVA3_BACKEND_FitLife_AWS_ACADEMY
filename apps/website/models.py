from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.accounts.models import User

class ContactMessage(models.Model):
    """
    Mensajes recibidos mediante el formulario de contacto público.
    """
    name = models.CharField(_('Nombre completo'), max_length=120)
    email = models.EmailField(_('Correo de contacto'))
    subject = models.CharField(_('Asunto'), max_length=150)
    message = models.TextField(_('Mensaje o consulta'))
    created_at = models.DateTimeField(_('Fecha de recepción'), auto_now_add=True)
    is_read = models.BooleanField(_('Leído por administración'), default=False)

    class Meta:
        verbose_name = _('Mensaje de Contacto')
        verbose_name_plural = _('Mensajes de Contacto')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.subject} ({self.created_at.strftime('%d/%m/%Y')})"


class Notification(models.Model):
    """
    Notificaciones internas dirigidas a socios (ej. cupo liberado en lista de espera,
    cancelación de clase por staff, vencimiento próximo).
    """
    member = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('Socio destinatario')
    )
    title = models.CharField(_('Título'), max_length=150)
    message = models.TextField(_('Cuerpo del mensaje'))
    created_at = models.DateTimeField(_('Fecha de notificación'), auto_now_add=True)
    is_read = models.BooleanField(_('Leída'), default=False)

    class Meta:
        verbose_name = _('Notificación de Socio')
        verbose_name_plural = _('Notificaciones de Socios')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} -> {self.member.username} ({'Leída' if self.is_read else 'Nueva'})"

