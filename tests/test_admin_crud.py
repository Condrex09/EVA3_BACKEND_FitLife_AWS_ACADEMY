from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth.models import Group, Permission

from apps.accounts.models import User, UserRole, MemberProfile
from apps.memberships.models import Plan, Membership, MembershipStatus, Payment, PaymentStatus
from apps.access.models import FacilitySetting, AccessLog, AccessDirection, AccessResult
from apps.classes.models import ClassType, ClassSession, Booking, BookingStatus, SessionStatus
from apps.website.models import ContactMessage, Notification


class AdminCRUDPermissionsTestCase(TestCase):
    """
    Verifica que las pantallas de lista, agregar, modificar y eliminar de los
    12 modelos del sistema respondan 200 para el Superusuario / Administrador,
    salvo restricciones de negocio justificadas (FacilitySetting singleton y
    AccessLog inmutable para trazabilidad), y que el rol Recepción reciba 403
    en los modelos y acciones no autorizados.
    """

    def setUp(self):
        # 1. Superusuario administrador
        self.superuser = User.objects.create_superuser(
            username='admin_test',
            email='admin@test.fitlife.cl',
            password='TestAdminPassword123!',
            role=UserRole.ADMIN
        )

        # 2. Usuario de Recepción con grupo y permisos específicos
        self.reception_user = User.objects.create_user(
            username='recep_test',
            email='recep@test.fitlife.cl',
            password='TestRecepPassword123!',
            role=UserRole.RECEPTION,
            is_staff=True
        )
        reception_group, _ = Group.objects.get_or_create(name='Recepcionistas_Test')
        reception_perms = [
            'view_user', 'view_memberprofile',
            'view_membership', 'change_membership',
            'view_payment', 'add_payment',
            'view_accesslog',
            'view_classsession', 'view_classtype',
            'view_booking', 'change_booking',
            'view_facilitysetting',
        ]
        for codename in reception_perms:
            p = Permission.objects.filter(codename=codename).first()
            if p:
                reception_group.permissions.add(p)
        self.reception_user.groups.add(reception_group)

        # 3. Socio normal
        self.member_user = User.objects.create_user(
            username='socio_test',
            email='socio@test.fitlife.cl',
            password='Password123!',
            role=UserRole.MEMBER
        )
        self.profile = MemberProfile.objects.create(
            user=self.member_user,
            rut='12.345.678-9',
            phone='+56912345678'
        )

        # 4. Modelos de dominio creados para probar URLs de change y delete
        self.plan = Plan.objects.create(
            name='Plan Oro Test',
            slug='plan-oro-test',
            monthly_price=35000,
            enrollment_price=10000,
            duration_days=30
        )
        today = timezone.localdate()
        self.membership = Membership.objects.create(
            member=self.member_user,
            plan=self.plan,
            start_date=today,
            end_date=today + timedelta(days=30),
            status=MembershipStatus.ACTIVE
        )
        self.payment = Payment.objects.create(
            member=self.member_user,
            amount=35000,
            concept='MEMBERSHIP',
            method='WEBPAY',
            status=PaymentStatus.APPROVED
        )
        self.facility = FacilitySetting.load()

        self.access_log = AccessLog.objects.create(
            member=self.member_user,
            direction=AccessDirection.IN,
            result=AccessResult.ALLOWED
        )
        self.class_type = ClassType.objects.create(
            name='CrossFit Test',
            slug='crossfit-test',
            duration_minutes=60,
            intensity='HIGH'
        )
        self.session = ClassSession.objects.create(
            class_type=self.class_type,
            instructor_name='Profesor Test',
            room='Sala A',
            start_datetime=timezone.now() + timedelta(days=1),
            capacity=20,
            status=SessionStatus.SCHEDULED
        )
        self.booking = Booking.objects.create(
            session=self.session,
            member=self.member_user,
            status=BookingStatus.CONFIRMED
        )
        self.contact = ContactMessage.objects.create(
            name='Juan Perez',
            email='juan@correo.cl',
            subject='Consulta horarios',
            message='Hola, quisiera saber los horarios.'
        )
        self.notification = Notification.objects.create(
            member=self.member_user,
            title='Recordatorio de clase',
            message='Tienes una clase agendada para mañana.'
        )

    def test_admin_dashboard_renders_with_brand_and_metrics(self):
        """Verifica que el dashboard principal de administración responda 200 con branding y métricas."""
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Socios Activos')
        self.assertContains(response, 'Ingresos de Hoy')
        self.assertContains(response, 'Aforo Actual de la Sede')
        self.assertContains(response, 'Reservas de Clases Hoy')
        self.assertContains(response, 'Desarrollado por Benjamin Gomez')

    def test_superuser_crud_views_respond_200(self):
        """
        Verifica que el superusuario acceda a lista, agregar, modificar y eliminar
        para los 12 modelos (con las excepciones justificadas de negocio).
        """
        self.client.force_login(self.superuser)

        # Matriz de los 12 modelos: (app_label, model_name, instance, can_add, can_delete)
        models_config = [
            ('accounts', 'user', self.superuser, True, True),
            ('accounts', 'memberprofile', self.profile, True, True),
            ('memberships', 'plan', self.plan, True, True),
            ('memberships', 'membership', self.membership, True, True),
            ('memberships', 'payment', self.payment, True, True),
            ('access', 'accesslog', self.access_log, True, False), # Delete desactivado por trazabilidad
            ('access', 'facilitysetting', self.facility, False, False), # Singleton: no add múltiple, no delete
            ('classes', 'classtype', self.class_type, True, True),
            ('classes', 'classsession', self.session, True, True),
            ('classes', 'booking', self.booking, True, True),
            ('website', 'contactmessage', self.contact, True, True),
            ('website', 'notification', self.notification, True, True),
        ]

        for app_label, model_name, instance, can_add, can_delete in models_config:
            # 1. Changelist (Lista) -> Siempre 200
            cl_url = reverse(f'admin:{app_label}_{model_name}_changelist')
            r_cl = self.client.get(cl_url)
            self.assertEqual(r_cl.status_code, 200, f"Error en changelist de {app_label}.{model_name}")

            # 2. Change (Modificar) -> Siempre 200
            ch_url = reverse(f'admin:{app_label}_{model_name}_change', args=[instance.pk])
            r_ch = self.client.get(ch_url)
            self.assertEqual(r_ch.status_code, 200, f"Error en change de {app_label}.{model_name}")

            # 3. Add (Agregar) -> 200 si permitido, 403 si singleton
            add_url = reverse(f'admin:{app_label}_{model_name}_add')
            r_add = self.client.get(add_url)
            if can_add:
                self.assertEqual(r_add.status_code, 200, f"Error en add de {app_label}.{model_name}")
            else:
                self.assertEqual(r_add.status_code, 403, f"Add de {app_label}.{model_name} debió ser 403 por singleton")

            # 4. Delete (Eliminar) -> 200 si permitido, 403 si desactivado
            del_url = reverse(f'admin:{app_label}_{model_name}_delete', args=[instance.pk])
            r_del = self.client.get(del_url)
            if can_delete:
                self.assertEqual(r_del.status_code, 200, f"Error en delete de {app_label}.{model_name}")
            else:
                self.assertEqual(r_del.status_code, 403, f"Delete de {app_label}.{model_name} debió ser 403 por trazabilidad")

    def test_reception_role_restricted_from_unauthorized_models(self):
        """
        Verifica que el rol Recepción no pueda acceder a modelos protegidos
        (Plan comercial, Mensajes de contacto, Notificaciones) ni eliminar registros.
        """
        self.client.force_login(self.reception_user)

        # 1. Modelos no autorizados para recepción: debe recibir 403
        unauthorized_urls = [
            reverse('admin:memberships_plan_changelist'),
            reverse('admin:memberships_plan_add'),
            reverse('admin:website_contactmessage_changelist'),
            reverse('admin:website_notification_changelist'),
            reverse('admin:memberships_membership_delete', args=[self.membership.pk]),
        ]
        for url in unauthorized_urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 403, f"Recepción no debió acceder a {url}")

        # 2. Modelos autorizados para recepción: debe recibir 200
        authorized_urls = [
            reverse('admin:memberships_membership_changelist'),
            reverse('admin:memberships_payment_changelist'),
            reverse('admin:access_accesslog_changelist'),
            reverse('admin:classes_classsession_changelist'),
            reverse('admin:classes_booking_changelist'),
        ]
        for url in authorized_urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, f"Recepción debió acceder a {url}")

