from rest_framework import serializers
from .models import ClassType, ClassSession, Booking

class ClassTypeSerializer(serializers.ModelSerializer):
    intensity_display = serializers.CharField(source='get_intensity_display', read_only=True)

    class Meta:
        model = ClassType
        fields = [
            'id', 'name', 'slug', 'description',
            'duration_minutes', 'intensity', 'intensity_display',
            'icon_or_image', 'is_active'
        ]

class ClassSessionSerializer(serializers.ModelSerializer):
    class_type_name = serializers.CharField(source='class_type.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    confirmed_count = serializers.IntegerField(read_only=True)
    waitlist_count = serializers.IntegerField(read_only=True)
    available_spots = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)

    class Meta:
        model = ClassSession
        fields = [
            'id', 'class_type', 'class_type_name', 'instructor_name',
            'room', 'start_datetime', 'end_datetime', 'capacity',
            'status', 'status_display', 'confirmed_count',
            'waitlist_count', 'available_spots', 'is_full'
        ]

class BookingSerializer(serializers.ModelSerializer):
    session_details = ClassSessionSerializer(source='session', read_only=True)
    member_name = serializers.CharField(source='member.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'session', 'session_details', 'member', 'member_name',
            'status', 'status_display', 'waitlist_position',
            'created_at', 'cancelled_at'
        ]
        read_only_fields = ['id', 'member', 'status', 'waitlist_position', 'created_at', 'cancelled_at']
