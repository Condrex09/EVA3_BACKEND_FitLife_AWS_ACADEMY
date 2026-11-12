from django.urls import path
from . import views

urlpatterns = [
    # Páginas Públicas
    path('', views.home_view, name='home'),
    path('planes/', views.plans_view, name='plans'),
    path('clases/', views.classes_schedule_view, name='classes-schedule'),
    path('sede/', views.facility_view, name='facility'),
    path('contacto/', views.contact_view, name='contact'),

    # Autenticación
    path('registro/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Portal del Socio
    path('mi-cuenta/', views.profile_view, name='profile'),
    path('checkout/<slug:plan_slug>/', views.checkout_view, name='checkout'),
    path('renovar/', views.renew_view, name='renew'),
    path('clases/reservar/', views.booking_calendar_view, name='booking-calendar'),
    path('clases/reservar/<int:session_id>/', views.book_session_action, name='book-session-action'),
    path('clases/cancelar/<int:booking_id>/', views.cancel_booking_action, name='cancel-booking-action'),
    path('notificaciones/<int:notif_id>/leer/', views.mark_notification_read, name='mark-notification-read'),

    # Personal de Recepción (Mostrador)
    path('recepcion/', views.reception_home_view, name='reception-home'),
    path('recepcion/acceso/', views.reception_access_view, name='reception-access'),
    path('dashboard/aforo/', views.dashboard_aforo_view, name='dashboard-aforo'),
    path('recepcion/socios/', views.reception_members_view, name='reception-members'),
    path('recepcion/socios/<int:user_id>/', views.reception_member_detail_view, name='reception-member-detail'),
    path('recepcion/socios/<int:user_id>/contacto/', views.reception_edit_contact_view, name='reception-edit-contact'),
    path('recepcion/socios/<int:user_id>/pase/', views.reception_member_qr_pass_view, name='reception-member-qr-pass'),
    path('recepcion/socios/<int:user_id>/pago-manual/', views.reception_manual_payment_view, name='reception-manual-payment'),
    path('recepcion/membresias/<int:membership_id>/congelar/', views.reception_freeze_membership_view, name='reception-freeze'),
    path('recepcion/membresias/<int:membership_id>/descongelar/', views.reception_unfreeze_membership_view, name='reception-unfreeze'),
    path('recepcion/inscribir/', views.reception_enroll_view, name='reception-enroll'),
    path('recepcion/clases/', views.reception_classes_view, name='reception-classes'),
    path('recepcion/clases/<int:session_id>/reservar/', views.reception_book_for_member_view, name='reception-book-for-member'),
    path('recepcion/reservas/<int:booking_id>/asistencia/', views.reception_update_attendance_view, name='reception-update-attendance'),
    path('recepcion/reservas/<int:booking_id>/cancelar/', views.reception_cancel_booking_view, name='reception-cancel-booking'),
]
