from datetime import timedelta
from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse

from apps.accounts.models import User, MemberProfile, UserRole
from apps.accounts.validators import clean_rut, validate_rut, format_rut
from apps.memberships.models import Plan, Membership, Payment, MembershipStatus, PaymentMethod, PaymentConcept
from apps.memberships.services import (
    process_subscription_payment, renew_membership, update_membership_status,
    freeze_membership, unfreeze_membership, record_manual_payment_at_reception,
    enroll_member_at_reception, MAX_FREEZE_DAYS, regenerate_qr_token
)
from apps.classes.models import ClassType, ClassSession, Booking, BookingStatus, SessionStatus
from apps.classes.services import book_class_session, cancel_booking
from apps.access.models import FacilitySetting, AccessLog
from apps.access.services import get_facility_occupancy_data, validate_and_record_access
from .models import Notification
from .forms import MemberRegistrationForm, MemberLoginForm, ContactForm, SimulatedPaymentForm

def home_view(request):
    """Página principal de FitLife con estilo dinámico inspirado en Smart Fit."""
    plans = Plan.objects.filter(is_active=True).order_by('order', 'monthly_price')[:3]
    class_types = ClassType.objects.filter(is_active=True)[:6]
    facility = FacilitySetting.load()
    return render(request, 'website/index.html', {
        'plans': plans,
        'class_types': class_types,
        'facility': facility,
    })

def plans_view(request):
    """Catálogo de planes comerciales con detalle de beneficios y precios en CLP."""
    plans = Plan.objects.filter(is_active=True).order_by('order', 'monthly_price')
    return render(request, 'website/plans.html', {'plans': plans})

def classes_schedule_view(request):
    """Horario semanal de clases grupales con filtros por disciplina y día."""
    now = timezone.now()
    class_types = ClassType.objects.filter(is_active=True)
    selected_class_type = request.GET.get('type')
    selected_day = request.GET.get('day')

    sessions = ClassSession.objects.filter(
        start_datetime__gte=now,
        start_datetime__lte=now + timedelta(days=7),
        status=SessionStatus.SCHEDULED
    ).select_related('class_type').order_by('start_datetime')

    if selected_class_type:
        sessions = sessions.filter(class_type__slug=selected_class_type)

    # Agrupar sesiones por fecha para visualización en acordeón o tabs
    sessions_by_date = {}
    for session in sessions:
        local_date = timezone.localtime(session.start_datetime).date()
        date_str = local_date.strftime('%Y-%m-%d')
        if selected_day and date_str != selected_day:
            continue
        if date_str not in sessions_by_date:
            sessions_by_date[date_str] = {
                'date': local_date,
                'sessions': []
            }
        sessions_by_date[date_str]['sessions'].append(session)

    return render(request, 'website/classes.html', {
        'class_types': class_types,
        'selected_class_type': selected_class_type,
        'selected_day': selected_day,
        'sessions_by_date': sessions_by_date,
    })

def facility_view(request):
    """Información de la sede FitLife: equipamiento, salas, servicios y horarios."""
    facility = FacilitySetting.load()
    return render(request, 'website/facility.html', {'facility': facility})

def contact_view(request):
    """Formulario de contacto público y preguntas frecuentes."""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "¡Gracias por contactarnos! Tu mensaje fue recibido y te responderemos a la brevedad.")
            return redirect('contact')
    else:
        form = ContactForm()
    return render(request, 'website/contact.html', {'form': form})

def register_view(request):
    """Registro público de nuevos socios con asignación automática de rol MEMBER y RUT."""
    if request.user.is_authenticated:
        return redirect('profile')

    if request.method == 'POST':
        form = MemberRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"¡Bienvenido a FitLife, {user.first_name}! Tu cuenta y pase QR han sido creados.")
            plan_slug = request.GET.get('plan')
            if plan_slug:
                return redirect('checkout', plan_slug=plan_slug)
            return redirect('plans')
    else:
        form = MemberRegistrationForm()
    return render(request, 'website/register.html', {'form': form})

def login_view(request):
    """Inicio de sesión con soporte para 'recordarme' y redirección según rol."""
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)

    if request.method == 'POST':
        form = MemberLoginForm(request.POST)
        if form.is_valid():
            username_or_email = form.cleaned_data['username']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data.get('remember_me', False)

            # Autenticar por usuario o por correo vía EmailOrUsernameModelBackend
            user = authenticate(request, username=username_or_email, password=password)

            if user is not None:
                login(request, user)
                if not remember_me:
                    request.session.set_expiry(0)  # Cierra sesión al cerrar navegador
                else:
                    request.session.set_expiry(60 * 60 * 24 * 14)  # 2 semanas

                messages.success(request, f"¡Bienvenido de vuelta, {user.first_name or user.username}!")

                # Respetar ?next= si es una URL segura
                next_url = request.GET.get('next') or request.POST.get('next')
                if next_url and url_has_allowed_host_and_scheme(
                    next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)
                return _redirect_by_role(user)
            else:
                messages.error(request, "Usuario, correo o contraseña incorrectos.")
    else:
        form = MemberLoginForm()
    return render(request, 'website/login.html', {'form': form})


def _redirect_by_role(user):
    """Redirige al usuario según su rol después del login."""
    if user.role == UserRole.ADMIN:
        return redirect('/admin/')
    elif user.role == UserRole.RECEPTION:
        return redirect('reception-home')
    return redirect('profile')

def logout_view(request):
    """Cierra la sesión de manera segura exigiendo método POST con protección CSRF."""
    if request.method != 'POST':
        return redirect('home')
    logout(request)
    messages.info(request, "Has cerrado tu sesión en FitLife correctamente.")
    return redirect('home')

@login_required
def profile_view(request):
    """Panel privado del socio ('Mi Espacio'): estado de membresía, QR pass, reservas y pagos."""
    user = request.user
    if user.role in [UserRole.ADMIN, UserRole.RECEPTION]:
        # Redirigir staff a la vista de recepción
        return redirect('reception-access')

    profile = getattr(user, 'profile', None)    qr_base64 = profile.generate_qr_base64() if profile else ""

    # Membresía actual
    membership = Membership.objects.filter(member=user).order_by('-end_date').first()
    if membership:
        membership = update_membership_status(membership)

    # Historial de pagos
    payments = Payment.objects.filter(member=user).order_by('-paid_at')[:10]

    # Mis reservas activas
    now = timezone.now()
    bookings = Booking.objects.filter(
        member=user,
        session__start_datetime__gte=now - timedelta(hours=2)
    ).select_related('session', 'session__class_type').order_by('session__start_datetime')

    # Historial de reservas pasadas
    past_bookings = Booking.objects.filter(
        member=user,
        session__start_datetime__lt=now - timedelta(hours=2)
    ).select_related('session', 'session__class_type').order_by('-session__start_datetime')[:10]

    # Notificaciones del socio
    notifications = Notification.objects.filter(member=user).order_by('-created_at')[:8]

    return render(request, 'website/profile.html', {
        'profile': profile,
        'qr_base64': qr_base64,
        'membership': membership,
        'payments': payments,
        'bookings': bookings,
        'past_bookings': past_bookings,
        'notifications': notifications,
    })

@login_required
def checkout_view(request, plan_slug):
    """Página de checkout con formulario simulado de pago para adquirir o renovar membresías."""
    plan = get_object_or_404(Plan, slug=plan_slug, is_active=True)
    total_amount = plan.monthly_price + plan.enrollment_price

    if request.method == 'POST':
        form = SimulatedPaymentForm(request.POST)
        if form.is_valid():
            card_number = form.cleaned_data['card_number']
            card_expiry = form.cleaned_data['card_expiry']
            card_cvv = form.cleaned_data['card_cvv']

            payment, membership, success, message = process_subscription_payment(
                member_user=request.user,
                plan=plan,
                card_number=card_number,
                card_expiry=card_expiry,
                card_cvv=card_cvv
            )

            if success:
                messages.success(request, message)
                return redirect('profile')
            else:
                messages.error(request, message)
    else:
        form = SimulatedPaymentForm(initial={'card_holder': request.user.get_full_name()})

    return render(request, 'website/checkout.html', {
        'plan': plan,
        'total_amount': total_amount,
        'form': form,
    })

@login_required
def renew_view(request):
    """Renovación rápida de la última membresía del socio."""
    membership = Membership.objects.filter(member=request.user).order_by('-end_date').first()
    if not membership:
        messages.warning(request, "No registras ninguna membresía previa. Selecciona un plan para comenzar.")
        return redirect('plans')

    if request.method == 'POST':
        form = SimulatedPaymentForm(request.POST)
        if form.is_valid():
            card_number = form.cleaned_data['card_number']
            payment, membership, success, message = renew_membership(
                member_user=request.user,
                plan=membership.plan,
                card_number=card_number
            )
            if success:
                messages.success(request, message)
                return redirect('profile')
            else:
                messages.error(request, message)
    else:
        form = SimulatedPaymentForm(initial={'card_holder': request.user.get_full_name()})

    return render(request, 'website/renew.html', {
        'membership': membership,
        'plan': membership.plan,
        'form': form,
    })

@login_required
def booking_calendar_view(request):
    """Portal interactivo de reserva de clases para socios."""
    now = timezone.now()
    membership = Membership.objects.filter(member=request.user).order_by('-end_date').first()
    has_active_membership = False
    if membership:
        membership = update_membership_status(membership)
        has_active_membership = (membership.status == MembershipStatus.ACTIVE and membership.end_date >= timezone.localdate())

    class_types = ClassType.objects.filter(is_active=True)
    selected_class_type = request.GET.get('type')

    sessions = ClassSession.objects.filter(
        start_datetime__gte=now,
        start_datetime__lte=now + timedelta(days=7),
        status=SessionStatus.SCHEDULED
    ).select_related('class_type').order_by('start_datetime')

    if selected_class_type:
        sessions = sessions.filter(class_type__slug=selected_class_type)

    # Identificar reservas ya hechas por el usuario
    my_session_ids = set(
        Booking.objects.filter(
            member=request.user,
            status__in=[BookingStatus.CONFIRMED, BookingStatus.WAITLIST]
        ).values_list('session_id', flat=True)
    )

    # Agrupar por fecha
    days_data = {}
    for s in sessions:
        date_key = timezone.localtime(s.start_datetime).strftime('%Y-%m-%d')
        if date_key not in days_data:
            days_data[date_key] = {
                'date': timezone.localtime(s.start_datetime).date(),
                'sessions': []
            }
        s.user_has_booking = (s.id in my_session_ids)
        days_data[date_key]['sessions'].append(s)

    return render(request, 'website/booking_calendar.html', {
        'has_active_membership': has_active_membership,
        'days_data': days_data,
        'class_types': class_types,
        'selected_class_type': selected_class_type,
    })

@login_required
def book_session_action(request, session_id):
    """Acción de reserva mediante POST para socios."""
    if request.method != 'POST':
        return redirect('booking-calendar')

    try:
        booking, is_confirmed, msg = book_class_session(request.user, session_id)
        if is_confirmed:
            messages.success(request, msg)
        else:
            messages.warning(request, msg)
    except ValidationError as e:
        messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return redirect('booking-calendar')

@login_required
def cancel_booking_action(request, booking_id):
    """Acción de cancelación de reserva por el socio."""
    if request.method != 'POST':
        return redirect('profile')

    try:
        cancel_booking(booking_id, requesting_user=request.user)
        messages.success(request, "Tu reserva ha sido cancelada correctamente.")
    except (ValidationError, PermissionDenied) as e:
        messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return redirect('profile')

@login_required
def mark_notification_read(request, notif_id):
    """Marca una notificación como leída."""
    notif = get_object_or_404(Notification, id=notif_id, member=request.user)
    notif.is_read = True
    notif.save()
    return redirect('profile')

# -------------------------------------------------------------
# Vistas exclusivas de Recepción y Personal Administrativo
# -------------------------------------------------------------

def reception_required(view_func):
    """
    Decorador para autorizar el acceso exclusivamente al personal de Recepción o Administrador.
    Rechaza a usuarios no autenticados y a socios normales.
    """
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.role not in [UserRole.ADMIN, UserRole.RECEPTION]:
            messages.error(request, "Acceso restringido: no tienes permisos de recepción.")
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


# Compatibilidad hacia atrás si alguna vista interna usa staff_required
staff_required = reception_required


@reception_required
def reception_home_view(request):
    """
    Panel central de recepción (Mostrador).
    Muestra tarjetas de acceso rápido y alertas operativas del día.
    """
    today = timezone.localdate()
    now = timezone.now()

    # 1. Alertas: membresías que vencen en los próximos 7 días
    in_7_days = today + timedelta(days=7)
    expiring_soon = (
        Membership.objects.filter(
            status=MembershipStatus.ACTIVE,
            end_date__gte=today,
            end_date__lte=in_7_days
        )
        .select_related('member', 'member__profile', 'plan')
        .order_by('end_date')[:6]
    )

    # 2. Alertas: membresías vencidas hoy
    expired_today = (
        Membership.objects.filter(
            status=MembershipStatus.EXPIRED,
            end_date=today
        )
        .select_related('member', 'member__profile', 'plan')[:6]
    )

    # 3. Alertas: sesiones de hoy con lista de espera
    waitlist_sessions = (
        ClassSession.objects.filter(
            start_datetime__date=today,
            bookings__status=BookingStatus.WAITLIST
        )
        .distinct()
        .select_related('class_type')
        .order_by('start_datetime')
    )

    # 4. Datos de aforo instantáneo
    aforo_data = get_facility_occupancy_data()

    return render(request, 'website/reception_home.html', {
        'expiring_soon': expiring_soon,
        'expired_today': expired_today,
        'waitlist_sessions': waitlist_sessions,
        'aforo_data': aforo_data,
        'today': today,
    })


@reception_required
def reception_access_view(request):
    """
    Interfaz de recepción para validación de acceso por QR.
    Incluye cámara web en vivo, autofocus en el código para lector USB de código de barras,
    tarjeta grande con resultado (verde/rojo) y alerta si la membresía vence en <7 días.
    """
    recent_logs = AccessLog.objects.select_related('member', 'member__profile').order_by('-timestamp')[:10]

    demo_tokens = []
    from decouple import config
    if config('SHOW_DEMO_CREDENTIALS', default=False, cast=bool):
        demo_usernames = ['carlos.silva', 'maria.gonzalez', 'juan.perez']
        demo_users = User.objects.filter(username__in=demo_usernames).select_related('profile')
        status_map = {
            'carlos.silva': 'Activo · FitLife Black',
            'maria.gonzalez': 'Vencido · Simula rechazo',
            'juan.perez': 'Congelado · Simula rechazo',
        }
        for u in demo_users:
            profile = getattr(u, 'profile', None)
            if profile:
                demo_tokens.append({
                    'name': u.get_full_name() or u.username,
                    'username': u.username,
                    'token': str(profile.qr_token),
                    'label': f"{u.first_name} {u.last_name} ({status_map.get(u.username, '')})"
                })

    return render(request, 'website/reception_access.html', {
        'recent_logs': recent_logs,
        'demo_tokens': demo_tokens,
    })


@reception_required
def dashboard_aforo_view(request):
    """
    Dashboard de aforo en tiempo real con tarjeta principal, barra de porcentaje,
    lista de socios dentro y gráfico de ingresos por hora del día con Chart.js.
    """
    data = get_facility_occupancy_data()
    return render(request, 'website/dashboard_aforo.html', {
        'aforo_data': data,
    })


@reception_required
def reception_members_view(request):
    """
    Buscador de socios para el personal de recepción.
    Solo busca y lista socios (UserRole.MEMBER). El personal administrativo nunca aparece.
    """
    query = request.GET.get('q', '').strip()
    members = []
    if query:
        clean_q = clean_rut(query)
        members = (
            User.objects.filter(role=UserRole.MEMBER)
            .filter(
                models.Q(username__icontains=query) |
                models.Q(first_name__icontains=query) |
                models.Q(last_name__icontains=query) |
                models.Q(email__icontains=query) |
                models.Q(profile__rut__icontains=clean_q or query) |
                models.Q(profile__phone__icontains=query)
            )
            .select_related('profile')
            .prefetch_related('memberships', 'memberships__plan')[:25]
        )
    return render(request, 'website/reception_members.html', {
        'query': query,
        'members': members,
    })


@reception_required
def reception_member_detail_view(request, user_id):
    """
    Ficha completa de un socio para recepción:
    - Datos de contacto y RUT.
    - Plan actual, estado y días restantes.
    - Acciones: Congelar, Descongelar, Registrar pago manual / renovar, Editar contacto, Ver Pase QR.
    - Historial de accesos, pagos con registered_by y próximas reservas.
    """
    member_user = get_object_or_404(User, id=user_id, role=UserRole.MEMBER)
    profile = getattr(member_user, 'profile', None)
    memberships = Membership.objects.filter(member=member_user).select_related('plan').order_by('-created_at')
    current_membership = memberships.first()
    if current_membership:
        current_membership = update_membership_status(current_membership)

    payments = Payment.objects.filter(member=member_user).select_related('registered_by').order_by('-paid_at')[:10]
    recent_logs = AccessLog.objects.filter(member=member_user).order_by('-timestamp')[:10]
    active_plans = Plan.objects.filter(is_active=True).order_by('order', 'monthly_price')

    now = timezone.now()
    upcoming_bookings = (
        Booking.objects.filter(
            member=member_user,
            session__start_datetime__gte=now - timedelta(hours=2)
        )
        .select_related('session', 'session__class_type')
        .order_by('session__start_datetime')[:6]
    )

    return render(request, 'website/reception_member_detail.html', {
        'member_user': member_user,
        'profile': profile,
        'current_membership': current_membership,
        'memberships': memberships,
        'payments': payments,
        'recent_logs': recent_logs,
        'active_plans': active_plans,
        'upcoming_bookings': upcoming_bookings,
        'MAX_FREEZE_DAYS': MAX_FREEZE_DAYS,
    })


@reception_required
def reception_edit_contact_view(request, user_id):
    """Permite al recepcionista editar únicamente el teléfono y contacto de emergencia de un socio."""
    if request.method != 'POST':
        return HttpResponseForbidden("Método no permitido")
    member_user = get_object_or_404(User, id=user_id, role=UserRole.MEMBER)
    profile = getattr(member_user, 'profile', None)
    if not profile:
        messages.error(request, "El socio no posee ficha de perfil.")
        return redirect('reception-member-detail', user_id=member_user.id)

    phone = request.POST.get('phone', '').strip()
    emergency_contact = request.POST.get('emergency_contact', '').strip()

    profile.phone = phone
    profile.emergency_contact = emergency_contact
    profile.save(update_fields=['phone', 'emergency_contact'])

    messages.success(request, f"Datos de contacto de {member_user.get_full_name()} actualizados correctamente.")
    return redirect('reception-member-detail', user_id=member_user.id)


@reception_required
def reception_freeze_membership_view(request, membership_id):
    """Acción operativa para congelar una membresía activa desde recepción (máx. 30 días)."""
    if request.method != 'POST':
        return HttpResponseForbidden("Método no permitido")
    membership = get_object_or_404(Membership, id=membership_id)
    frozen_until_str = request.POST.get('frozen_until')
    if not frozen_until_str:
        messages.error(request, "Debes ingresar una fecha límite para congelar la membresía.")
        return redirect('reception-member-detail', user_id=membership.member_id)

    try:
        from datetime import datetime
        frozen_until = datetime.strptime(frozen_until_str, '%Y-%m-%d').date()
        freeze_membership(membership, frozen_until)
        messages.success(request, f"Membresía congelada exitosamente hasta el {frozen_until.strftime('%d/%m/%Y')}.")
    except (ValueError, ValidationError) as e:
        messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return redirect('reception-member-detail', user_id=membership.member_id)


@reception_required
def reception_unfreeze_membership_view(request, membership_id):
    """Acción operativa para descongelar una membresía desde recepción."""
    if request.method != 'POST':
        return HttpResponseForbidden("Método no permitido")
    membership = get_object_or_404(Membership, id=membership_id)
    try:
        unfreeze_membership(membership)
        messages.success(request, f"Membresía descongelada correctamente. Nueva fecha de término: {membership.end_date.strftime('%d/%m/%Y')}.")
    except ValidationError as e:
        messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return redirect('reception-member-detail', user_id=membership.member_id)


@reception_required
def reception_manual_payment_view(request, user_id):
    """
    Registra un pago manual en mostrador (efectivo o transferencia).
    El monto siempre proviene del plan seleccionado (solo lectura).
    Si es transferencia, exige comprobante. Registra registered_by = request.user.
    """
    if request.method != 'POST':
        return HttpResponseForbidden("Método no permitido")
    member_user = get_object_or_404(User, id=user_id, role=UserRole.MEMBER)
    plan_id = request.POST.get('plan_id')
    method = request.POST.get('method', 'CASH')
    receipt_number = request.POST.get('receipt_number', '').strip()

    plan = get_object_or_404(Plan, id=plan_id)

    try:
        new_membership, payment = record_manual_payment_at_reception(
            member_user=member_user,
            plan=plan,
            method=method,
            receipt_number=receipt_number,
            reception_user=request.user
        )
        messages.success(
            request,
            f"Pago manual de ${payment.amount:,} CLP registrado ({payment.get_method_display()}). "
            f"Membresía {plan.name} activada hasta el {new_membership.end_date.strftime('%d/%m/%Y')}."
        )
    except ValidationError as e:
        messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return redirect('reception-member-detail', user_id=member_user.id)


@reception_required
def reception_member_qr_pass_view(request, user_id):
    """
    Página optimizada e imprimible para el Pase QR del socio.
    Muestra el QR en grande, datos personales, RUT, plan y estado.
    """
    member_user = get_object_or_404(User, id=user_id, role=UserRole.MEMBER)
    profile = getattr(member_user, 'profile', None)
    if not profile:
        messages.error(request, "El socio no posee ficha de perfil con Pase QR.")
        return redirect('reception-member-detail', user_id=member_user.id)

    membership = Membership.objects.filter(member=member_user).order_by('-end_date').first()
    if membership:
        membership = update_membership_status(membership)

    qr_base64 = profile.generate_qr_base64()
    temp_password = request.session.pop(f'temp_pass_{member_user.id}', None)

    return render(request, 'website/reception_member_qr_pass.html', {
        'member_user': member_user,
        'profile': profile,
        'membership': membership,
        'qr_base64': qr_base64,
        'temp_password': temp_password,
    })


@reception_required
def reception_enroll_view(request):
    """
    Inscribe a un socio nuevo en mostrador en un único formulario:
    Crea atómicamente User, Profile, QR token, Membership activa y Payment.
    Muestra contraseña temporal generada y redirige al pase QR imprimible.
    """
    active_plans = Plan.objects.filter(is_active=True).order_by('order', 'monthly_price')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        rut = request.POST.get('rut', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        emergency_contact = request.POST.get('emergency_contact', '').strip()
        plan_id = request.POST.get('plan_id')
        method = request.POST.get('method', 'CASH')
        receipt_number = request.POST.get('receipt_number', '').strip()

        plan = get_object_or_404(Plan, id=plan_id, is_active=True)

        try:
            user, profile, membership, payment, temp_password = enroll_member_at_reception(
                first_name=first_name,
                last_name=last_name,
                email=email,
                rut=rut,
                phone=phone,
                emergency_contact=emergency_contact,
                plan=plan,
                method=method,
                receipt_number=receipt_number,
                reception_user=request.user
            )

            # Guardar la contraseña temporal en sesión para mostrarla en el pase imprimible
            request.session[f'temp_pass_{user.id}'] = temp_password
            messages.success(
                request,
                f"¡Socio {user.get_full_name()} inscrito con éxito! "
                f"Membresía {plan.name} activada. Contraseña temporal generada: {temp_password}"
            )
            return redirect('reception-member-qr-pass', user_id=user.id)

        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
            return render(request, 'website/reception_enroll.html', {
                'active_plans': active_plans,
                'form_data': request.POST,
            })

    return render(request, 'website/reception_enroll.html', {
        'active_plans': active_plans,
        'form_data': {},
    })


@reception_required
def reception_classes_view(request):
    """
    Gestión operativa de clases del día:
    - Lista las sesiones de hoy con horario, cupos e instructor.
    - Lista de socios confirmados con botones 'Asistió' y 'No asistió'.
    - Lista de espera con orden.
    - Formulario para inscribir a un socio en la clase.
    """
    today = timezone.localdate()
    sessions = (
        ClassSession.objects.filter(start_datetime__date=today)
        .select_related('class_type')
        .prefetch_related('bookings', 'bookings__member', 'bookings__member__profile')
        .order_by('start_datetime')
    )

    # Preparar datos enriquecidos por sesión
    sessions_data = []
    for s in sessions:
        confirmed_bookings = s.bookings.filter(status__in=[BookingStatus.CONFIRMED, BookingStatus.ATTENDED, BookingStatus.NO_SHOW]).order_by('created_at')
        waitlist_bookings = s.bookings.filter(status=BookingStatus.WAITLIST).order_by('waitlist_position', 'created_at')
        sessions_data.append({
            'session': s,
            'confirmed_bookings': confirmed_bookings,
            'waitlist_bookings': waitlist_bookings,
            'confirmed_count': confirmed_bookings.count(),
            'waitlist_count': waitlist_bookings.count(),
        })

    # Socios activos disponibles para inscribir
    active_members = (
        User.objects.filter(
            role=UserRole.MEMBER,
            memberships__status=MembershipStatus.ACTIVE,
            memberships__end_date__gte=today
        )
        .distinct()
        .select_related('profile')
        .order_by('first_name', 'last_name')[:50]
    )

    return render(request, 'website/reception_classes.html', {
        'today': today,
        'sessions_data': sessions_data,
        'active_members': active_members,
    })


@reception_required
def reception_update_attendance_view(request, booking_id):
    """Marca la asistencia (ATTENDED) o inasistencia (NO_SHOW) de un socio a su clase."""
    if request.method != 'POST':
        return HttpResponseForbidden("Método no permitido")
    booking = get_object_or_404(Booking, id=booking_id)
    new_status = request.POST.get('status')

    if new_status in [BookingStatus.ATTENDED, BookingStatus.NO_SHOW, BookingStatus.CONFIRMED]:
        booking.status = new_status
        booking.save(update_fields=['status'])
        status_label = "presente (Asistió)" if new_status == BookingStatus.ATTENDED else "ausente (No Asistió)"
        messages.success(request, f"Reserva de {booking.member.get_full_name()} marcada como {status_label}.")
    else:
        messages.error(request, "Estado de asistencia no reconocido.")

    return redirect('reception-classes')


@reception_required
def reception_book_for_member_view(request, session_id):
    """Permite al recepcionista reservar un cupo en una clase a nombre de un socio."""
    if request.method != 'POST':
        return HttpResponseForbidden("Método no permitido")
    member_id = request.POST.get('member_id')
    member_user = get_object_or_404(User, id=member_id, role=UserRole.MEMBER)

    try:
        booking, is_confirmed, msg = book_class_session(member_user, session_id)
        if is_confirmed:
            messages.success(request, f"Reserva confirmada para {member_user.get_full_name()}: {msg}")
        else:
            messages.warning(request, f"Cupo en lista de espera para {member_user.get_full_name()}: {msg}")
    except ValidationError as e:
        messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return redirect('reception-classes')


@reception_required
def reception_cancel_booking_view(request, booking_id):
    """Permite al recepcionista cancelar la reserva de un socio respetando las reglas de negocio."""
    if request.method != 'POST':
        return HttpResponseForbidden("Método no permitido")
    try:
        cancel_booking(booking_id, requesting_user=request.user)
        messages.success(request, "Reserva cancelada correctamente.")
    except (ValidationError, PermissionDenied) as e:
        messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return redirect('reception-classes')


# -------------------------------------------------------------
# Redirección global: cualquier URL inexistente → Inicio
# -------------------------------------------------------------

def redirect_to_home(request, *args, **kwargs):
    """Redirige cualquier ruta inexistente a la página de inicio."""
    return redirect('home')


def api_not_found(request, *args, **kwargs):
    """Retorna 404 en JSON para endpoints inexistentes bajo /api/."""
    return JsonResponse({'detail': 'No encontrado.'}, status=404)
