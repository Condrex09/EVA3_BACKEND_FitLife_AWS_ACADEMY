from rest_framework import serializers
from .models import Plan, Membership, Payment

class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            'id', 'name', 'slug', 'description', 'monthly_price',
            'enrollment_price', 'duration_days', 'loyalty_months',
            'benefits', 'is_featured', 'is_active', 'order'
        ]

class MembershipSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    member_name = serializers.CharField(source='member.get_full_name', read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = Membership
        fields = [
            'id', 'member', 'member_name', 'plan', 'plan_name',
            'start_date', 'end_date', 'status', 'status_display',
            'frozen_from', 'frozen_until', 'days_remaining', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def validate(self, attrs):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Si no es administrador, no puede asignar miembros arbitrarios
            is_admin = request.user.is_staff or getattr(request.user, 'role', None) == 'ADMIN'
            if not is_admin and 'member' in attrs and attrs['member'] != request.user:
                raise serializers.ValidationError({'member': 'No tienes permisos para asignar membresías a otros socios.'})
        return super().validate(attrs)

class PaymentSerializer(serializers.ModelSerializer):
    concept_display = serializers.CharField(source='get_concept_display', read_only=True)
    method_display = serializers.CharField(source='get_method_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    member_name = serializers.CharField(source='member.get_full_name', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'membership', 'member', 'member_name', 'amount',
            'concept', 'concept_display', 'method', 'method_display',
            'status', 'status_display', 'reference', 'paid_at'
        ]
        read_only_fields = ['id', 'reference', 'paid_at']

    def validate(self, attrs):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            is_staff = request.user.is_staff or getattr(request.user, 'role', None) in ['ADMIN', 'RECEPTION']
            if not is_staff and 'member' in attrs and attrs['member'] != request.user:
                raise serializers.ValidationError({'member': 'No tienes permisos para registrar pagos a nombre de otros usuarios.'})
        return super().validate(attrs)
