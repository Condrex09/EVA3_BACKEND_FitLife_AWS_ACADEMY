from django.contrib import admin
from .models import ContactMessage, Notification

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'subject', 'created_at', 'is_read']
    list_filter = ['is_read', 'created_at']
    search_fields = ['name', 'email', 'subject', 'message']
    list_editable = ['is_read']
    ordering = ['-created_at']
    save_on_top = True
    list_per_page = 25

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'member', 'created_at', 'is_read']
    list_filter = ['is_read', 'created_at']
    search_fields = ['title', 'member__username', 'member__first_name', 'member__last_name']
    autocomplete_fields = ['member']
    list_editable = ['is_read']
    ordering = ['-created_at']
    save_on_top = True
    list_per_page = 25
