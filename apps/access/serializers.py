from rest_framework import serializers
from .models import AccessLog, FacilitySetting

class AccessLogSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.get_full_name', read_only=True)
    scanned_by_name = serializers.CharField(source='scanned_by.get_full_name', read_only=True)
    direction_display = serializers.CharField(source='get_direction_display', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    deny_reason_display = serializers.CharField(source='get_deny_reason_display', read_only=True)

    class Meta:
        model = AccessLog
        fields = [
            'id', 'member', 'member_name', 'scanned_by', 'scanned_by_name',
            'direction', 'direction_display', 'result', 'result_display',
            'deny_reason', 'deny_reason_display', 'timestamp'
        ]
        read_only_fields = ['id', 'timestamp']

class FacilitySettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacilitySetting
        fields = ['facility_name', 'max_capacity', 'warning_threshold_pct', 'danger_threshold_pct', 'updated_at']

class QRValidationRequestSerializer(serializers.Serializer):
    qr_token = serializers.CharField(required=True, help_text="UUID del código QR escaneado")

