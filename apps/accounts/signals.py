from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, UserRole, MemberProfile

@receiver(post_save, sender=User)
def create_member_profile_if_needed(sender, instance, created, **kwargs):
    """
    Si se crea un usuario con rol MEMBER y no tiene perfil, se asegura que no rompa
    la lógica antes de que se completen sus datos en el registro o seed.
    """
    pass

