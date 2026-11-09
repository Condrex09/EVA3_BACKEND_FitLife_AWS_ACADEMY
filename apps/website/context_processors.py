from decouple import config
from .models import Notification

def site_context(request):
    """
    Context processor global que inyecta:
    - Footer obligatorio institucional
    - Contador de notificaciones no leídas
    - Credenciales demo del admin y bandera SHOW_DEMO_CREDENTIALS
    """
    footer_text = "Desarrollado por Benjamin Gomez · Sección AP-N4-C1 · INACAP · EVA 3 Desarrollo Backend"
    unread_notifications = 0
    if request.user.is_authenticated and getattr(request.user, 'role', None) == 'MEMBER':
        unread_notifications = Notification.objects.filter(member=request.user, is_read=False).count()

    show_demo_credentials = config('SHOW_DEMO_CREDENTIALS', default=True, cast=bool)
    demo_admin_user = config('DEMO_ADMIN_USER', default='admin')
    demo_admin_email = config('DEMO_ADMIN_EMAIL', default='admin@fitlife.cl')
    demo_admin_password = config('DEMO_ADMIN_PASSWORD', default='Admin#FitLife2026')

    return {
        'FOOTER_TEXT': footer_text,
        'UNREAD_NOTIFICATIONS_COUNT': unread_notifications,
        'CURRENT_YEAR': 2026,
        'SHOW_DEMO_CREDENTIALS': show_demo_credentials,
        'DEMO_ADMIN_USER': demo_admin_user,
        'DEMO_ADMIN_EMAIL': demo_admin_email,
        'DEMO_ADMIN_PASSWORD': demo_admin_password,
    }
