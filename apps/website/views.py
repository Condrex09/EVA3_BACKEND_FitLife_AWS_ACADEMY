from datetime import timedelta
from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import HttpResponseForbidden, JsonResponse

from apps.accounts.models import User, MemberProfile, UserRole
from apps.accounts.validators import clean_rut
from apps.memberships.models import Plan, Membership, Payment, MembershipStatus
from apps.memberships.services import process_subscription_payment, renew_membership, update_membership_status
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
        return redirect('reception-access')
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

    profile = getattr(user, 'profile', None)
    qr_base64 = profile.generate_qr_base64() if profile else ""

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

def staff_required(view_func):
    """Decorador para proteger vistas operativas de recepción y aforo."""
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not (request.user.is_staff or request.user.role in [UserRole.ADMIN, UserRole.RECEPTION]):
            messages.error(request, "Acceso restringido: requiere permisos de personal de recepción.")
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

@staff_required
def reception_access_view(request):
    """
    Interfaz de recepción para validación de acceso por QR.
    Incluye cámara web en vivo (html5-qrcode) + simulador manual por token.
    Muestra tarjeta grande de resultado y bitácora de los últimos 10 accesos.
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

@staff_required
def dashboard_aforo_view(request):
    """
    Dashboard de aforo en tiempo real con tarjeta principal, barra de porcentaje,
    lista de socios dentro y gráfico de ingresos por hora del día con Chart.js.
    """
    data = get_facility_occupancy_data()
    return render(request, 'website/dashboard_aforo.html', {
        'aforo_data': data,
    })

@staff_required
def reception_members_view(request):
    """Buscador y ficha de socios para el personal de recepción."""
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
                models.Q(profile__rut__icontains=clean_q or query)
            )
            .select_related('profile')
            .prefetch_related('memberships')[:20]
        )
    return render(request, 'website/reception_members.html', {
        'query': query,
        'members': members,
    })

@staff_required
def reception_member_detail_view(request, user_id):
    """Ficha completa de un socio para recepción con acciones de congelar/descongelar y registro de pagos."""
    member_user = get_object_or_404(User, id=user_id, role=UserRole.MEMBER)
    profile = getattr(member_user, 'profile', None)
    memberships = Membership.objects.filter(member=member_user).order_by('-created_at')
    payments = Payment.objects.filter(member=member_user).order_by('-paid_at')[:10]
    recent_logs = AccessLog.objects.filter(member=member_user).order_by('-timestamp')[:10]
    active_plans = Plan.objects.filter(is_active=True).order_by('order', 'monthly_price')

    return render(request, 'website/reception_member_detail.html', {
        'member_user': member_user,
        'profile': profile,
        'memberships': memberships,
        'payments': payments,
        'recent_logs': recent_logs,
        'active_plans': active_plans,
    })

@staff_required
def reception_freeze_membership_view(request, membership_id):
    """Acción operativa para congelar una membresía activa desde recepción."""
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
        from apps.memberships.services import freeze_membership
        freeze_membership(membership, frozen_until)
        messages.success(request, f"Membresía congelada exitosamente hasta el {frozen_until.strftime('%d/%m/%Y')}.")
    except (ValueError, ValidationError) as e:
        messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return redirect('reception-member-detail', user_id=membership.member_id)

@staff_required
def reception_unfreeze_membership_view(request, membership_id):
    """Acción operativa para descongelar una membresía desde recepción."""
    if request.method != 'POST':
        return HttpResponseForbidden("Método no permitido")
    membership = get_object_or_404(Membership, id=membership_id)
    try:
        from apps.memberships.services import unfreeze_membership
        unfreeze_membership(membership)
        messages.success(request, f"Membresía descongelada correctamente. Nueva fecha de término: {membership.end_date.strftime('%d/%m/%Y')}.")
    except ValidationError as e:
        messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return redirect('reception-member-detail', user_id=membership.member_id)

@staff_required
def reception_manual_payment_view(request, user_id):
    """Registra un pago manual en efectivo o transferencia y activa/renueva la membresía."""
    if request.method != 'POST':
        return HttpResponseForbidden("Método no permitido")
    member_user = get_object_or_404(User, id=user_id, role=UserRole.MEMBER)
    plan_id = request.POST.get('plan_id')
    amount_str = request.POST.get('amount')
    concept = request.POST.get('concept', 'MONTHLY')
    method = request.POST.get('method', 'CASH')

    plan = get_object_or_404(Plan, id=plan_id)
    try:
        amount = int(amount_str) if amount_str else plan.monthly_price
    except ValueError:
        amount = plan.monthly_price

    from django.db import transaction
    with transaction.atomic():
        today = timezone.localdate()
        # Expirar membresías activas o congeladas previas
        Membership.objects.filter(
            member=member_user,
            status__in=[MembershipStatus.ACTIVE, MembershipStatus.FROZEN]
        ).update(status=MembershipStatus.EXPIRED)

        new_membership = Membership.objects.create(
            member=member_user,
            plan=plan,
            start_date=today,
            end_date=today + timedelta(days=plan.duration_days),
            status=MembershipStatus.ACTIVE
        )

        Payment.objects.create(
            membership=new_membership,
            member=member_user,
            amount=amount,
            concept=concept,
            method=method,
            status=PaymentStatus.APPROVED,
            reference=Payment.generate_reference("MAN")
        )

    messages.success(request, f"Pago manual de ${amount:,} CLP registrado ({method}). Membresía {plan.name} activada con éxito.")
    return redirect('reception-member-detail', user_id=member_user.id)


# -------------------------------------------------------------
# Redirección global: cualquier URL inexistente → Inicio
# -------------------------------------------------------------

def redirect_to_home(request, *args, **kwargs):
    """Redirige cualquier ruta inexistente a la página de inicio."""
    return redirect('home')


def api_not_found(request, *args, **kwargs):
    """Retorna 404 en JSON para endpoints inexistentes bajo /api/."""
    return JsonResponse({'detail': 'No encontrado.'}, status=404)
