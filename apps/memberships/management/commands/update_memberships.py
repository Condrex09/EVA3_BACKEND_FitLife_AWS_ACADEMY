from django.core.management.base import BaseCommand
from apps.memberships.services import update_all_memberships

class Command(BaseCommand):
    help = 'Actualiza el estado de las membresías vencidas a EXPIRED de manera idempotente.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Revisando membresías vencidas..."))
        count = update_all_memberships()
        self.stdout.write(self.style.SUCCESS(f"Se actualizaron {count} membresías vencidas a estado EXPIRED."))

