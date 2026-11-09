from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import User, MemberProfile, UserRole

class MemberProfileInline(admin.StackedInline):
    model = MemberProfile
    can_delete = False
    verbose_name = _('Ficha de Socio')
    verbose_name_plural = _('Ficha de Socio')
    readonly_fields = ['qr_token', 'qr_preview', 'created_at']
    fields = ['rut', 'phone', 'birth_date', 'emergency_contact', 'qr_token', 'qr_preview', 'created_at']

    def qr_preview(self, instance):
        if instance.pk:
            return format_html(
                '<img src="{}" width="120" height="120" style="border: 2px solid #FFC400; border-radius: 8px; padding: 4px; background: #fff;" />',
                instance.generate_qr_base64()
            )
        return "-"
    qr_preview.short_description = "Vista previa QR"

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [MemberProfileInline]
    list_display = ['username', 'email', 'get_full_name', 'role_badge', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff', 'is_superuser']
    search_fields = ['username', 'first_name', 'last_name', 'email', 'profile__rut']
    ordering = ['-date_joined']

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Información Personal'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Rol y Permisos FitLife'), {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Fechas Importantes'), {'fields': ('last_login', 'date_joined')}),
    )

    def role_badge(self, obj):
        colors = {
            UserRole.ADMIN: '#dc3545',     # Rojo
            UserRole.RECEPTION: '#0d6efd', # Azul
            UserRole.MEMBER: '#198754',    # Verde
        }
        bg = colors.get(obj.role, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: #fff; padding: 3px 8px; border-radius: 12px; font-weight: bold; font-size: 11px;">{}</span>',
            bg,
            obj.get_role_display()
        )
    role_badge.short_description = 'Rol'

@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'formatted_rut', 'phone', 'qr_token', 'active_membership_summary', 'created_at']
    search_fields = ['rut', 'user__username', 'user__first_name', 'user__last_name', 'user__email']
    readonly_fields = ['qr_token', 'qr_preview', 'formatted_rut_display', 'active_membership_link', 'created_at']
    fields = ['user', 'rut', 'formatted_rut_display', 'phone', 'birth_date', 'emergency_contact', 'qr_token', 'qr_preview', 'active_membership_link', 'created_at']
    ordering = ['-created_at']

    def qr_preview(self, instance):
        if instance.pk:
            return format_html(
                '<img src="{}" width="140" height="140" style="border: 2px solid #FFC400; border-radius: 8px; padding: 4px; background: #fff;" />',
                instance.generate_qr_base64()
            )
        return "-"
    qr_preview.short_description = "Vista previa Pase QR"

    def formatted_rut_display(self, instance):
        return instance.formatted_rut
    formatted_rut_display.short_description = "RUT Formateado"

    def active_membership_summary(self, instance):
        mem = instance.user.memberships.filter(status='ACTIVE').first()
        if mem:
            return format_html('<span style="color: #198754; font-weight: bold;">{} (hasta {})</span>', mem.plan.name, mem.end_date.strftime('%d/%m/%Y'))
        return format_html('<span style="color: #dc3545;">Sin membresía activa</span>')
    active_membership_summary.short_description = "Membresía Vigente"

    def active_membership_link(self, instance):
        mem = instance.user.memberships.order_by('-end_date').first()
        if mem:
            from django.urls import reverse
            url = reverse('admin:memberships_membership_change', args=[mem.id])
            return format_html('<a href="{}" target="_blank">Ver membresía {} ({})</a>', url, mem.plan.name, mem.get_status_display())
        return "No registra membresías."
    active_membership_link.short_description = "Membresía vinculada"

