from datetime import timedelta
from django.db import transaction, models
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from apps.memberships.models import Membership, MembershipStatus
from apps.memberships.services import update_membership_status
from .models import ClassSession, Booking, BookingStatus, SessionStatus

def book_class_session(member_user, session_id: int) -> tuple[Booking, bool, str]:
    """
    Realiza la reserva de una clase grupal con control estricto de concurrencia.
    Utiliza select_for_update() sobre la sesión dentro de transaction.atomic()
    para garantizar que dos personas reservando a la vez nunca superen el cupo.
    Si hay cupo -> CONFIRMED.
    Si no hay cupo -> WAITLIST con asignación de posición secuencial.
    """
    # 1. Verificar membresía activa del socio
    active_membership = (
        Membership.objects.filter(member=member_user)
        .order_by('-end_date')
        .first()
    )
    if not active_membership:
        raise ValidationError("Debes contar con una membresía para reservar clases grupales.")

    active_membership = update_membership_status(active_membership)
    if active_membership.status != MembershipStatus.ACTIVE or active_membership.end_date < timezone.localdate():
        raise ValidationError("Tu membresía se encuentra vencida o inactiva. Renueva tu plan para acceder a clases grupales.")

    # 2. Transacción concurrente
    with transaction.atomic():
        try:
            session = (
                ClassSession.objects.select_for_update()
                .select_related('class_type')
                .get(id=session_id)
            )
        except ClassSession.DoesNotExist:
            raise ValidationError("La sesión de clase solicitada no existe.")

        if session.status != SessionStatus.SCHEDULED:
            raise ValidationError("Esta sesión de clase ha sido cancelada o ya finalizó.")

        if session.start_datetime <= timezone.now():
            raise ValidationError("No es posible reservar sesiones de clases pasadas o en curso.")

        # Verificar si el socio ya tiene reserva activa
        existing = Booking.objects.filter(
            session=session,
            member=member_user,
            status__in=[BookingStatus.CONFIRMED, BookingStatus.WAITLIST, BookingStatus.ATTENDED]
        ).first()

        if existing:
            if existing.status == BookingStatus.CONFIRMED:
                raise ValidationError("Ya tienes un cupo confirmado para esta clase.")
            elif existing.status == BookingStatus.WAITLIST:
                raise ValidationError(f"Ya estás en la lista de espera de esta clase (Posición #{existing.waitlist_position}).")
            else:
                raise ValidationError("Ya figuras con asistencia registrada en esta clase.")

        # Contar cupos confirmados actualmente
        confirmed_count = Booking.objects.filter(
            session=session,
            status=BookingStatus.CONFIRMED
        ).count()

        if confirmed_count < session.capacity:
            # Hay cupo disponible -> CONFIRMADA
            booking = Booking.objects.create(
                session=session,
                member=member_user,
                status=BookingStatus.CONFIRMED,
                waitlist_position=None
            )
            return booking, True, f"¡Reserva confirmada con éxito para {session.class_type.name}!"
        else:
            # Sala llena -> Lista de espera
            max_waitlist = (
                Booking.objects.filter(session=session, status=BookingStatus.WAITLIST)
                .aggregate(models.Max('waitlist_position'))['waitlist_position__max'] or 0
            )
            next_pos = max_waitlist + 1
            booking = Booking.objects.create(
                session=session,
                member=member_user,
                status=BookingStatus.WAITLIST,
                waitlist_position=next_pos
            )
            return booking, False, f"La sala está con cupo completo. Quedaste registrado en la Lista de Espera en la posición #{next_pos}."


def cancel_booking(booking_id: int, requesting_user=None, force: bool = False) -> Booking:
    """
    Cancela una reserva garantizando la regla de las 2 horas de anticipación
    y la promoción automática en lista de espera dentro de una transacción atómica.
    """
    with transaction.atomic():
        try:
            booking = (
                Booking.objects.select_for_update()
                .select_related('session', 'session__class_type', 'member')
                .get(id=booking_id)
            )
        except Booking.DoesNotExist:
            raise ValidationError("La reserva solicitada no existe.")

        # Control de permisos (solo el propio socio o staff)
        is_staff = requesting_user and (requesting_user.is_staff or requesting_user.role in ['ADMIN', 'RECEPTION'])
        if requesting_user and not is_staff and booking.member != requesting_user:
            raise PermissionDenied("No tienes permisos para cancelar esta reserva.")

        if booking.status in [BookingStatus.CANCELLED, BookingStatus.ATTENDED, BookingStatus.NO_SHOW]:
            raise ValidationError("Esta reserva ya no puede ser cancelada en su estado actual.")

        # Regla de negocio: cancelación permitida hasta 2 horas antes de la clase
        now = timezone.now()
        deadline = booking.session.start_datetime - timedelta(hours=2)
        if not force and not is_staff and now > deadline:
            raise ValidationError("Las reservas solo pueden cancelarse hasta 2 horas antes del inicio de la sesión.")

        was_confirmed = (booking.status == BookingStatus.CONFIRMED)
        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = timezone.now()
        booking.waitlist_position = None
        booking.save()

        # Si se liberó un cupo confirmado, promover al primero de la lista de espera con membresía ACTIVA
        if was_confirmed:
            from apps.website.models import Notification
            waitlist_candidates = (
                Booking.objects.select_for_update()
                .filter(session=booking.session, status=BookingStatus.WAITLIST)
                .order_by('waitlist_position', 'created_at')
            )
            for candidate in waitlist_candidates:
                mem = Membership.objects.filter(member=candidate.member).order_by('-end_date').first()
                if mem:
                    mem = update_membership_status(mem)
                if mem and mem.status == MembershipStatus.ACTIVE and mem.end_date >= timezone.localdate():
                    # Candidato elegible: se confirma su cupo
                    candidate.status = BookingStatus.CONFIRMED
                    candidate.waitlist_position = None
                    candidate.save(update_fields=['status', 'waitlist_position'])

                    Notification.objects.create(
                        member=candidate.member,
                        title="¡Se liberó un cupo en tu clase!",
                        message=(
                            f"¡Buenas noticias! Se liberó un cupo y tu reserva para "
                            f"{booking.session.class_type.name} el "
                            f"{timezone.localtime(booking.session.start_datetime).strftime('%d/%m a las %H:%M')} "
                            f"ha sido confirmada automáticamente."
                        )
                    )
                    break
                else:
                    # Membresía no activa: se cancela y notifica, saltando al siguiente candidato
                    candidate.status = BookingStatus.CANCELLED
                    candidate.cancelled_at = timezone.now()
                    candidate.waitlist_position = None
                    candidate.save(update_fields=['status', 'cancelled_at', 'waitlist_position'])

                    Notification.objects.create(
                        member=candidate.member,
                        title="Cupo no asignado por membresía inactiva",
                        message=(
                            f"Se liberó un cupo en {booking.session.class_type.name}, pero no pudo confirmarse "
                            f"porque tu membresía no se encuentra activa. Renueva tu plan para acceder a clases grupales."
                        )
                    )

        # Reordenar las posiciones restantes de la lista de espera (1, 2, 3...)
        remaining_waitlist = (
            Booking.objects.select_for_update()
            .filter(session=booking.session, status=BookingStatus.WAITLIST)
            .order_by('waitlist_position', 'created_at')
        )
        for index, b in enumerate(remaining_waitlist, start=1):
            if b.waitlist_position != index:
                b.waitlist_position = index
                b.save(update_fields=['waitlist_position'])

        return booking


def admin_cancel_session(session_id: int, staff_user=None, reason: str = "") -> ClassSession:
    """
    Cancela una sesión completa por parte del Administrador o Recepción,
    cancelando automáticamente todas sus reservas y notificando a los socios afectados.
    """
    with transaction.atomic():
        session = (
            ClassSession.objects.select_for_update()
            .select_related('class_type')
            .get(id=session_id)
        )
        session.status = SessionStatus.CANCELLED
        session.save()

        active_bookings = Booking.objects.filter(
            session=session,
            status__in=[BookingStatus.CONFIRMED, BookingStatus.WAITLIST]
        )

        from apps.website.models import Notification
        for b in active_bookings:
            b.status = BookingStatus.CANCELLED
            b.cancelled_at = timezone.now()
            b.save(update_fields=['status', 'cancelled_at'])

            msg_reason = f" Motivo: {reason}" if reason else ""
            Notification.objects.create(
                member=b.member,
                title="Sesión de clase cancelada",
                message=(
                    f"Lamentamos informarte que la sesión de {session.class_type.name} programada para el "
                    f"{timezone.localtime(session.start_datetime).strftime('%d/%m a las %H:%M')} fue cancelada por la administración.{msg_reason}"
                )
            )

        return session

