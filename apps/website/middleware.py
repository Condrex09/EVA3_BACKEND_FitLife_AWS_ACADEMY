from django.shortcuts import redirect

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

