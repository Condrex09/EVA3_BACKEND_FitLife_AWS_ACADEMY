import json
from datetime import timedelta
from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

from apps.accounts.models import User, UserRole, MemberProfile
from apps.memberships.models import Plan, Membership, MembershipStatus, Payment, PaymentStatus
from apps.access.models import FacilitySetting, AccessLog, AccessDirection, AccessResult
from apps.classes.models import ClassType, ClassSession, Booking, BookingStatus, SessionStatus
from apps.classes.services import book_class_session, cancel_booking
from apps.memberships.services import unfreeze_membership, freeze_membership


class URLRedirectionTestCase(TestCase):
    """
    Verifica que las rutas inexistentes redirijan siempre al inicio ('/')
    y que la API responda con 404 JSON sin redirigir a HTML.
    """

    def test_nonexistent_web_urls_redirect_to_home(self):
        urls_to_test = ['/logn/', '/cualquier-cosa/', '/clases/xyz/abc/']
        for url in urls_to_test:
            response = self.client.get(url, follow=False)
            self.assertEqual(
                response.status_code, 302,
                f"La URL {url} debió responder con redirección 302."
            )
            self.assertEqual(response.url, '/')

    def test_admin_nonexistent_url_redirects_when_staff_logged_in(self):
        admin = User.objects.create_user(username='adm_test', email='a@t.cl', password='p', role=UserRole.ADMIN, is_staff=True)
        self.client.force_login(admin)
        response = self.client.get('/admin/no-existe/', follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')

    def test_nonexistent_api_url_returns_404_json(self):
        response = self.client.get('/api/no-existe/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers.get('Content-Type'), 'application/json')
        data = response.json()
        self.assertIn('detail', data)
        self.assertEqual(data['detail'], 'No encontrado.')


class AdminAuthenticationTestCase(TestCase):
    """
    Pruebas para verificar que el administrador demo puede iniciar sesión
    tanto con su nombre de usuario como con su correo electrónico,
    y que es redirigido a /admin/.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@fitlife.cl',
            password='Admin#FitLife2026',
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True
        )

    def test_login_with_username_redirects_to_admin(self):
        response = self.client.post(reverse('login'), {
            'username': 'admin',
            'password': 'Admin#FitLife2026',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/', response.url)

    def test_login_with_email_redirects_to_admin(self):
        response = self.client.post(reverse('login'), {
            'username': 'admin@fitlife.cl',
            'password': 'Admin#FitLife2026',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/', response.url)

    def test_login_demo_card_visibility_when_enabled(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cuenta de administrador (demo)")
        self.assertContains(response, "Autocompletar")


class APIPermissionsTestCase(APITestCase):
    """
    Pruebas estrictas de permisos REST (Tarea 1):
    - Un socio no puede crear ni modificar membresías ni pagos.
    - Un socio no puede hacer PATCH ni DELETE sobre reservas.
    - Un socio no puede consultar /api/aforo/ ni /api/access/logs/.
    - Control IDOR: un socio no puede ver datos de otro socio.
    """

    def setUp(self):
        self.plan = Plan.objects.create(
            name="Plan Test",
            slug="plan-test",
            description="Desc",
            monthly_price=25000,
            enrollment_price=0,
            duration_days=30
        )
        self.class_type = ClassType.objects.create(
            name="Funcional Test",
            slug="funcional-test",
            description="Desc",
            duration_minutes=45,
            intensity="MEDIUM"
        )
        self.session = ClassSession.objects.create(
            class_type=self.class_type,
            instructor_name="Profesor",
            room="Sala 1",
            start_datetime=timezone.now() + timedelta(days=2),
            end_datetime=timezone.now() + timedelta(days=2, minutes=45),
            capacity=10,
            status=SessionStatus.SCHEDULED
        )

        # Socio 1
        self.member1 = User.objects.create_user(username="m1", email="m1@t.cl", password="p", role=UserRole.MEMBER)
        MemberProfile.objects.create(user=self.member1, rut="11.111.111-1")
        self.mem1 = Membership.objects.create(
            member=self.member1, plan=self.plan,
            start_date=timezone.localdate(), end_date=timezone.localdate() + timedelta(days=30),
            status=MembershipStatus.ACTIVE
        )
        self.pay1 = Payment.objects.create(
            membership=self.mem1, member=self.member1, amount=25000,
            reference="PAY-M1-001", status=PaymentStatus.APPROVED
        )
        self.book1 = Booking.objects.create(
            session=self.session, member=self.member1, status=BookingStatus.CONFIRMED
        )

        # Socio 2
        self.member2 = User.objects.create_user(username="m2", email="m2@t.cl", password="p", role=UserRole.MEMBER)
        MemberProfile.objects.create(user=self.member2, rut="22.222.222-2")
        self.mem2 = Membership.objects.create(
            member=self.member2, plan=self.plan,
            start_date=timezone.localdate(), end_date=timezone.localdate() + timedelta(days=30),
            status=MembershipStatus.ACTIVE
        )

    def test_member_forbidden_create_membership(self):
        self.client.force_authenticate(user=self.member1)
        response = self.client.post('/api/memberships/', {
            'member': self.member1.id,
            'plan': self.plan.id,
            'start_date': str(timezone.localdate()),
            'end_date': str(timezone.localdate() + timedelta(days=30)),
            'status': 'ACTIVE'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_member_forbidden_edit_membership(self):
        self.client.force_authenticate(user=self.member1)
        response = self.client.patch(f'/api/memberships/{self.mem1.id}/', {'status': 'ACTIVE'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_member_forbidden_create_payment(self):
        self.client.force_authenticate(user=self.member1)
        response = self.client.post('/api/payments/', {
            'member': self.member1.id,
            'amount': 25000,
            'status': 'APPROVED'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_booking_disallows_patch_and_delete(self):
        self.client.force_authenticate(user=self.member1)
        # PATCH no está en http_method_names
        patch_resp = self.client.patch(f'/api/bookings/{self.book1.id}/', {'status': 'CONFIRMED'})
        self.assertEqual(patch_resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # DELETE no está en http_method_names
        delete_resp = self.client.delete(f'/api/bookings/{self.book1.id}/')
        self.assertEqual(delete_resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_member_forbidden_detailed_aforo_and_access_logs(self):
        self.client.force_authenticate(user=self.member1)
        # GET /api/aforo/ solo para staff/reception
        aforo_resp = self.client.get('/api/aforo/')
        self.assertEqual(aforo_resp.status_code, status.HTTP_403_FORBIDDEN)

        # GET /api/access/logs/ solo para staff/reception
        logs_resp = self.client.get('/api/access/logs/')
        self.assertEqual(logs_resp.status_code, status.HTTP_403_FORBIDDEN)

        # GET /api/aforo/resumen/ es público
        summary_resp = self.client.get('/api/aforo/resumen/')
        self.assertEqual(summary_resp.status_code, status.HTTP_200_OK)
        self.assertIn('current_count', summary_resp.data)
        self.assertNotIn('people_inside', summary_resp.data)

    def test_idor_protection_member_cannot_see_other_member_data(self):
        self.client.force_authenticate(user=self.member1)
        response = self.client.get('/api/memberships/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        member_ids = [m['member'] for m in response.data.get('results', response.data)]
        self.assertIn(self.member1.id, member_ids)
        self.assertNotIn(self.member2.id, member_ids)


class WaitlistPromotionLogicTestCase(TestCase):
    """
    Verifica que al cancelar una reserva confirmada, si el primero de la lista
    de espera tiene la membresía vencida, se lo salta y se promueve al siguiente.
    """

    def test_skip_inactive_member_on_waitlist_promotion(self):
        plan = Plan.objects.create(name="P", slug="p", description="", monthly_price=20000, duration_days=30)
        class_type = ClassType.objects.create(name="C", slug="c", description="", duration_minutes=45)
        future_start = timezone.now() + timedelta(days=2)
        session = ClassSession.objects.create(
            class_type=class_type, instructor_name="P", room="R",
            start_datetime=future_start, end_datetime=future_start + timedelta(minutes=45),
            capacity=1, status=SessionStatus.SCHEDULED
        )

        # Socio 1 (Confirmado)
        u1 = User.objects.create_user(username="u1", email="u1@t.cl", password="p", role=UserRole.MEMBER)
        MemberProfile.objects.create(user=u1, rut="11.111.111-1")
        Membership.objects.create(member=u1, plan=plan, start_date=timezone.localdate(), end_date=timezone.localdate()+timedelta(days=30), status=MembershipStatus.ACTIVE)
        b1, _, _ = book_class_session(u1, session.id)

        # Socio 2 (Lista de Espera #1 pero con MEMBRESÍA VENCIDA)
        u2 = User.objects.create_user(username="u2", email="u2@t.cl", password="p", role=UserRole.MEMBER)
        MemberProfile.objects.create(user=u2, rut="22.222.222-2")
        m2 = Membership.objects.create(member=u2, plan=plan, start_date=timezone.localdate()-timedelta(days=40), end_date=timezone.localdate()+timedelta(days=30), status=MembershipStatus.ACTIVE)
        b2, _, _ = book_class_session(u2, session.id)
        self.assertEqual(b2.status, BookingStatus.WAITLIST)
        # Vencer manualmente su membresía antes de la promoción
        m2.status = MembershipStatus.EXPIRED
        m2.end_date = timezone.localdate() - timedelta(days=1)
        m2.save()

        # Socio 3 (Lista de Espera #2 con MEMBRESÍA ACTIVA)
        u3 = User.objects.create_user(username="u3", email="u3@t.cl", password="p", role=UserRole.MEMBER)
        MemberProfile.objects.create(user=u3, rut="33.333.333-3")
        Membership.objects.create(member=u3, plan=plan, start_date=timezone.localdate(), end_date=timezone.localdate()+timedelta(days=30), status=MembershipStatus.ACTIVE)
        b3, _, _ = book_class_session(u3, session.id)
        self.assertEqual(b3.status, BookingStatus.WAITLIST)

        # Socio 1 cancela su reserva
        cancel_booking(b1.id, requesting_user=u1)

        b2.refresh_from_db()
        b3.refresh_from_db()

        # Socio 2 debió ser cancelado por tener membresía inactiva
        self.assertEqual(b2.status, BookingStatus.CANCELLED)

        # Socio 3 debió ser promovido a CONFIRMED
        self.assertEqual(b3.status, BookingStatus.CONFIRMED)
        self.assertIsNone(b3.waitlist_position)
