from django.contrib import admin
from .models import ContactMessage, Notification

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'subject', 'created_at', 'is_read']
    list_filter = ['is_read', 'created_at']
    search_fields = ['name', 'email', 'subject', 'message']
    ordering = ['-created_at']

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'member', 'created_at', 'is_read']
    list_filter = ['is_read', 'created_at']
    search_fields = ['title', 'member__username', 'member__first_name', 'member__last_name']
    ordering = ['-created_at']

