from rest_framework import permissions
from .models import UserRole

class IsAdminRole(permissions.BasePermission):
    """Permiso solo para usuarios con rol Administrador o superusuarios."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.role == UserRole.ADMIN or request.user.is_superuser))

class IsReceptionRole(permissions.BasePermission):
    """Permiso para personal de recepción o administradores (basado estrictamente en roles)."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in [UserRole.RECEPTION, UserRole.ADMIN])

class IsMemberRole(permissions.BasePermission):
    """Permiso para socios registrados."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == UserRole.MEMBER)

class IsOwnerOrStaff(permissions.BasePermission):
    """Permite el acceso si el usuario es staff/recepción o es el dueño del objeto."""
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role in [UserRole.ADMIN, UserRole.RECEPTION]:
            return True
        # Si el objeto es un User
        if hasattr(obj, 'username'):
            return obj == request.user
        # Si el objeto tiene campo member o user
        if hasattr(obj, 'member'):
            return obj.member == request.user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False
