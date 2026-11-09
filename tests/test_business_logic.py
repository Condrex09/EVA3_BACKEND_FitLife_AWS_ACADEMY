import uuid
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied

from apps.accounts.models import User, UserRole, MemberProfile
from apps.memberships.models import Plan, Membership, MembershipStatus, Payment, PaymentStatus
from apps.access.models import FacilitySetting, AccessLog, AccessDirection, AccessResult, DenyReason
from apps.access.services import validate_and_record_access, get_facility_occupancy_count
from apps.classes.models import ClassType, ClassSession, Booking, BookingStatus, SessionStatus
from apps.classes.services import book_class_session, cancel_booking
from apps.website.models import Notification

class FitLifeBusinessLogicTestCase(TestCase):
    """
    Suite de pruebas unitarias para validar las reglas de negocio críticas
    requeridas por la rúbrica de la Evaluación 3 de Backend (INACAP).
    """

    def setUp(self):
        # Configuración de Sede
        self.facility = FacilitySetting.load()
        self.facility.max_capacity = 2  # Capacidad baja para probar aforo lleno
        self.facility.save()

        # Plan base
        self.plan = Plan.objects.create(
            name="Plan Test",
            slug="plan-test",
            description="Plan para pruebas",
            monthly_price=25000,
            enrollment_price=0,
            duration_days=30
        )

        # Disciplina de clase
        self.class_type = ClassType.objects.create(
            name="Spinning Test",
            slug="spinning-test",
            description="Clase para test",
            duration_minutes=50,
            intensity="HIGH"
        )

        # Usuarios de prueba
        self.receptionist = User.objects.create_user(
            username="recepcion_test",
            email="rec@test.cl",
            password="pass",
            role=UserRole.RECEPTION,
            is_staff=True
        )

        # Socio 1 (Activo)
        self.member1 = User.objects.create_user(
            username="socio1",
            email="s1@test.cl",
            password="pass",
            role=UserRole.MEMBER
        )
        self.profile1 = MemberProfile.objects.create(
            user=self.member1,
            rut="11.111.111-1"
        )
        self.mem1 = Membership.objects.create(
            member=self.member1,
            plan=self.plan,
            start_date=timezone.localdate() - timedelta(days=5),
            end_date=timezone.localdate() + timedelta(days=25),
            status=MembershipStatus.ACTIVE
        )

        # Socio 2 (Vencido)
        self.member2 = User.objects.create_user(
            username="socio2",
            email="s2@test.cl",
            password="pass",
            role=UserRole.MEMBER
        )
        self.profile2 = MemberProfile.objects.create(
            user=self.member2,
            rut="22.222.222-2"
        )
        self.mem2 = Membership.objects.create(
            member=self.member2,
            plan=self.plan,
            start_date=timezone.localdate() - timedelta(days=40),
            end_date=timezone.localdate() - timedelta(days=10),
            status=MembershipStatus.EXPIRED
        )

        # Socio 3 (Congelado)
        self.member3 = User.objects.create_user(
            username="socio3",
            email="s3@test.cl",
            password="pass",
            role=UserRole.MEMBER
        )
        self.profile3 = MemberProfile.objects.create(
            user=self.member3,
            rut="33.333.333-3"
        )
        self.mem3 = Membership.objects.create(
            member=self.member3,
            plan=self.plan,
            start_date=timezone.localdate() - timedelta(days=5),
            end_date=timezone.localdate() + timedelta(days=25),
            status=MembershipStatus.FROZEN,
            frozen_from=timezone.localdate() - timedelta(days=2),
            frozen_until=timezone.localdate() + timedelta(days=15)
        )

    # -------------------------------------------------------------------------
    # 1. Pruebas de Control de Acceso por QR y Estados de Membresía
    # -------------------------------------------------------------------------

    def test_access_denied_with_expired_membership(self):
        """Verifica que un socio con membresía vencida tenga acceso DENEGADO."""
        result = validate_and_record_access(str(self.profile2.qr_token), scanned_by=self.receptionist)
        self.assertFalse(result['allowed'])
        self.assertEqual(result['status'], 'DENIED')
        self.assertEqual(result['reason'], 'EXPIRED')

        log = AccessLog.objects.filter(member=self.member2).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.result, AccessResult.DENIED)
        self.assertEqual(log.deny_reason, DenyReason.EXPIRED)

    def test_access_denied_with_frozen_membership(self):
        """Verifica que un socio con membresía congelada tenga acceso DENEGADO."""
        result = validate_and_record_access(str(self.profile3.qr_token), scanned_by=self.receptionist)
        self.assertFalse(result['allowed'])
        self.assertEqual(result['reason'], 'FROZEN')

    def test_access_allowed_and_toggle_in_out(self):
        """Verifica que el escaneo alterne automáticamente entre Entrada (IN) y Salida (OUT)."""
        # Primer escaneo -> IN (Entrada)
        res1 = validate_and_record_access(str(self.profile1.qr_token), scanned_by=self.receptionist)
        self.assertTrue(res1['allowed'])
        self.assertEqual(res1['direction'], AccessDirection.IN)

        # Segundo escaneo -> OUT (Salida)
        res2 = validate_and_record_access(str(self.profile1.qr_token), scanned_by=self.receptionist)
        self.assertTrue(res2['allowed'])
        self.assertEqual(res2['direction'], AccessDirection.OUT)

    def test_access_denied_when_facility_capacity_full(self):
        """Verifica que al alcanzar el aforo máximo, se bloquee el ingreso con CAPACITY_FULL."""
        # Creamos un socio extra activo
        extra_user = User.objects.create_user(username="extra_user", email="extra@test.cl", password="p", role=UserRole.MEMBER)
        extra_profile = MemberProfile.objects.create(user=extra_user, rut="44.444.444-4")
        Membership.objects.create(member=extra_user, plan=self.plan, start_date=timezone.localdate(), end_date=timezone.localdate()+timedelta(days=30), status=MembershipStatus.ACTIVE)

        # max_capacity está seteado en 2 en setUp
        # Ingresan socio1 y extra_user
        res_u1 = validate_and_record_access(str(self.profile1.qr_token), scanned_by=self.receptionist)
        self.assertTrue(res_u1['allowed'])
        res_u2 = validate_and_record_access(str(extra_profile.qr_token), scanned_by=self.receptionist)
        self.assertTrue(res_u2['allowed'])

        self.assertEqual(get_facility_occupancy_count(), 2)

        # Ahora un tercer socio activo intenta ingresar
        user3 = User.objects.create_user(username="user3", email="u3@test.cl", password="p", role=UserRole.MEMBER)
        profile3_extra = MemberProfile.objects.create(user=user3, rut="55.555.555-5")
        Membership.objects.create(member=user3, plan=self.plan, start_date=timezone.localdate(), end_date=timezone.localdate()+timedelta(days=30), status=MembershipStatus.ACTIVE)

        res_u3 = validate_and_record_access(str(profile3_extra.qr_token), scanned_by=self.receptionist)
        self.assertFalse(res_u3['allowed'])
        self.assertEqual(res_u3['reason'], 'CAPACITY_FULL')

    # -------------------------------------------------------------------------
    # 2. Pruebas de Reserva de Clases, Cupos y Lista de Espera Concurrente
    # -------------------------------------------------------------------------

    def test_booking_quota_and_waitlist_order(self):
        """Verifica la asignación de cupos confirmados y lista de espera secuencial."""
        future_start = timezone.now() + timedelta(days=2)
        session = ClassSession.objects.create(
            class_type=self.class_type,
            instructor_name="Instructor Test",
            room="Sala 1",
            start_datetime=future_start,
            end_datetime=future_start + timedelta(minutes=50),
            capacity=1,  # Capacidad de solo 1 cupo
            status=SessionStatus.SCHEDULED
        )

        # Socio 1 reserva -> Cupo CONFIRMED
        booking1, is_confirmed, _ = book_class_session(self.member1, session.id)
        self.assertTrue(is_confirmed)
        self.assertEqual(booking1.status, BookingStatus.CONFIRMED)
        self.assertIsNone(booking1.waitlist_position)

        # Creamos otro socio activo para reservar
        other_user = User.objects.create_user(username="other", email="other@test.cl", password="p", role=UserRole.MEMBER)
        MemberProfile.objects.create(user=other_user, rut="66.666.666-6")
        Membership.objects.create(member=other_user, plan=self.plan, start_date=timezone.localdate(), end_date=timezone.localdate()+timedelta(days=30), status=MembershipStatus.ACTIVE)

        # other_user reserva en sesión llena -> WAITLIST posición #1
        booking2, is_confirmed_2, _ = book_class_session(other_user, session.id)
        self.assertFalse(is_confirmed_2)
        self.assertEqual(booking2.status, BookingStatus.WAITLIST)
        self.assertEqual(booking2.waitlist_position, 1)

    def test_automatic_promotion_on_cancellation(self):
        """Verifica que al cancelar una reserva confirmada, se promueva automáticamente al primero de la lista de espera."""
        future_start = timezone.now() + timedelta(days=2)
        session = ClassSession.objects.create(
            class_type=self.class_type,
            instructor_name="Instructor Test",
            room="Sala 1",
            start_datetime=future_start,
            end_datetime=future_start + timedelta(minutes=50),
            capacity=1,
            status=SessionStatus.SCHEDULED
        )

        # Usuario A (Confirmado)
        booking_a, _, _ = book_class_session(self.member1, session.id)

        # Usuario B (Lista de Espera)
        user_b = User.objects.create_user(username="user_b", email="ub@test.cl", password="p", role=UserRole.MEMBER)
        MemberProfile.objects.create(user=user_b, rut="77.777.777-7")
        Membership.objects.create(member=user_b, plan=self.plan, start_date=timezone.localdate(), end_date=timezone.localdate()+timedelta(days=30), status=MembershipStatus.ACTIVE)
        booking_b, _, _ = book_class_session(user_b, session.id)
        self.assertEqual(booking_b.status, BookingStatus.WAITLIST)

        # Usuario A cancela su reserva
        cancel_booking(booking_a.id, requesting_user=self.member1)

        # Verificar que A quedó CANCELLED
        booking_a.refresh_from_db()
        self.assertEqual(booking_a.status, BookingStatus.CANCELLED)

        # Verificar que B fue promovido a CONFIRMED
        booking_b.refresh_from_db()
        self.assertEqual(booking_b.status, BookingStatus.CONFIRMED)
        self.assertIsNone(booking_b.waitlist_position)

        # Verificar notificación creada para Usuario B
        notif = Notification.objects.filter(member=user_b).first()
        self.assertIsNotNone(notif)
        self.assertIn("liberó un cupo", notif.title)

    def test_cancellation_deadline_within_two_hours(self):
        """Verifica que no se permita la cancelación con menos de 2 horas de anticipación."""
        soon_start = timezone.now() + timedelta(hours=1)  # En 1 hora (menos de 2 horas)
        session = ClassSession.objects.create(
            class_type=self.class_type,
            instructor_name="Instructor",
            room="Sala 1",
            start_datetime=soon_start,
            end_datetime=soon_start + timedelta(minutes=50),
            capacity=10,
            status=SessionStatus.SCHEDULED
        )

        booking, _, _ = book_class_session(self.member1, session.id)

        with self.assertRaises(ValidationError) as ctx:
            cancel_booking(booking.id, requesting_user=self.member1)
        self.assertIn("2 horas", str(ctx.exception))

