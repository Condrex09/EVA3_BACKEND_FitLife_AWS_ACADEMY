from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import AccessLog, AccessResult, AccessDirection, FacilitySetting

@admin.register(FacilitySetting)
class FacilitySettingAdmin(admin.ModelAdmin):
    list_display = ['facility_name', 'max_capacity', 'warning_threshold_pct', 'danger_threshold_pct', 'updated_at']
    save_on_top = True

    def has_add_permission(self, request):
        # Impedir crear múltiples instancias para mantener el patrón Singleton de la sede
        return not FacilitySetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Desactivado: la configuración de sede única no puede eliminarse
        return False


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'timestamp', 'member_info', 'direction_badge', 'result_badge', 'deny_reason_display', 'scanned_by']
    list_filter = ['result', 'direction', 'deny_reason', 'timestamp']
    search_fields = ['member__username', 'member__first_name', 'member__last_name', 'member__profile__rut']
    autocomplete_fields = ['member', 'scanned_by']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    save_on_top = True
    list_per_page = 25
    show_full_result_count = False

    def has_delete_permission(self, request, obj=None):
        # Desactivado para conservar la trazabilidad y auditoría de accesos al recinto deportivo
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj:
            # En registros históricos existentes, todos los campos son de solo lectura para evitar alteraciones
            return ['member', 'scanned_by', 'direction', 'result', 'deny_reason', 'timestamp']
        # Al registrar un acceso manual, permitir seleccionar socio, dirección y resultado
        return ['timestamp']

    def member_info(self, obj):
        if obj.member:
            rut = getattr(getattr(obj.member, 'profile', None), 'formatted_rut', '')
            return f"{obj.member.get_full_name() or obj.member.username} ({rut})"
        return format_html('<span style="color: #999;">Anónimo / QR Inválido</span>')
    member_info.short_description = "Socio"

    def direction_badge(self, obj):
        if obj.direction == AccessDirection.IN:
            return format_html('<span style="background-color: #0d6efd; color: #fff; padding: 2px 7px; border-radius: 10px; font-weight: bold; font-size: 11px;">⬇ Entrada</span>')
        return format_html('<span style="background-color: #6c757d; color: #fff; padding: 2px 7px; border-radius: 10px; font-weight: bold; font-size: 11px;">⬆ Salida</span>')
    direction_badge.short_description = "Dirección"

    def result_badge(self, obj):
        if obj.result == AccessResult.ALLOWED:
            return format_html('<span style="background-color: #198754; color: #fff; padding: 3px 8px; border-radius: 12px; font-weight: bold; font-size: 11px;">PERMITIDO</span>')
        return format_html('<span style="background-color: #dc3545; color: #fff; padding: 3px 8px; border-radius: 12px; font-weight: bold; font-size: 11px;">DENEGADO</span>')
    result_badge.short_description = "Resultado"

    def deny_reason_display(self, obj):
        return obj.get_deny_reason_display() if obj.deny_reason else "-"
    deny_reason_display.short_description = "Motivo de rechazo"
