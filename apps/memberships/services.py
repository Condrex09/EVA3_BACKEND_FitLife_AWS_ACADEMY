from datetime import timedelta, date
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Membership, MembershipStatus, Payment, PaymentConcept, PaymentMethod, PaymentStatus, Plan

def update_membership_status(membership: Membership) -> Membership:
    """
    Reevalúa el estado de una membresía en función de la fecha actual.
    Si end_date < hoy y el estado no es FROZEN, pasa a EXPIRED.
    """
    today = timezone.localdate()
    if membership.status == MembershipStatus.ACTIVE and membership.end_date < today:
        membership.status = MembershipStatus.EXPIRED
        membership.save(update_fields=['status'])
    elif membership.status == MembershipStatus.FROZEN and membership.frozen_until and membership.frozen_until < today:
        # Si el plazo de congelación terminó, se descongela automáticamente
        unfreeze_membership(membership)
    return membership

def update_all_memberships() -> int:
    """
    Comando por lotes para expirar membresías activas cuya fecha ya pasó.
    Es idempotente y retorna el número de registros actualizados.
    """
    today = timezone.localdate()
    count = 0
    expired_memberships = Membership.objects.filter(
        status=MembershipStatus.ACTIVE,
        end_date__lt=today
    )
    for m in expired_memberships:
        m.status = MembershipStatus.EXPIRED
        m.save(update_fields=['status'])
        count += 1
    return count

def freeze_membership(membership: Membership, frozen_until: date) -> Membership:
    """
    Congela una membresía activa hasta una fecha futura determinada.
    Mientras esté congelada, no permite el acceso a la sede ni reservar clases.
    """
    today = timezone.localdate()
    if membership.status != MembershipStatus.ACTIVE:
        raise ValidationError("Solo se pueden congelar membresías con estado ACTIVA.")
    if frozen_until <= today:
        raise ValidationError("La fecha de congelamiento debe ser posterior a la fecha de hoy.")
    
    membership.status = MembershipStatus.FROZEN
    membership.frozen_from = today
    membership.frozen_until = frozen_until
    membership.save()
    return membership

def unfreeze_membership(membership: Membership) -> Membership:
    """
    Descongela una membresía, extendiendo la fecha de término (end_date)
    por la cantidad exacta de días en los que estuvo congelada.
    """
    if membership.status != MembershipStatus.FROZEN:
        raise ValidationError("La membresía no se encuentra congelada.")
    
    today = timezone.localdate()
    frozen_from = membership.frozen_from or today
    days_frozen = max(0, (today - frozen_from).days)

    if days_frozen > 0:
        membership.end_date = membership.end_date + timedelta(days=days_frozen)
    membership.status = MembershipStatus.ACTIVE
    membership.frozen_from = None
    membership.frozen_until = None
    membership.save()
    return membership

def process_subscription_payment(
    member_user,
    plan: Plan,
    card_number: str,
    card_expiry: str,
    card_cvv: str,
    concept: str = PaymentConcept.ENROLLMENT,
    method: str = PaymentMethod.SIMULATED_CARD
) -> tuple[Payment, Membership | None, bool, str]:
    """
    Flujo de pago simulado dentro de una transacción atómica.
    Regla de prueba:
    - Tarjeta terminada en '0000' simula fondos insuficientes / tarjeta rechazada.
    - Demás tarjetas válidas aprueban la transacción y activan la membresía.
    """
    clean_card = "".join(filter(str.isdigit, str(card_number or "")))
    amount = plan.monthly_price
    if concept == PaymentConcept.ENROLLMENT and plan.enrollment_price > 0:
        amount += plan.enrollment_price

    # Validación de simulación
    if clean_card.endswith('0000') or len(clean_card) < 13:
        # Pago rechazado
        payment = Payment.objects.create(
            member=member_user,
            amount=amount,
            concept=concept,
            method=method,
            status=PaymentStatus.REJECTED,
            reference=Payment.generate_reference("REJ")
        )
        return payment, None, False, "Pago rechazado por la entidad bancaria emisora (Simulación: tarjeta terminada en 0000 o inválida)."

    with transaction.atomic():
        today = timezone.localdate()
        # Expirar membresías activas o congeladas previas si existieran
        existing_active = Membership.objects.filter(
            member=member_user,
            status__in=[MembershipStatus.ACTIVE, MembershipStatus.FROZEN]
        )
        for m in existing_active:
            m.status = MembershipStatus.EXPIRED
            m.save()

        # Crear nueva membresía
        start_date = today
        end_date = today + timedelta(days=plan.duration_days)
        membership = Membership.objects.create(
            member=member_user,
            plan=plan,
            start_date=start_date,
            end_date=end_date,
            status=MembershipStatus.ACTIVE
        )

        payment = Payment.objects.create(
            membership=membership,
            member=member_user,
            amount=amount,
            concept=concept,
            method=method,
            status=PaymentStatus.APPROVED,
            reference=Payment.generate_reference("PAY")
        )

        return payment, membership, True, "¡Suscripción y pago aprobados exitosamente! Tu membresía está activa."

def renew_membership(
    member_user,
    plan: Plan = None,
    method: str = PaymentMethod.SIMULATED_CARD,
    card_number: str = "4500000000001234"
) -> tuple[Payment, Membership, bool, str]:
    """
    Renueva la membresía de un socio. Si ya tiene una vigente, la extiende.
    Si está vencida, inicia desde hoy.
    """
    with transaction.atomic():
        latest = Membership.objects.filter(member=member_user).order_by('-end_date').first()
        target_plan = plan or (latest.plan if latest else None)
        if not target_plan:
            raise ValidationError("No se especificó un plan para renovar.")

        clean_card = "".join(filter(str.isdigit, str(card_number or "")))
        if clean_card.endswith('0000'):
            payment = Payment.objects.create(
                member=member_user,
                amount=target_plan.monthly_price,
                concept=PaymentConcept.RENEWAL,
                method=method,
                status=PaymentStatus.REJECTED,
                reference=Payment.generate_reference("REJ")
            )
            return payment, latest, False, "El pago de renovación fue rechazado."

        today = timezone.localdate()
        if latest and latest.status == MembershipStatus.ACTIVE and latest.end_date >= today:
            new_start = latest.end_date + timedelta(days=1)
            new_end = new_start + timedelta(days=target_plan.duration_days)
            latest.end_date = new_end
            latest.plan = target_plan
            latest.save()
            membership = latest
        else:
            # Expirar membresías activas o congeladas previas antes de crear una nueva
            Membership.objects.filter(
                member=member_user,
                status__in=[MembershipStatus.ACTIVE, MembershipStatus.FROZEN]
            ).update(status=MembershipStatus.EXPIRED)

            new_start = today
            new_end = today + timedelta(days=target_plan.duration_days)
            membership = Membership.objects.create(
                member=member_user,
                plan=target_plan,
                start_date=new_start,
                end_date=new_end,
                status=MembershipStatus.ACTIVE
            )

        payment = Payment.objects.create(
            membership=membership,
            member=member_user,
            amount=target_plan.monthly_price,
            concept=PaymentConcept.RENEWAL,
            method=method,
            status=PaymentStatus.APPROVED,
            reference=Payment.generate_reference("REN")
        )

        return payment, membership, True, f"Membresía renovada exitosamente hasta el {membership.end_date.strftime('%d/%m/%Y')}."

