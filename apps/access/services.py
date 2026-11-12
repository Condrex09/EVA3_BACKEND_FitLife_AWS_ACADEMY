import uuid
from django.db import models
from django.utils import timezone
from apps.accounts.models import MemberProfile
from apps.memberships.models import Membership, MembershipStatus
from apps.memberships.services import update_membership_status
from .models import AccessLog, AccessDirection, AccessResult, DenyReason, FacilitySetting

def get_current_occupancy_logs():
    """
    Obtiene los registros de los socios que actualmente se encuentran dentro de la sede.
    Un socio está dentro si su último registro ALLOWED tiene dirección 'IN'.
    Utiliza una subconsulta de Max(id) por socio, altamente optimizada para PostgreSQL.
    """
    latest_log_ids = (
        AccessLog.objects.filter(result=AccessResult.ALLOWED, member__isnull=False)
        .values('member_id')
        .annotate(latest_id=models.Max('id'))
        .values('latest_id')
    )
    return (
        AccessLog.objects.filter(id__in=latest_log_ids, direction=AccessDirection.IN)
        .select_related('member', 'member__profile')
        .order_by('-timestamp')
    )

def get_facility_occupancy_count() -> int:
    """Retorna la cantidad exacta de socios que se encuentran actualmente dentro."""
    return get_current_occupancy_logs().count()

def get_facility_occupancy_data() -> dict:
    """
    Calcula las métricas completas de aforo en tiempo real para el dashboard:
    - Personas dentro, capacidad máxima, porcentaje de ocupación, color semáforo.
    - Distribución horaria de ingresos del día de hoy para renderizar en Chart.js.
    - Últimos 10 accesos registrados.
    """
    settings = FacilitySetting.load()
    current_count = get_facility_occupancy_count()
    max_cap = settings.max_capacity or 120
    percentage = round((current_count / max_cap) * 100, 1) if max_cap > 0 else 0

    # Determinación del color semáforo
    if percentage >= settings.danger_threshold_pct:
        status_color = 'red'
        status_text = 'Crítico / Sobrecupo'
    elif percentage >= settings.warning_threshold_pct:
        status_color = 'yellow'
        status_text = 'Advertencia / Alta Demanda'
    else:
        status_color = 'green'
        status_text = 'Normal / Aforo Óptimo'

    today = timezone.localdate()
    today_start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
    
    # Distribución por hora (de 06:00 a 23:00)
    hourly_counts = {f"{h:02d}:00": 0 for h in range(6, 24)}
    today_in_logs = AccessLog.objects.filter(
        direction=AccessDirection.IN,
        result=AccessResult.ALLOWED,
        timestamp__gte=today_start
    )
    for log in today_in_logs:
        h = timezone.localtime(log.timestamp).hour
        hour_key = f"{h:02d}:00"
        if hour_key in hourly_counts:
            hourly_counts[hour_key] += 1

    # Últimos 10 registros
    recent_logs = []
    for log in AccessLog.objects.select_related('member').order_by('-timestamp')[:10]:
        recent_logs.append({
            'id': log.id,
            'member_name': log.member.get_full_name() if log.member else "Desconocido",
            'direction': log.get_direction_display(),
            'result': log.result,
            'result_display': log.get_result_display(),
            'deny_reason': log.get_deny_reason_display() if log.deny_reason else None,
            'time': timezone.localtime(log.timestamp).strftime('%H:%M:%S'),
        })

    # Lista de socios actualmente adentro
    people_inside = []
    for log in get_current_occupancy_logs()[:25]:
        profile = getattr(log.member, 'profile', None)
        people_inside.append({
            'name': log.member.get_full_name() or log.member.username,
            'rut': profile.formatted_rut if profile else "-",
            'entry_time': timezone.localtime(log.timestamp).strftime('%H:%M:%S'),
        })

    return {
        'facility_name': settings.facility_name,
        'current_count': current_count,
        'max_capacity': max_cap,
        'percentage': percentage,
        'status_color': status_color,
        'status_text': status_text,
        'hourly_labels': list(hourly_counts.keys()),
        'hourly_data': list(hourly_counts.values()),
        'recent_logs': recent_logs,
        'people_inside': people_inside,
    }

def validate_and_record_access(qr_token_str: str, scanned_by=None) -> dict:
    """
    Valida un pase QR en milisegundos con una sola consulta optimizada.
    Aplica todas las reglas de negocio:
    1. Existencia del QR.
    2. Estado de membresía (Activa / Vencida / Congelada).
    3. Alternancia automática Entrada / Salida (Toggle IN/OUT).
    4. Control de límite de aforo si la dirección es IN.
    Registra el resultado en AccessLog y retorna el resultado estructurado.
    """
    # 1. Validar formato UUID
    try:
        token_uuid = uuid.UUID(str(qr_token_str).strip())
    except (ValueError, AttributeError):
        log = AccessLog.objects.create(
            scanned_by=scanned_by,
            direction=AccessDirection.IN,
            result=AccessResult.DENIED,
            deny_reason=DenyReason.INVALID_QR
        )
        return {
            'allowed': False,
            'status': 'DENIED',
            'reason': 'INVALID_QR',
            'message': 'Código QR con formato inválido o no reconocido.',
            'timestamp': timezone.localtime(log.timestamp).strftime('%H:%M:%S')
        }

    # 2. Consulta optimizada del socio
    profile = (
        MemberProfile.objects.select_related('user')
        .filter(qr_token=token_uuid)
        .first()
    )

    if not profile or not profile.user:
        log = AccessLog.objects.create(
            scanned_by=scanned_by,
            direction=AccessDirection.IN,
            result=AccessResult.DENIED,
            deny_reason=DenyReason.INVALID_QR
        )
        return {
            'allowed': False,
            'status': 'DENIED',
            'reason': 'INVALID_QR',
            'message': 'El código QR no corresponde a ningún socio registrado.',
            'timestamp': timezone.localtime(log.timestamp).strftime('%H:%M:%S')
        }

    user = profile.user
    full_name = user.get_full_name() or user.username

    # 3. Validar membresía
    membership = (
        Membership.objects.select_related('plan')
        .filter(member=user)
        .order_by('-end_date')
        .first()
    )

    if not membership:
        log = AccessLog.objects.create(
            member=user,
            scanned_by=scanned_by,
            direction=AccessDirection.IN,
            result=AccessResult.DENIED,
            deny_reason=DenyReason.NO_MEMBERSHIP
        )
        return {
            'allowed': False,
            'status': 'DENIED',
            'reason': 'NO_MEMBERSHIP',
            'member_name': full_name,
            'rut': profile.formatted_rut,
            'message': 'El socio no registra ninguna membresía en el sistema.',
            'timestamp': timezone.localtime(log.timestamp).strftime('%H:%M:%S')
        }

    # Actualizar estado según fecha actual
    membership = update_membership_status(membership)

    if membership.status == MembershipStatus.EXPIRED:
        log = AccessLog.objects.create(
            member=user,
            scanned_by=scanned_by,
            direction=AccessDirection.IN,
            result=AccessResult.DENIED,
            deny_reason=DenyReason.EXPIRED
        )
        return {
            'allowed': False,
            'status': 'DENIED',
            'reason': 'EXPIRED',
            'member_name': full_name,
            'rut': profile.formatted_rut,
            'plan_name': membership.plan.name,
            'end_date': membership.end_date.strftime('%d/%m/%Y'),
            'message': f'Membresía vencida el {membership.end_date.strftime("%d/%m/%Y")}. Debe renovar para ingresar.',
            'timestamp': timezone.localtime(log.timestamp).strftime('%H:%M:%S')
        }

    if membership.status == MembershipStatus.FROZEN:
        log = AccessLog.objects.create(
            member=user,
            scanned_by=scanned_by,
            direction=AccessDirection.IN,
            result=AccessResult.DENIED,
            deny_reason=DenyReason.FROZEN
        )
        until_str = membership.frozen_until.strftime('%d/%m/%Y') if membership.frozen_until else "indefinido"
        return {
            'allowed': False,
            'status': 'DENIED',
            'reason': 'FROZEN',
            'member_name': full_name,
            'rut': profile.formatted_rut,
            'plan_name': membership.plan.name,
            'message': f'Membresía congelada hasta el {until_str}. Acceso temporalmente suspendido.',
            'timestamp': timezone.localtime(log.timestamp).strftime('%H:%M:%S')
        }

    # 4. Determinar dirección (Toggle Entrada / Salida)
    last_allowed_log = (
        AccessLog.objects.filter(member=user, result=AccessResult.ALLOWED)
        .order_by('-timestamp')
        .first()
    )

    if last_allowed_log and last_allowed_log.direction == AccessDirection.IN:
        next_direction = AccessDirection.OUT
        direction_label = "Salida"
    else:
        next_direction = AccessDirection.IN
        direction_label = "Entrada"

    # 5. Si es ingreso, verificar aforo máximo
    if next_direction == AccessDirection.IN:
        settings = FacilitySetting.load()
        current_inside = get_facility_occupancy_count()
        if current_inside >= settings.max_capacity:
            log = AccessLog.objects.create(
                member=user,
                scanned_by=scanned_by,
                direction=AccessDirection.IN,
                result=AccessResult.DENIED,
                deny_reason=DenyReason.CAPACITY_FULL
            )
            return {
                'allowed': False,
                'status': 'DENIED',
                'reason': 'CAPACITY_FULL',
                'member_name': full_name,
                'rut': profile.formatted_rut,
                'plan_name': membership.plan.name,
                'message': f'Aforo completo ({current_inside}/{settings.max_capacity}). Por favor espere que salga un usuario.',
                'timestamp': timezone.localtime(log.timestamp).strftime('%H:%M:%S')
            }

    # 6. Registrar acceso permitido
    log = AccessLog.objects.create(
        member=user,
        scanned_by=scanned_by,
        direction=next_direction,
        result=AccessResult.ALLOWED
    )

    today = timezone.localdate()
    days_left = (membership.end_date - today).days if membership.end_date else 0
    return {
        'allowed': True,
        'status': 'ALLOWED',
        'direction': next_direction,
        'direction_display': direction_label,
        'member_name': full_name,
        'rut': profile.formatted_rut,
        'plan_name': membership.plan.name,
        'end_date': membership.end_date.strftime('%d/%m/%Y'),
        'days_remaining': days_left,
        'expiring_soon': (0 <= days_left <= 7),
        'message': f'¡Acceso Permitido! Se registró {direction_label} correctamente.',
        'timestamp': timezone.localtime(log.timestamp).strftime('%H:%M:%S')
    }

