import uuid
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.conf import settings
from decouple import config as env_config

from apps.accounts.models import User, UserRole, MemberProfile
from apps.memberships.models import Plan, Membership, MembershipStatus, Payment, PaymentConcept, PaymentMethod, PaymentStatus
from apps.access.models import FacilitySetting, AccessLog, AccessDirection, AccessResult
from apps.classes.models import ClassType, ClassSession, Booking, BookingStatus, SessionStatus

class Command(BaseCommand):
    help = 'Poblamiento idempotente y no destructivo de datos demo para FitLife (EVA 3 Backend).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-passwords',
            action='store_true',
            help='Fuerza la actualización de contraseñas de todos los usuarios demo existentes.',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Limpia y recrea las sesiones, reservas y accesos de prueba.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Requerido para ejecutar --reset cuando DEBUG=False.',
        )

    def handle(self, *args, **options):
        reset_passwords = options.get('reset_passwords', False)
        reset_data = options.get('reset', False)
        force = options.get('force', False)

        if reset_data and not settings.DEBUG and not force:
            self.stdout.write(self.style.ERROR(
                "ADVERTENCIA DE SEGURIDAD: En entorno de producción (DEBUG=False) la opción --reset requiere explícitamente el parámetro --force. No se eliminaron datos."
            ))
            return

        self.stdout.write(self.style.NOTICE("== Iniciando poblamiento de datos demo (seed_demo) =="))

        # 1. Crear Grupos y Permisos Reales (Tarea 3.1)
        admin_group, _ = Group.objects.get_or_create(name='Administradores')
        reception_group, _ = Group.objects.get_or_create(name='Recepcionistas')
        member_group, _ = Group.objects.get_or_create(name='Socios')

        # Asignar permisos operativos al personal de Recepción
        reception_perms_codenames = [
            'view_user', 'view_memberprofile',
            'view_membership', 'change_membership',
            'view_payment', 'add_payment',
            'view_accesslog',
            'view_classsession', 'view_classtype',
            'view_booking', 'change_booking',
            'view_facilitysetting',
        ]
        reception_group.permissions.clear()
        for codename in reception_perms_codenames:
            p = Permission.objects.filter(codename=codename).first()
            if p:
                reception_group.permissions.add(p)

        # Asignar todos los permisos del dominio al grupo Administradores
        admin_group.permissions.clear()
        domain_cts = ContentType.objects.filter(
            app_label__in=['accounts', 'memberships', 'access', 'classes', 'website']
        )
        domain_perms = Permission.objects.filter(content_type__in=domain_cts)
        admin_group.permissions.set(domain_perms)
        self.stdout.write("✓ Grupos 'Administradores', 'Recepcionistas' y 'Socios' configurados con sus permisos.")

        # 2. Configuración de Sede (Singleton)
        facility = FacilitySetting.load()
        facility.facility_name = 'Sede Central FitLife Apoquindo'
        facility.max_capacity = 120
        facility.warning_threshold_pct = 60
        facility.danger_threshold_pct = 85
        facility.save()
        self.stdout.write("✓ Configuración de sede actualizada.")

        # 3. Planes comerciales
        plans_data = [
            {
                'name': 'FitLife Black',
                'slug': 'fitlife-black',
                'description': 'Acceso total y prioritario a todas las áreas, clases ilimitadas e invitaciones para amigos.',
                'monthly_price': 34990,
                'enrollment_price': 19990,
                'duration_days': 30,
                'loyalty_months': 12,
                'benefits': [
                    'Acceso a todas las sedes futuras de la cadena',
                    '5 pases de invitado al mes para amigos',
                    'Todas las clases grupales ilimitadas incluidas',
                    'Pase QR preferencial de acceso',
                    'Silla de masaje y zona de recuperación'
                ],
                'is_featured': True,
                'order': 1
            },
            {
                'name': 'FitLife Plus',
                'slug': 'fitlife-plus',
                'description': 'Ideal para quienes disfrutan de las clases dirigidas y la sala de pesas en una sola sede.',
                'monthly_price': 27990,
                'enrollment_price': 19990,
                'duration_days': 30,
                'loyalty_months': 12,
                'benefits': [
                    'Acceso ilimitado a la Sede Central',
                    'Clases grupales de Spinning, Yoga y HIIT incluidas',
                    'Pase QR digital express',
                    'Evaluación física inicial por profesor'
                ],
                'is_featured': False,
                'order': 2
            },
            {
                'name': 'FitLife Básico',
                'slug': 'fitlife-basico',
                'description': 'Para enfocarte en tu rutina de máquinas y cardio sin pagar de más ni amarras.',
                'monthly_price': 19990,
                'enrollment_price': 15000,
                'duration_days': 30,
                'loyalty_months': 0,
                'benefits': [
                    'Acceso ilimitado a sala de pesas y máquinas',
                    'Zona de cardio completa',
                    'Camarines y duchas con agua caliente',
                    'Sin contrato de permanencia'
                ],
                'is_featured': False,
                'order': 3
            }
        ]

        plans_dict = {}
        for p_info in plans_data:
            plan_obj, _ = Plan.objects.update_or_create(
                slug=p_info['slug'],
                defaults=p_info
            )
            plans_dict[p_info['slug']] = plan_obj
        self.stdout.write("✓ 3 Planes comerciales FitLife verificados/actualizados.")

        # 4. Superusuario Admin y Personal de Recepción
        admin_username = env_config('DEMO_ADMIN_USER', default='admin')
        admin_email = env_config('DEMO_ADMIN_EMAIL', default='admin@fitlife.cl')
        admin_password = env_config('DEMO_ADMIN_PASSWORD', default='Admin#FitLife2026')

        admin_user, created_admin = User.objects.get_or_create(
            username=admin_username,
            defaults={
                'email': admin_email,
                'first_name': 'Administrador',
                'last_name': 'Principal',
                'role': UserRole.ADMIN,
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            }
        )
        if created_admin or reset_passwords:
            admin_user.set_password(admin_password)
        admin_user.email = admin_email
        admin_user.role = UserRole.ADMIN
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.is_active = True
        admin_user.save()
        admin_user.groups.add(admin_group)

        reception_user, created_rec = User.objects.get_or_create(
            username='recepcion',
            defaults={
                'email': 'recepcion@fitlife.cl',
                'first_name': 'Camila',
                'last_name': 'Rojas',
                'role': UserRole.RECEPTION,
                'is_staff': True,
                'is_superuser': False,
                'is_active': True,
            }
        )
        if created_rec or reset_passwords:
            reception_user.set_password('RecepcionFitLife2026!')
        reception_user.role = UserRole.RECEPTION
        reception_user.is_staff = True
        reception_user.save()
        reception_user.groups.add(reception_group)
        self.stdout.write("✓ Usuarios 'admin' y 'recepcion' verificados.")

        # 5. 8 Socios de prueba (ACTIVE, EXPIRED, FROZEN)
        demo_members_data = [
            {
                'username': 'carlos.silva',
                'email': 'carlos.silva@demo.cl',
                'first_name': 'Carlos',
                'last_name': 'Silva',
                'rut': '11.111.111-1',
                'phone': '+56 9 8811 2233',
                'plan': 'fitlife-black',
                'status': MembershipStatus.ACTIVE,
                'days_ago': 10,
                'duration': 30
            },
            {
                'username': 'maria.gonzalez',
                'email': 'maria.gonzalez@demo.cl',
                'first_name': 'María',
                'last_name': 'González',
                'rut': '22.222.222-2',
                'phone': '+56 9 7722 3344',
                'plan': 'fitlife-plus',
                'status': MembershipStatus.EXPIRED,
                'days_ago': 45,
                'duration': 30
            },
            {
                'username': 'juan.perez',
                'email': 'juan.perez@demo.cl',
                'first_name': 'Juan',
                'last_name': 'Pérez',
                'rut': '33.333.333-3',
                'phone': '+56 9 6633 4455',
                'plan': 'fitlife-basico',
                'status': MembershipStatus.FROZEN,
                'days_ago': 5,
                'duration': 30,
                'frozen_days': 20
            },
            {
                'username': 'valentina.munoz',
                'email': 'valentina.munoz@demo.cl',
                'first_name': 'Valentina',
                'last_name': 'Muñoz',
                'rut': '15.555.555-5',
                'phone': '+56 9 5544 3322',
                'plan': 'fitlife-black',
                'status': MembershipStatus.ACTIVE,
                'days_ago': 2,
                'duration': 30
            },
            {
                'username': 'rodrigo.castro',
                'email': 'rodrigo.castro@demo.cl',
                'first_name': 'Rodrigo',
                'last_name': 'Castro',
                'rut': '16.666.666-6',
                'phone': '+56 9 4433 2211',
                'plan': 'fitlife-plus',
                'status': MembershipStatus.ACTIVE,
                'days_ago': 15,
                'duration': 30
            },
            {
                'username': 'francisca.lopez',
                'email': 'francisca.lopez@demo.cl',
                'first_name': 'Francisca',
                'last_name': 'López',
                'rut': '17.777.777-7',
                'phone': '+56 9 3322 1100',
                'plan': 'fitlife-black',
                'status': MembershipStatus.ACTIVE,
                'days_ago': 1,
                'duration': 30
            },
            {
                'username': 'matias.valenzuela',
                'email': 'matias.valenzuela@demo.cl',
                'first_name': 'Matías',
                'last_name': 'Valenzuela',
                'rut': '18.888.888-8',
                'phone': '+56 9 2211 0099',
                'plan': 'fitlife-plus',
                'status': MembershipStatus.ACTIVE,
                'days_ago': 8,
                'duration': 30
            },
            {
                'username': 'javiera.morales',
                'email': 'javiera.morales@demo.cl',
                'first_name': 'Javiera',
                'last_name': 'Morales',
                'rut': '19.999.999-9',
                'phone': '+56 9 1100 9988',
                'plan': 'fitlife-basico',
                'status': MembershipStatus.ACTIVE,
                'days_ago': 12,
                'duration': 30
            }
        ]

        created_members = []
        today = timezone.localdate()

        for m_data in demo_members_data:
            user, u_created = User.objects.get_or_create(
                username=m_data['username'],
                defaults={
                    'email': m_data['email'],
                    'first_name': m_data['first_name'],
                    'last_name': m_data['last_name'],
                    'role': UserRole.MEMBER
                }
            )
            if u_created or reset_passwords:
                user.set_password('SocioFitLife2026!')
                user.role = UserRole.MEMBER
                user.save()
            user.groups.add(member_group)

            profile, _ = MemberProfile.objects.get_or_create(
                user=user,
                defaults={
                    'rut': m_data['rut'],
                    'phone': m_data['phone']
                }
            )
            created_members.append((user, profile, m_data))

            plan = plans_dict[m_data['plan']]
            start_date = today - timedelta(days=m_data['days_ago'])
            end_date = start_date + timedelta(days=m_data['duration'])

            existing_membership = Membership.objects.filter(member=user).first()
            if not existing_membership or reset_data:
                if reset_data:
                    Membership.objects.filter(member=user).delete()

                mem = Membership.objects.create(
                    member=user,
                    plan=plan,
                    start_date=start_date,
                    end_date=end_date,
                    status=m_data['status']
                )

                if m_data['status'] == MembershipStatus.FROZEN:
                    mem.frozen_from = today - timedelta(days=2)
                    mem.frozen_until = today + timedelta(days=m_data.get('frozen_days', 15))
                    mem.save()

                Payment.objects.get_or_create(
                    reference=f"PAY-INIT-{user.id:04d}",
                    defaults={
                        'membership': mem,
                        'member': user,
                        'amount': plan.monthly_price + plan.enrollment_price,
                        'concept': PaymentConcept.ENROLLMENT,
                        'method': PaymentMethod.SIMULATED_CARD,
                        'status': PaymentStatus.APPROVED,
                    }
                )

        self.stdout.write("✓ 8 Socios de prueba verificados con membresías y pagos.")

        # 6. Crear 6 Tipos de Clase
        class_types_data = [
            {'name': 'Spinning Pro', 'slug': 'spinning', 'description': 'Pedaleo indoor de alta exigencia cardiovascular al ritmo de la mejor música.', 'duration_minutes': 50, 'intensity': 'HIGH', 'icon_or_image': 'fa-person-biking'},
            {'name': 'Yoga Vinyasa', 'slug': 'yoga', 'description': 'Secuencia fluida de posturas para mejorar flexibilidad, equilibrio y respiración.', 'duration_minutes': 60, 'intensity': 'LOW', 'icon_or_image': 'fa-spa'},
            {'name': 'Entrenamiento Funcional', 'slug': 'funcional', 'description': 'Circuitos de fuerza y resistencia con pesas rusas, balones y peso corporal.', 'duration_minutes': 45, 'intensity': 'MEDIUM', 'icon_or_image': 'fa-dumbbell'},
            {'name': 'Zumba Fitness', 'slug': 'zumba', 'description': 'Ritmos latinos y movimientos aeróbicos diseñados para quemar calorías divirtiéndote.', 'duration_minutes': 50, 'intensity': 'MEDIUM', 'icon_or_image': 'fa-music'},
            {'name': 'HIIT Quema Grasa', 'slug': 'hiit', 'description': 'Intervalos de máxima intensidad para acelerar el metabolismo post-entrenamiento.', 'duration_minutes': 40, 'intensity': 'HIGH', 'icon_or_image': 'fa-bolt'},
            {'name': 'Pilates Mat', 'slug': 'pilates', 'description': 'Fortalecimiento de la musculatura profunda del core, postura y alineación.', 'duration_minutes': 50, 'intensity': 'LOW', 'icon_or_image': 'fa-heart-pulse'},
        ]

        created_class_types = {}
        for ct_data in class_types_data:
            ct_obj, _ = ClassType.objects.update_or_create(
                slug=ct_data['slug'],
                defaults=ct_data
            )
            created_class_types[ct_data['slug']] = ct_obj
        self.stdout.write("✓ 6 Tipos de clases grupales verificados.")

        # 7. Crear Sesiones de Clases para los próximos 7 días
        if reset_data:
            ClassSession.objects.all().delete()

        now = timezone.now()
        spinning_type = created_class_types['spinning']

        # Sesión ESTRELLA de Spinning (capacidad reducida a 5 para evidenciar lista de espera)
        star_start = (now + timedelta(hours=3)).replace(minute=0, second=0, microsecond=0)
        spinning_session, spinning_created = ClassSession.objects.get_or_create(
            class_type=spinning_type,
            start_datetime=star_start,
            defaults={
                'instructor_name': 'Ignacio Valdés',
                'room': 'Sala 1 - Ciclo Indoor',
                'end_datetime': star_start + timedelta(minutes=50),
                'capacity': 5,
                'status': SessionStatus.SCHEDULED,
            }
        )

        active_users = [u for u, p, d in created_members if d['status'] == MembershipStatus.ACTIVE]

        if spinning_created or reset_data:
            # Inscribir 5 socios confirmados
            for u in active_users[:5]:
                Booking.objects.get_or_create(
                    session=spinning_session,
                    member=u,
                    defaults={
                        'status': BookingStatus.CONFIRMED,
                        'waitlist_position': None
                    }
                )

            # Inscribir 1 socio en lista de espera (Posición #1)
            if len(active_users) >= 6:
                Booking.objects.get_or_create(
                    session=spinning_session,
                    member=active_users[5],
                    defaults={
                        'status': BookingStatus.WAITLIST,
                        'waitlist_position': 1
                    }
                )

        # Crear sesiones de la semana si no existen
        instructors = ['Constanza Vera', 'Alejandro Tapia', 'Patricia Morales', 'Esteban Silva']
        days_offsets = [0, 1, 2, 3, 4, 5, 6]
        hour_slots = [(9, 0), (11, 0), (18, 0), (19, 30)]

        for day in days_offsets:
            for ct_slug, ct_obj in created_class_types.items():
                slot = hour_slots[(day + len(ct_slug)) % len(hour_slots)]
                session_start = (now + timedelta(days=day)).replace(hour=slot[0], minute=slot[1], second=0, microsecond=0)
                session_end = session_start + timedelta(minutes=ct_obj.duration_minutes)

                s, s_created = ClassSession.objects.get_or_create(
                    class_type=ct_obj,
                    start_datetime=session_start,
                    defaults={
                        'instructor_name': instructors[day % len(instructors)],
                        'room': 'Sala Principal Multiuso' if ct_slug != 'spinning' else 'Sala 1 - Ciclo Indoor',
                        'end_datetime': session_end,
                        'capacity': 20,
                        'status': SessionStatus.SCHEDULED,
                    }
                )
                if s_created and day > 0 and len(active_users) >= 2:
                    Booking.objects.get_or_create(session=s, member=active_users[0], defaults={'status': BookingStatus.CONFIRMED})
                    Booking.objects.get_or_create(session=s, member=active_users[1], defaults={'status': BookingStatus.CONFIRMED})

        self.stdout.write("✓ Sesiones de clases verificadas (incluyendo Spinning con cupo lleno y lista de espera).")

        # 8. Generar registros históricos de aforo si no existen o si reset_data
        if reset_data:
            AccessLog.objects.all().delete()

        if AccessLog.objects.count() == 0:
            today_start = timezone.now().replace(hour=7, minute=0, second=0)
            for idx, (u, p, d) in enumerate(created_members[:4]):
                entry_time = today_start + timedelta(hours=idx * 2)
                AccessLog.objects.create(
                    member=u,
                    scanned_by=reception_user,
                    direction=AccessDirection.IN,
                    result=AccessResult.ALLOWED,
                    timestamp=entry_time
                )
            self.stdout.write("✓ Registros de accesos generados para simular aforo en tiempo real.")

        self.stdout.write(self.style.SUCCESS(f"""
===================================================================
¡POBLAMIENTO DEMO COMPLETADO CON ÉXITO!
Credenciales de acceso para la defensa:

1. Administrador:
   Usuario: {admin_username} ({admin_email})
   Clave:   {admin_password}
   Rol:     ADMIN (Acceso total al Django Admin y métricas)

2. Personal de Recepción:
   Usuario: recepcion
   Clave:   RecepcionFitLife2026!
   Rol:     RECEPTION (Control de acceso QR y aforo)

3. Socios para demostración en vivo (Clave: SocioFitLife2026!):
   • carlos.silva       -> Membresía ACTIVA (FitLife Black) [Pase QR Válido]
   • maria.gonzalez     -> Membresía VENCIDA [Simula Acceso DENEGADO]
   • juan.perez         -> Membresía CONGELADA [Simula Acceso DENEGADO]
   • valentina.munoz    -> Membresía ACTIVA [Inscrita en lista de espera Spinning]
===================================================================
"""))
