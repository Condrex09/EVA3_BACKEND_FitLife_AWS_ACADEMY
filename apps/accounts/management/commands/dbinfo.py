from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from apps.accounts.models import User
from apps.memberships.models import Plan, Membership, Payment
from apps.classes.models import ClassType, ClassSession, Booking
from apps.access.models import AccessLog, FacilitySetting

class Command(BaseCommand):
    help = 'Muestra información detallada de la base de datos para la defensa de la evaluación.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=" * 65))
        self.stdout.write(self.style.NOTICE("  FitLife · Información de Conexión a Base de Datos (EVA 3)"))
        self.stdout.write(self.style.NOTICE("=" * 65))

        # 1. Motor y Versión
        vendor = connection.vendor
        db_settings = connection.settings_dict
        db_name = db_settings.get('NAME', 'N/A')
        db_host = db_settings.get('HOST', 'localhost') or 'localhost'
        db_port = db_settings.get('PORT', '5432') or '5432'
        db_engine = db_settings.get('ENGINE', 'N/A')

        server_version = "N/A"
        try:
            with connection.cursor() as cursor:
                if vendor == 'postgresql':
                    cursor.execute("SHOW server_version;")
                    server_version = cursor.fetchone()[0]
                elif vendor == 'sqlite':
                    cursor.execute("SELECT sqlite_version();")
                    server_version = cursor.fetchone()[0]
        except Exception as e:
            server_version = f"Error al consultar versión: {e}"

        self.stdout.write(f"Motor ORM:            {self.style.SUCCESS(vendor.upper())} ({db_engine})")
        self.stdout.write(f"Versión del Servidor: {self.style.SUCCESS(server_version)}")
        self.stdout.write(f"Nombre de Base:       {db_name}")
        self.stdout.write(f"Host / Puerto:        {db_host}:{db_port}")

        # 2. Conteo de Migraciones Aplicadas
        try:
            recorder = MigrationRecorder(connection)
            applied_migrations_count = len(recorder.applied_migrations())
        except Exception as e:
            applied_migrations_count = f"Error: {e}"
        self.stdout.write(f"Migraciones aplicadas:{self.style.SUCCESS(str(applied_migrations_count))}")

        # 3. Conteo de Filas en Tablas Principales
        self.stdout.write("-" * 65)
        self.stdout.write(self.style.NOTICE("Conteo de Filas Persistidas en Tablas Principales:"))

        tables = [
            ("Usuarios (accounts.User)", User.objects.count()),
            ("Planes Comerciales (memberships.Plan)", Plan.objects.count()),
            ("Membresías (memberships.Membership)", Membership.objects.count()),
            ("Pagos y Transacciones (memberships.Payment)", Payment.objects.count()),
            ("Tipos de Clase (classes.ClassType)", ClassType.objects.count()),
            ("Sesiones Programadas (classes.ClassSession)", ClassSession.objects.count()),
            ("Reservas de Clases (classes.Booking)", Booking.objects.count()),
            ("Bitácora de Accesos (access.AccessLog)", AccessLog.objects.count()),
        ]

        for label, count in tables:
            self.stdout.write(f"  • {label:<45} : {self.style.SUCCESS(str(count))}")

        self.stdout.write(self.style.NOTICE("=" * 65))

