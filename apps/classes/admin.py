from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import ClassType, ClassSession, Booking, BookingStatus, SessionStatus
from .services import admin_cancel_session

class BookingInline(admin.TabularInline):
    model = Booking
    extra = 0
    fields = ['member', 'status', 'waitlist_position', 'created_at']
    readonly_fields = ['created_at']
    can_delete = True
    ordering = ['status', 'waitlist_position', 'created_at']

@admin.register(ClassType)
class ClassTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'duration_minutes', 'intensity_badge', 'is_active']
    list_filter = ['intensity', 'is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}

    def intensity_badge(self, obj):
        colors = {
            'LOW': '#198754',    # Verde
            'MEDIUM': '#ffc107', # Amarillo
            'HIGH': '#dc3545',   # Rojo
        }
        color = colors.get(obj.intensity, '#6c757d')
        text_color = '#000' if obj.intensity == 'MEDIUM' else '#fff'
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 3px 8px; border-radius: 10px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            text_color,
            obj.get_intensity_display()
        )
    intensity_badge.short_description = 'Intensidad'

@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    inlines = [BookingInline]
    list_display = ['class_type', 'start_datetime', 'instructor_name', 'room', 'occupancy_badge', 'status_badge']
    list_filter = ['status', 'class_type', 'room', 'start_datetime']
    search_fields = ['class_type__name', 'instructor_name', 'room']
    date_hierarchy = 'start_datetime'
    ordering = ['-start_datetime']
    actions = ['action_cancel_sessions']

    def occupancy_badge(self, obj):
        confirmed = obj.confirmed_count
        cap = obj.capacity
        waitlist = obj.waitlist_count
        pct = (confirmed / cap) * 100 if cap > 0 else 0
        color = '#dc3545' if pct >= 100 else ('#ffc107' if pct >= 75 else '#198754')
        text_color = '#000' if pct >= 75 and pct < 100 else '#fff'
        extra = f" (+{waitlist} en espera)" if waitlist > 0 else ""
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 3px 8px; border-radius: 10px; font-weight: bold; font-size: 11px;">{}/{} cupos{}</span>',
            color, text_color, confirmed, cap, extra
        )
    occupancy_badge.short_description = 'Cupos Ocupados'

    def status_badge(self, obj):
        colors = {
            SessionStatus.SCHEDULED: '#0d6efd',
            SessionStatus.CANCELLED: '#dc3545',
            SessionStatus.DONE: '#6c757d',
        }
        return format_html(
            '<span style="background-color: {}; color: #fff; padding: 3px 8px; border-radius: 10px; font-weight: bold; font-size: 11px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Estado'

    @admin.action(description="Cancelar sesiones seleccionadas y notificar a los inscritos")
    def action_cancel_sessions(self, request, queryset):
        cancelled_count = 0
        for s in queryset.filter(status=SessionStatus.SCHEDULED):
            admin_cancel_session(s.id, staff_user=request.user, reason="Cancelación operativa desde panel administrativo")
            cancelled_count += 1
        self.message_user(request, f"Se cancelaron {cancelled_count} sesiones y se emitieron las notificaciones correspondientes.")

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['id', 'session_info', 'member_info', 'status_badge', 'waitlist_position', 'created_at']
    list_filter = ['status', 'session__class_type', 'session__start_datetime']
    search_fields = ['member__username', 'member__first_name', 'member__last_name', 'session__class_type__name']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    actions = ['action_mark_attended', 'action_mark_no_show']

    def session_info(self, obj):
        start = obj.session.start_datetime.strftime('%d/%m %H:%M')
        return f"{obj.session.class_type.name} ({start})"
    session_info.short_description = "Sesión"

    def member_info(self, obj):
        return f"{obj.member.get_full_name() or obj.member.username}"
    member_info.short_description = "Socio"

    def status_badge(self, obj):
        colors = {
            BookingStatus.CONFIRMED: '#198754', # Verde
            BookingStatus.WAITLIST: '#ffc107',  # Amarillo
            BookingStatus.CANCELLED: '#dc3545', # Rojo
            BookingStatus.ATTENDED: '#0d6efd',  # Azul
            BookingStatus.NO_SHOW: '#6c757d',   # Gris
        }
        color = colors.get(obj.status, '#6c757d')
        text_color = '#000' if obj.status == BookingStatus.WAITLIST else '#fff'
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 3px 8px; border-radius: 10px; font-weight: bold; font-size: 11px;">{}</span>',
            color, text_color, obj.get_status_display()
        )
    status_badge.short_description = 'Estado'

    @admin.action(description="Marcar asistencia (ATTENDED)")
    def action_mark_attended(self, request, queryset):
        count = queryset.update(status=BookingStatus.ATTENDED)
        self.message_user(request, f"Se marcaron {count} asistencias.")

    @admin.action(description="Marcar inasistencia (NO_SHOW)")
    def action_mark_no_show(self, request, queryset):
        count = queryset.update(status=BookingStatus.NO_SHOW)
        self.message_user(request, f"Se marcaron {count} inasistencias.")

