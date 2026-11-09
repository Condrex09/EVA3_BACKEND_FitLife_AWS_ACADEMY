from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from apps.accounts.models import User

class EmailOrUsernameModelBackend(ModelBackend):
    """
    Backend de autenticación que permite iniciar sesión tanto con el
    nombre de usuario como con la dirección de correo electrónico
    (sin distinguir mayúsculas/minúsculas).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get('email')
        if username is None or password is None:
            return None

        try:
            # Buscar coincidencia exacta por username o case-insensitive por email
            user = User.objects.get(
                Q(username__iexact=username) | Q(email__iexact=username)
            )
        except User.DoesNotExist:
            # Ejecutar el hasher de contraseñas para mitigar ataques de timing
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            # En caso raro de múltiples, tomar el primero que coincida por username
            user = User.objects.filter(
                Q(username__iexact=username) | Q(email__iexact=username)
            ).order_by('id').first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

