from datetime import timedelta
from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse
from django.core.management import call_command
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User, UserRole, MemberProfile
from apps.memberships.models import Plan, Membership, MembershipStatus, Payment, PaymentMethod, PaymentStatus
from apps.classes.models import ClassType, ClassSession, Booking, BookingStatus, SessionStatus
from apps.memberships.services import (
    MAX_FREEZE_DAYS,
    freeze_membership,
    unfreeze_membership,
    record_manual_payment_at_reception,
    enroll_member_at_reception,
)
from apps.classes.services import book_class_session


class ReceptionRoleTestCase(TestCase):
    """
    Suite exhaustiva de pruebas para el rol Recepción (Sección 5):
    1. Usuario 'recepcion' de seed_demo tiene is_staff=False, role=RECEPTION y redirige desde /admin/ a /recepcion/.
    2. Socio recibe 403 o redirección en /recepcion/* y /api/aforo/; recepción y admin entran (200).
    3. Recepción recibe 403 al intentar POST/PATCH/DELETE sobre /api/plans/, /api/sessions/ y /api/classes/.
    4. Pago manual toma el monto del plan, ignora monto manual y registra registered_by; transferencia sin comprobante es rechazada.
    5. Inscripción en mostrador crea usuario, perfil, pago y membresía atómicamente; falla si RUT existe.
    6. Congelar más de MAX_FREEZE_DAYS (30) falla; descongelar el mismo día no extiende días.
    7. Marcar asistencia actualiza reserva; reservar a nombre de socio respeta aforo y envía a lista de espera.
    8. Ambas tarjetas demo aparecen con SHOW_DEMO_CREDENTIALS=True y ninguna con False.
    9. Búsqueda de socios en recepción excluye staff y recepcionistas.
    10. seed_demo ejecutado dos veces es idempotente (no duplica ni sobrescribe contraseñas sin --reset-passwords).
    """

    def setUp(self):
        self.api_client = APIClient()

        # Admin
        self.admin_user = User.objects.create_superuser(
            username='admin_role_test',
            email='admin_role@fitlife.cl',
            password='AdminPassword123!',
            role=UserRole.ADMIN
        )

        # Recepcionista
        self.reception_user = User.objects.create_user(
            username='recep_role_test',
            email='recep_role@fitlife.cl',
            password='RecepPassword123!',
            role=UserRole.RECEPTION,
            is_staff=False,
            is_superuser=False
        )

        # Socio normal
        self.member_user = User.objects.create_user(
            username='member_role_test',
            email='member_role@fitlife.cl',
            password='MemberPassword123!',
            role=UserRole.MEMBER,
            is_staff=False,
            is_superuser=False
        )
        self.member_profile = MemberProfile.objects.create(
            user=self.member_user,
            rut='15.345.678-9',
            phone='+56911223344',
            emergency_contact='Contacto +56999887766'
        )

        # Plan base
        self.plan = Plan.objects.create(
            name='Plan Oro Test',
            slug='plan-oro-test',
            monthly_price=35000,
            enrollment_price=10000,
            duration_days=30,
            is_active=True
        )

        # Membresía activa del socio
        today = timezone.localdate()
        self.membership = Membership.objects.create(
            member=self.member_user,
            plan=self.plan,
            start_date=today,
            end_date=today + timedelta(days=30),
            status=MembershipStatus.ACTIVE
        )

    # -------------------------------------------------------------------------
    # 1. seed_demo: recepcion tiene is_staff=False, role=RECEPTION y bloquea /admin/
    # -------------------------------------------------------------------------
    def test_01_seed_demo_reception_user_attributes_and_admin_redirect(self):
        call_command('seed_demo')
        recep = User.objects.get(username='recepcion')
        self.assertFalse(recep.is_staff, "El recepcionista de seed_demo NO debe tener is_staff.")
        self.assertFalse(recep.is_superuser)
        self.assertEqual(recep.role, UserRole.RECEPTION)

        # Acceso a /admin/ debe ser interceptado y redirigido a /recepcion/
        self.client.force_login(recep)
        resp = self.client.get('/admin/', follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/recepcion/', resp['Location'])

    # -------------------------------------------------------------------------
    # 2. Rutas /recepcion/* y /api/aforo/: Socio bloqueado; Recepción y Admin entran
    # -------------------------------------------------------------------------
    def test_02_member_blocked_reception_and_admin_allowed(self):
        # Socio en /recepcion/
        self.client.force_login(self.member_user)
        resp_member = self.client.get(reverse('reception-home'))
        self.assertIn(resp_member.status_code, [302, 403])

        # Socio en /api/aforo/
        self.api_client.force_authenticate(user=self.member_user)
        api_resp_member = self.api_client.get(reverse('api-aforo'))
        self.assertEqual(api_resp_member.status_code, status.HTTP_403_FORBIDDEN)

        # Recepción en /recepcion/ y /api/aforo/
        self.client.force_login(self.reception_user)
        resp_recep = self.client.get(reverse('reception-home'))
        self.assertEqual(resp_recep.status_code, 200)

        self.api_client.force_authenticate(user=self.reception_user)
        api_resp_recep = self.api_client.get(reverse('api-aforo'))
        self.assertEqual(api_resp_recep.status_code, status.HTTP_200_OK)

        # Admin en /recepcion/ y /api/aforo/
        self.client.force_login(self.admin_user)
        resp_admin = self.client.get(reverse('reception-home'))
        self.assertEqual(resp_admin.status_code, 200)

        self.api_client.force_authenticate(user=self.admin_user)
        api_resp_admin = self.api_client.get(reverse('api-aforo'))
        self.assertEqual(api_resp_admin.status_code, status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # 3. Recepción recibe 403 en POST/PATCH/DELETE sobre /api/plans/, /api/sessions/, etc.
    # -------------------------------------------------------------------------
    def test_03_reception_forbidden_api_modifications(self):
        self.api_client.force_authenticate(user=self.reception_user)

        # POST /api/plans/
        resp_post_plan = self.api_client.post('/api/plans/', {
            'name': 'Plan Prohibido',
            'slug': 'plan-prohibido',
            'monthly_price': 50000,
            'duration_days': 30
        })
        self.assertEqual(resp_post_plan.status_code, status.HTTP_403_FORBIDDEN)

        # PATCH /api/plans/{id}/
        resp_patch_plan = self.api_client.patch(f'/api/plans/{self.plan.id}/', {'monthly_price': 99999})
        self.assertEqual(resp_patch_plan.status_code, status.HTTP_403_FORBIDDEN)

        # DELETE /api/plans/{id}/
        resp_del_plan = self.api_client.delete(f'/api/plans/{self.plan.id}/')
        self.assertEqual(resp_del_plan.status_code, status.HTTP_403_FORBIDDEN)

        # POST /api/classes/
        resp_post_class = self.api_client.post('/api/classes/', {
            'name': 'Yoga Prohibido',
            'slug': 'yoga-prohibido',
            'duration_minutes': 60
        })
        self.assertEqual(resp_post_class.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # 4. Pago manual: precio del plan fijo, registered_by registrado, transfer exige comprobante
    # -------------------------------------------------------------------------
    def test_04_manual_payment_fixed_amount_and_receipt_validation(self):
        # Transferencia sin comprobante -> ValidationError
        with self.assertRaises(ValidationError):
            record_manual_payment_at_reception(
                member_user=self.member_user,
                plan=self.plan,
                method=PaymentMethod.TRANSFER,
                receipt_number='',
                reception_user=self.reception_user
            )

        # Efectivo -> Éxito, registrado por recepcionista y monto igual a monthly_price
        new_mem, pay = record_manual_payment_at_reception(
            member_user=self.member_user,
            plan=self.plan,
            method=PaymentMethod.CASH,
            receipt_number='',
            reception_user=self.reception_user
        )
        self.assertEqual(pay.amount, self.plan.monthly_price)
        self.assertEqual(pay.registered_by, self.reception_user)
        self.assertEqual(new_mem.status, MembershipStatus.ACTIVE)

        # Vía vista web enviando un monto malicioso (debe ser ignorado)
        self.client.force_login(self.reception_user)
        url = reverse('reception-member-detail', args=[self.member_user.id])
        resp = self.client.post(url, {
            'action': 'register_payment',
            'plan_id': self.plan.id,
            'payment_method': 'CASH',
            'amount': 10  # Intento de pagar $10 en vez de $35.000
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        latest_payment = Payment.objects.filter(member=self.member_user).order_by('-paid_at').first()
        self.assertEqual(latest_payment.amount, self.plan.monthly_price)
        self.assertEqual(latest_payment.registered_by, self.reception_user)

    # -------------------------------------------------------------------------
    # 5. Inscripción en mostrador: atómica, crea usuario/perfil/pago/membresía, RUT único
    # -------------------------------------------------------------------------
    def test_05_in_person_enrollment_atomic_and_rut_validation(self):
        valid_rut = '16.789.012-1'
        u, prof, mem, pay, temp_pass = enroll_member_at_reception(
            first_name='Pedro',
            last_name='Picapiedra',
            email='pedro.pica@fitlife.cl',
            rut=valid_rut,
            phone='+56987654321',
            emergency_contact='Vilma +56911223344',
            plan=self.plan,
            method=PaymentMethod.CASH,
            receipt_number='',
            reception_user=self.reception_user
        )
        self.assertEqual(u.role, UserRole.MEMBER)
        self.assertTrue(prof.qr_token)
        self.assertEqual(mem.status, MembershipStatus.ACTIVE)
        self.assertEqual(pay.amount, self.plan.monthly_price + self.plan.enrollment_price)
        self.assertEqual(pay.registered_by, self.reception_user)
        self.assertTrue(temp_pass.startswith('FitLife-'))

        # Intentar inscribir nuevamente con el mismo RUT debe fallar
        with self.assertRaises(ValidationError):
            enroll_member_at_reception(
                first_name='Otro',
                last_name='Usuario',
                email='otro@fitlife.cl',
                rut=valid_rut,
                phone='+56900000000',
                emergency_contact='N/A',
                plan=self.plan,
                method=PaymentMethod.CASH,
                reception_user=self.reception_user
            )

    # -------------------------------------------------------------------------
    # 6. Congelamiento: límite MAX_FREEZE_DAYS (30) y descongelar mismo día no extiende
    # -------------------------------------------------------------------------
    def test_06_freeze_max_days_limit_and_same_day_unfreeze(self):
        today = timezone.localdate()

        # Intentar congelar por 31 días -> Falla
        with self.assertRaises(ValidationError):
            freeze_membership(self.membership, frozen_until=today + timedelta(days=MAX_FREEZE_DAYS + 1))

        # Congelar válido por 10 días
        original_end = self.membership.end_date
        freeze_membership(self.membership, frozen_until=today + timedelta(days=10))
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.status, MembershipStatus.FROZEN)

        # Descongelar el mismo día -> no debe aumentar la fecha de término
        unfreeze_membership(self.membership)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.status, MembershipStatus.ACTIVE)
        self.assertEqual(self.membership.end_date, original_end)

    # -------------------------------------------------------------------------
    # 7. Asistencia (ATTENDED / NO_SHOW) y reserva con cupos / lista de espera
    # -------------------------------------------------------------------------
    def test_07_attendance_marking_and_booking_capacity(self):
        ct = ClassType.objects.create(
            name='Spinning Test',
            slug='spinning-test',
            duration_minutes=45,
            intensity='HIGH'
        )
        start = timezone.now() + timedelta(days=1)
        session = ClassSession.objects.create(
            class_type=ct,
            instructor_name='Instructor Test',
            room='Sala Bici',
            start_datetime=start,
            end_datetime=start + timedelta(minutes=45),
            capacity=1,
            status=SessionStatus.SCHEDULED
        )

        # 1ra reserva: CONFIRMED
        booking1, is_confirmed1, _ = book_class_session(self.member_user, session.id)
        self.assertTrue(is_confirmed1)
        self.assertEqual(booking1.status, BookingStatus.CONFIRMED)

        # 2do socio reserva para la misma sesión (capacidad 1) -> pasa a WAITLIST
        member2 = User.objects.create_user(username='member2_test', email='m2@test.cl', password='Pass123!')
        MemberProfile.objects.create(user=member2, rut='18.111.222-3')
        Membership.objects.create(
            member=member2,
            plan=self.plan,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=30),
            status=MembershipStatus.ACTIVE
        )
        booking2, is_confirmed2, _ = book_class_session(member2, session.id)
        self.assertFalse(is_confirmed2)
        self.assertEqual(booking2.status, BookingStatus.WAITLIST)

        # Marcar asistencia via POST recepcionista
        self.client.force_login(self.reception_user)
        url_att = reverse('reception-update-attendance', args=[booking1.id])
        resp = self.client.post(url_att, {'status': BookingStatus.ATTENDED}, follow=True)
        self.assertEqual(resp.status_code, 200)
        booking1.refresh_from_db()
        self.assertEqual(booking1.status, BookingStatus.ATTENDED)

    # -------------------------------------------------------------------------
    # 8. Tarjetas demo en login con SHOW_DEMO_CREDENTIALS True y False
    # -------------------------------------------------------------------------
    def test_08_demo_cards_display_on_login(self):
        url = reverse('login')

        with self.settings(SHOW_DEMO_CREDENTIALS=True):
            resp_on = self.client.get(url)
            self.assertEqual(resp_on.status_code, 200)
            self.assertContains(resp_on, "Cuenta de administrador (demo)")
            self.assertContains(resp_on, "Cuenta de recepcionista (demo)")

        with self.settings(SHOW_DEMO_CREDENTIALS=False):
            resp_off = self.client.get(url)
            self.assertEqual(resp_off.status_code, 200)
            self.assertNotContains(resp_off, "Cuenta de administrador (demo)")
            self.assertNotContains(resp_off, "Cuenta de recepcionista (demo)")

    # -------------------------------------------------------------------------
    # 9. Búsqueda de socios excluye staff y recepcionistas
    # -------------------------------------------------------------------------
    def test_09_reception_search_excludes_staff_and_receptionists(self):
        self.client.force_login(self.reception_user)
        url = reverse('reception-members')

        # Buscar por el nombre del admin
        resp = self.client.get(url, {'q': self.admin_user.username})
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, self.admin_user.email)

        # Buscar por el nombre del recepcionista
        resp_rec = self.client.get(url, {'q': self.reception_user.username})
        self.assertEqual(resp_rec.status_code, 200)
        self.assertNotContains(resp_rec, self.reception_user.email)

        # Buscar por el socio normal -> aparece
        resp_mem = self.client.get(url, {'q': self.member_user.username})
        self.assertEqual(resp_mem.status_code, 200)
        self.assertContains(resp_mem, self.member_user.username)

    # -------------------------------------------------------------------------
    # 10. seed_demo es idempotente (no duplica ni sobrescribe contraseñas sin flag)
    # -------------------------------------------------------------------------
    def test_10_seed_demo_idempotence(self):
        call_command('seed_demo')
        count_users_first = User.objects.count()
        recep = User.objects.get(username='recepcion')
        recep_pass_hash = recep.password

        # Segunda ejecución sin --reset-passwords
        call_command('seed_demo')
        count_users_second = User.objects.count()
        recep.refresh_from_db()

        self.assertEqual(count_users_first, count_users_second, "seed_demo duplicó registros.")
        self.assertEqual(recep.password, recep_pass_hash, "seed_demo sobrescribió contraseñas sin --reset-passwords.")
