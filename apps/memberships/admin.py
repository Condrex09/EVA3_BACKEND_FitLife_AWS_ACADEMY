import csv
from datetime import timedelta
from django.contrib import admin
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Plan, Membership, MembershipStatus, Payment, PaymentStatus

@admin.action(description="Exportar registros seleccionados a archivo CSV")
def export_to_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename={modeladmin.model._meta.verbose_name_plural}.csv'
    writer = csv.writer(response)
    field_names = [f.name for f in modeladmin.model._meta.fields]
    writer.writerow(field_names)
    for obj in queryset:
        writer.writerow([getattr(obj, field) for field in field_names])
    return response

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'monthly_price', 'enrollment_price_clp', 'duration_days', 'loyalty_months', 'is_featured', 'is_active', 'order']
    list_editable = ['monthly_price', 'is_featured', 'is_active', 'order']
    list_filter = ['is_active', 'is_featured']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order', 'monthly_price']
    actions = [export_to_csv]
    save_as = True
    save_on_top = True
    list_per_page = 25

    def monthly_price_clp(self, obj):
        return f"${obj.monthly_price:,} CLP"
    monthly_price_clp.short_description = "Precio Mensual"

    def enrollment_price_clp(self, obj):
        return f"${obj.enrollment_price:,} CLP"
    enrollment_price_clp.short_description = "Matrícula"

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ['id', 'member', 'plan', 'status_badge', 'start_date', 'end_date', 'days_left', 'created_at']
    list_filter = ['status', 'plan', 'start_date', 'end_date']
    search_fields = ['member__username', 'member__first_name', 'member__last_name', 'member__profile__rut', 'plan__name']
    autocomplete_fields = ['member', 'plan']
    date_hierarchy = 'start_date'
    actions = ['action_freeze_30_days', 'action_mark_expired', 'action_unfreeze', export_to_csv]
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    save_on_top = True
    list_per_page = 25
    show_full_result_count = False

    def status_badge(self, obj):
        colors = {
            MembershipStatus.ACTIVE: '#198754',  # Verde
            MembershipStatus.EXPIRED: '#dc3545', # Rojo
            MembershipStatus.FROZEN: '#0dcaf0',  # Celeste / Azul
        }
        color = colors.get(obj.status, '#6c757d')
        text_color = '#000' if obj.status == MembershipStatus.FROZEN else '#fff'
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            text_color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Estado'

    def days_left(self, obj):
        days = obj.days_remaining
        if obj.status == MembershipStatus.ACTIVE:
            return format_html('<strong>{} días</strong>', days)
        return "-"
    days_left.short_description = 'Días restantes'

    @admin.action(description="Congelar membresías seleccionadas por 30 días")
    def action_freeze_30_days(self, request, queryset):
        today = timezone.localdate()
        until = today + timedelta(days=30)
        updated = 0
        for m in queryset.filter(status=MembershipStatus.ACTIVE):
            m.status = MembershipStatus.FROZEN
            m.frozen_from = today
            m.frozen_until = until
            m.save()
            updated += 1
        self.message_user(request, f"Se congelaron {updated} membresías hasta el {until}.")

    @admin.action(description="Descongelar membresías seleccionadas")
    def action_unfreeze(self, request, queryset):
        today = timezone.localdate()
        updated = 0
        for m in queryset.filter(status=MembershipStatus.FROZEN):
            days_frozen = max(0, (today - (m.frozen_from or today)).days)
            if days_frozen > 0:
                m.end_date = m.end_date + timedelta(days=days_frozen)
            m.status = MembershipStatus.ACTIVE
            m.frozen_from = None
            m.frozen_until = None
            m.save()
            updated += 1
        self.message_user(request, f"Se descongelaron {updated} membresías reactivadas.")

    @admin.action(description="Marcar membresías seleccionadas como VENCIDAS (EXPIRED)")
    def action_mark_expired(self, request, queryset):
        count = queryset.update(status=MembershipStatus.EXPIRED)
        self.message_user(request, f"Se marcaron {count} membresías como vencidas.")

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['reference', 'member', 'amount_clp', 'concept', 'method', 'registered_by', 'status_badge', 'paid_at']
    list_filter = ['status', 'concept', 'method', 'paid_at']
    search_fields = ['reference', 'member__username', 'member__first_name', 'member__last_name', 'member__profile__rut', 'registered_by__username']
    autocomplete_fields = ['member', 'registered_by']
    date_hierarchy = 'paid_at'
    readonly_fields = ['reference', 'paid_at']
    actions = ['action_approve_payments', export_to_csv]
    ordering = ['-paid_at']
    save_on_top = True
    list_per_page = 25
    show_full_result_count = False

    def amount_clp(self, obj):
        return f"${obj.amount:,} CLP"
    amount_clp.short_description = "Monto"

    def status_badge(self, obj):
        colors = {
            PaymentStatus.APPROVED: '#198754', # Verde
            PaymentStatus.REJECTED: '#dc3545', # Rojo
            PaymentStatus.PENDING: '#ffc107',  # Amarillo
        }
        color = colors.get(obj.status, '#6c757d')
        text_color = '#000' if obj.status == PaymentStatus.PENDING else '#fff'
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            text_color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Estado'

    @admin.action(description="Aprobar pagos pendientes seleccionados")
    def action_approve_payments(self, request, queryset):
        count = queryset.filter(status=PaymentStatus.PENDING).update(status=PaymentStatus.APPROVED)
        self.message_user(request, f"Se aprobaron {count} pagos pendientes.")

