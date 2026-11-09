from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from apps.accounts.api_views import CurrentUserView
from apps.memberships.api_views import PlanViewSet, MembershipViewSet, PaymentViewSet
from apps.classes.api_views import ClassTypeViewSet, ClassSessionViewSet, BookingViewSet
from apps.access.api_views import (
    QRValidationView,
    AccessLogViewSet,
    FacilityOccupancyView,
    FacilityOccupancySummaryView,
)

router = DefaultRouter()
router.register(r'plans', PlanViewSet, basename='api-plan')
router.register(r'memberships', MembershipViewSet, basename='api-membership')
router.register(r'payments', PaymentViewSet, basename='api-payment')
router.register(r'classes', ClassTypeViewSet, basename='api-classtype')
router.register(r'sessions', ClassSessionViewSet, basename='api-session')
router.register(r'bookings', BookingViewSet, basename='api-booking')
router.register(r'access/logs', AccessLogViewSet, basename='api-accesslog')

urlpatterns = [
    # Autenticación JWT
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Perfil del socio autenticado
    path('me/', CurrentUserView.as_view(), name='api-me'),

    # Control de Acceso y Aforo
    path('access/validate/', QRValidationView.as_view(), name='api-access-validate'),
    path('aforo/resumen/', FacilityOccupancySummaryView.as_view(), name='api-aforo-resumen'),
    path('aforo/', FacilityOccupancyView.as_view(), name='api-aforo'),

    # Recursos vía Router
    path('', include(router.urls)),
]
