from django import template
from django.db.models import Sum
from django.utils import timezone
from apps.memberships.models import Membership, MembershipStatus, Payment, PaymentStatus
from apps.classes.models import Booking, BookingStatus
from apps.access.services import get_facility_occupancy_count
from apps.access.models import FacilitySetting

register = template.Library()

@register.simple_tag
def get_admin_metrics():
    """
    Calcula métricas clave en vivo para desplegar en el portal de inicio del Django Admin.
    """
    today = timezone.localdate()
    
    # 1. Socios activos
    active_members_count = Membership.objects.filter(
        status=MembershipStatus.ACTIVE,
        end_date__gte=today
    ).count()

    # 2. Ingresos recaudados hoy (CLP)
    today_income = Payment.objects.filter(
        status=PaymentStatus.APPROVED,
        paid_at__date=today
    ).aggregate(total=Sum('amount'))['total'] or 0

    # 3. Aforo actual y capacidad
    facility = FacilitySetting.load()
    current_occupancy = get_facility_occupancy_count()

    # 4. Reservas de clases de hoy
    today_bookings_count = Booking.objects.filter(
        session__start_datetime__date=today,
        status=BookingStatus.CONFIRMED
    ).count()

    return {
        'active_members': active_members_count,
        'today_income': today_income,
        'current_occupancy': current_occupancy,
        'max_capacity': facility.max_capacity,
        'today_bookings': today_bookings_count,
    }

