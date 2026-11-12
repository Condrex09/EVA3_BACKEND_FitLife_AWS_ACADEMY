import secrets
from datetime import timedelta, date
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Membership, MembershipStatus, Payment, PaymentConcept, PaymentMethod, PaymentStatus, Plan
from apps.accounts.models import User, UserRole, MemberProfile
from apps.accounts.validators import validate_rut, clean_rut

MAX_FREEZE_DAYS = 30

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
    Congela una membresía activa hasta una fecha futura determinada (máximo 30 días).
    Mientras esté congelada, no permite el acceso a la sede ni reservar clases.
    """
    today = timezone.localdate()
    if membership.status != MembershipStatus.ACTIVE:
        raise ValidationError("Solo se pueden congelar membresías con estado ACTIVA.")
    if frozen_until <= today:
        raise ValidationError("La fecha de congelamiento debe ser posterior a la fecha de hoy.")
    
    freeze_days = (frozen_until - today).days
    if freeze_days > MAX_FREEZE_DAYS:
        raise ValidationError(f"El congelamiento no puede exceder el límite máximo de {MAX_FREEZE_DAYS} días (solicitado: {freeze_days} días).")
    
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
    total_amount = plan.monthly_price
    if concept == PaymentConcept.ENROLLMENT:
        total_amount += plan.enrollment_price

    with transaction.atomic():
        if clean_card.endswith('0000'):
            payment = Payment.objects.create(
                member=member_user,
                amount=total_amount,
                concept=concept,
                method=method,
                status=PaymentStatus.REJECTED,
                reference=Payment.generate_reference("REJ")
            )
            return payment, None, False, "El pago fue rechazado por el emisor (fondos insuficientes simulados)."

        today = timezone.localdate()
        # Expirar membresías activas o congeladas previas antes de crear la nueva
        Membership.objects.filter(
            member=member_user,
            status__in=[MembershipStatus.ACTIVE, MembershipStatus.FROZEN]
        ).update(status=MembershipStatus.EXPIRED)

        membership = Membership.objects.create(
            member=member_user,
            plan=plan,
            start_date=today,
            end_date=today + timedelta(days=plan.duration_days),
            status=MembershipStatus.ACTIVE
        )

        payment = Payment.objects.create(
            membership=membership,
            member=member_user,
            amount=total_amount,
            concept=concept,
            method=method,
            status=PaymentStatus.APPROVED,
            reference=Payment.generate_reference("OK")
        )

        return payment, membership, True, f"Pago de ${total_amount:,} CLP aprobado. Membresía {plan.name} activada hasta el {membership.end_date.strftime('%d/%m/%Y')}."

def renew_membership(
    member_user,
    plan: Plan = None,
    card_number: str = "1111",
    method: str = PaymentMethod.SIMULATED_CARD
) -> tuple[Payment, Membership, bool, str]:
    """
    Renueva una membresía. Si la última sigue activa, extiende su fecha fin.
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

def record_manual_payment_at_reception(
    member_user: User,
    plan: Plan,
    method: str,
    receipt_number: str = "",
    reception_user: User = None
) -> tuple[Membership, Payment]:
    """
    Registra un pago manual en mostrador de recepción (efectivo o transferencia).
    El monto es estricta e inmutablemente el precio del plan elegido (de solo lectura).
    Si el método es transferencia, exige obligatoriamente número de comprobante.
    Asocia registered_by al recepcionista actuante para auditoría.
    """
    clean_method = method.upper()
    if clean_method not in [PaymentMethod.CASH, PaymentMethod.TRANSFER]:
        clean_method = PaymentMethod.CASH

    if clean_method == PaymentMethod.TRANSFER and not (receipt_number and receipt_number.strip()):
        raise ValidationError("Las transferencias bancarias requieren obligatoriamente el número de comprobante.")

    with transaction.atomic():
        today = timezone.localdate()
        # Expirar membresías activas o congeladas anteriores
        Membership.objects.filter(
            member=member_user,
            status__in=[MembershipStatus.ACTIVE, MembershipStatus.FROZEN]
        ).update(status=MembershipStatus.EXPIRED, frozen_from=None, frozen_until=None)

        new_membership = Membership.objects.create(
            member=member_user,
            plan=plan,
            start_date=today,
            end_date=today + timedelta(days=plan.duration_days),
            status=MembershipStatus.ACTIVE
        )

        ref_prefix = "REC-TRF" if clean_method == PaymentMethod.TRANSFER else "REC-CSH"
        reference = Payment.generate_reference(ref_prefix)
        if receipt_number and receipt_number.strip():
            reference = f"{reference}-{receipt_number.strip()[:15]}"

        payment = Payment.objects.create(
            membership=new_membership,
            member=member_user,
            amount=plan.monthly_price,  # El monto siempre se toma del plan
            concept=PaymentConcept.RENEWAL,
            method=clean_method,
            status=PaymentStatus.APPROVED,
            reference=reference,
            registered_by=reception_user
        )

        return new_membership, payment

def enroll_member_at_reception(
    first_name: str,
    last_name: str,
    email: str,
    rut: str,
    phone: str,
    emergency_contact: str,
    plan: Plan,
    method: str,
    receipt_number: str = "",
    reception_user: User = None
) -> tuple[User, MemberProfile, Membership, Payment, str]:
    """
    Inscribe a un socio nuevo en mostrador en una única transacción atómica:
    - Valida RUT y unicidad de correo y RUT.
    - Genera contraseña temporal segura (se retorna para mostrarse una sola vez).
    - Crea User (rol MEMBER), MemberProfile (con token QR generado).
    - Crea Membership ACTIVA por los días del plan.
    - Crea Payment por monto = matrícula + primera mensualidad con registered_by.
    """
    # 1. Validaciones previas
    clean_email = email.strip().lower()
    if not clean_email or '@' not in clean_email:
        raise ValidationError("Debe proporcionar una dirección de correo electrónico válida.")

    if User.objects.filter(email__iexact=clean_email).exists():
        raise ValidationError("Ya existe un usuario registrado con este correo electrónico.")

    cleaned_rut = clean_rut(rut)
    validate_rut(cleaned_rut)

    if MemberProfile.objects.filter(rut=cleaned_rut).exists():
        raise ValidationError("Ya existe un socio registrado con este RUT en el sistema.")

    clean_method = method.upper() if method else PaymentMethod.CASH
    if clean_method not in [PaymentMethod.CASH, PaymentMethod.TRANSFER]:
        clean_method = PaymentMethod.CASH

    if clean_method == PaymentMethod.TRANSFER and not (receipt_number and receipt_number.strip()):
        raise ValidationError("Las transferencias bancarias requieren obligatoriamente el número de comprobante.")

    # 2. Generar nombre de usuario único y contraseña temporal
    base_username = clean_email.split('@')[0].replace('.', '').replace('-', '')[:15]
    if not base_username:
        base_username = "socio"
    username = base_username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username[:12]}{counter}"
        counter += 1

    temp_password = f"FitLife-{secrets.token_hex(3).upper()}"

    # 3. Transacción atómica integral
    with transaction.atomic():
        user = User.objects.create_user(
            username=username,
            email=clean_email,
            password=temp_password,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            role=UserRole.MEMBER,
            is_active=True
        )

        profile = MemberProfile.objects.create(
            user=user,
            rut=cleaned_rut,
            phone=phone.strip(),
            emergency_contact=emergency_contact.strip()
        )

        today = timezone.localdate()
        membership = Membership.objects.create(
            member=user,
            plan=plan,
            start_date=today,
            end_date=today + timedelta(days=plan.duration_days),
            status=MembershipStatus.ACTIVE
        )

        total_amount = plan.monthly_price + plan.enrollment_price
        ref_prefix = "ENR-TRF" if clean_method == PaymentMethod.TRANSFER else "ENR-CSH"
        reference = Payment.generate_reference(ref_prefix)
        if receipt_number and receipt_number.strip():
            reference = f"{reference}-{receipt_number.strip()[:15]}"

        payment = Payment.objects.create(
            membership=membership,
            member=user,
            amount=total_amount,
            concept=PaymentConcept.ENROLLMENT,
            method=clean_method,
            status=PaymentStatus.APPROVED,
            reference=reference,
            registered_by=reception_user
        )

        return user, profile, membership, payment, temp_password
