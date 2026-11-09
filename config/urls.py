"""
FitLife URL Configuration
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static

from apps.website.views import redirect_to_home, api_not_found

# Personalización del encabezado del Django Admin
admin.site.site_header = "Panel FitLife"
admin.site.site_title = "FitLife Administración"
admin.site.index_title = "Gestión Integral de Centro Deportivo"

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),

    # API REST (DRF & JWT)
    path('api/', include('config.api_urls')),

    # Portal Web Público y Privado
    path('', include('apps.website.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])

# --------------------------------------------------------------------------
# Catch-all: Redirigir rutas inexistentes al inicio (cubre DEBUG=True).
# - /api/* → respuesta JSON 404 (para clientes REST).
# - /static/* y /media/* se dejan pasar para que su 404 nativo revele
#   errores de carga de CSS/JS/imágenes (nunca se redirigen a HTML).
# - Cualquier otra ruta inexistente → redirección 302 a '/'.
# --------------------------------------------------------------------------
urlpatterns += [
    re_path(r'^api/.*$', api_not_found),   # API endpoints inexistentes → JSON 404
    re_path(r'^(?!static/|media/).*$', redirect_to_home),  # todo lo demás → inicio
]

# Handlers personalizados para errores HTTP (cubren DEBUG=False / producción)
handler404 = 'apps.website.views.redirect_to_home'
handler403 = 'apps.website.error_views.custom_403'
handler500 = 'apps.website.error_views.custom_500'
