from rest_framework import serializers
from .models import User, MemberProfile, UserRole
from .validators import validate_rut, format_rut

class MemberProfileSerializer(serializers.ModelSerializer):
    formatted_rut = serializers.ReadOnlyField()
    qr_token = serializers.UUIDField(read_only=True)
    qr_base64 = serializers.SerializerMethodField()

    class Meta:
        model = MemberProfile
        fields = [
            'id', 'rut', 'formatted_rut', 'phone',
            'birth_date', 'emergency_contact',
            'qr_token', 'qr_base64', 'created_at'
        ]

    def get_qr_base64(self, obj) -> str:
        return obj.generate_qr_base64()

class UserSerializer(serializers.ModelSerializer):
    profile = MemberProfileSerializer(read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name',
            'last_name', 'role', 'role_display',
            'profile', 'date_joined'
        ]
        read_only_fields = ['id', 'date_joined']

class MemberRegisterSerializer(serializers.ModelSerializer):
    """Serializer para registro público de nuevos socios."""
    rut = serializers.CharField(write_only=True, validators=[validate_rut])
    phone = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'first_name', 'last_name', 'rut', 'phone']

    def create(self, validated_data):
        rut = validated_data.pop('rut')
        phone = validated_data.pop('phone', '')
        password = validated_data.pop('password')
        
        user = User.objects.create_user(
            role=UserRole.MEMBER,
            **validated_data
        )
        user.set_password(password)
        user.save()

        MemberProfile.objects.create(
            user=user,
            rut=rut,
            phone=phone
        )
        return user

