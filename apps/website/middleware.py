from django.shortcuts import redirect
from django.conf import settings
from django.contrib import messages

class DynamicCSRFTrustedOriginMiddleware:
    """
    Agrega dinámicamente el origen de la petición a CSRF_TRUSTED_ORIGINS
    para evitar errores 403 Forbidden al enviar formularios desde cualquier
    IP pública o elástica en AWS EC2 (según receta INACAP).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host()
        if host:
            clean_host = host.split(':')[0]
            origin = f"{request.scheme}://{clean_host}"
            origin_port = f"{request.scheme}://{host}"
            if origin not in settings.CSRF_TRUSTED_ORIGINS:
                settings.CSRF_TRUSTED_ORIGINS.append(origin)
            if origin_port not in settings.CSRF_TRUSTED_ORIGINS:
                settings.CSRF_TRUSTED_ORIGINS.append(origin_port)

        return self.get_response(request)


class AdminAccessRestrictionMiddleware:
    """
    Bloquea el acceso a /admin/ para usuarios autenticados sin permisos de staff
    (como personal de recepción o socios), redirigiéndolos de manera
    amable a su panel con el mensaje: 'El panel de administración es solo para administradores'.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            # Solo interceptar usuarios autenticados que no sean staff
            if hasattr(request, 'user') and request.user.is_authenticated and not request.user.is_staff:
                messages.warning(request, "El panel de administración es solo para administradores.")
                if getattr(request.user, 'role', None) == 'RECEPTION':
                    return redirect('reception-home')
                return redirect('profile')

        return self.get_response(request)


class NotFoundRedirectMiddleware:
    """
    Middleware que intercepta respuestas 404 en peticiones GET
    cuyo path no corresponda a API, estáticos ni media,
    y las redirige automáticamente a la página de inicio ('/').
    Cubre tanto entornos con DEBUG=True como DEBUG=False,
    incluyendo rutas inexistentes dentro de /admin/.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if response.status_code == 404 and request.method == 'GET':
            path = request.path_info
            # No redirigir llamadas a API REST ni recursos estáticos/media
            if not (path.startswith('/api/') or path.startswith('/static/') or path.startswith('/media/')):
                return redirect('home')

        return response
