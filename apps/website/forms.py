from django import forms
from django.contrib.auth import authenticate
from apps.accounts.models import User, MemberProfile, UserRole
from apps.accounts.validators import validate_rut, clean_rut
from .models import ContactMessage

class MemberRegistrationForm(forms.ModelForm):
    first_name = forms.CharField(label="Nombre", max_length=50, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Juan'}))
    last_name = forms.CharField(label="Apellidos", max_length=50, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Pérez González'}))
    email = forms.EmailField(label="Correo Electrónico", required=True, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.cl'}))
    rut = forms.CharField(label="RUT", max_length=15, required=True, validators=[validate_rut], widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '12.345.678-5'}))
    phone = forms.CharField(label="Teléfono", max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+56 9 1234 5678'}))
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Mínimo 6 caracteres'}))
    password_confirm = forms.CharField(label="Confirmar Contraseña", widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Repite la contraseña'}))

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de usuario único'}),
        }

    def clean_rut(self):
        rut = self.cleaned_data.get('rut')
        cleaned = clean_rut(rut)
        if MemberProfile.objects.filter(rut=cleaned).exists():
            raise forms.ValidationError("Este RUT ya se encuentra registrado en FitLife.")
        return cleaned

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', 'Las contraseñas no coinciden.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = UserRole.MEMBER
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            MemberProfile.objects.create(
                user=user,
                rut=self.cleaned_data['rut'],
                phone=self.cleaned_data.get('phone', '')
            )
        return user


class MemberLoginForm(forms.Form):
    username = forms.CharField(label="Usuario o Correo", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingresa tu usuario'}))
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Ingresa tu contraseña'}))
    remember_me = forms.BooleanField(label="Recordarme en este equipo", required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tu nombre completo'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'tu-correo@ejemplo.cl'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Asunto de tu consulta'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': '¿En qué podemos ayudarte?'}),
        }


class SimulatedPaymentForm(forms.Form):
    card_holder = forms.CharField(label="Nombre del Titular", max_length=100, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Como aparece en la tarjeta'}))
    card_number = forms.CharField(label="Número de Tarjeta", max_length=19, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '4500 0000 0000 1234'}))
    card_expiry = forms.CharField(label="Vencimiento (MM/AA)", max_length=5, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '12/28'}))
    card_cvv = forms.CharField(label="CVV / CVC", max_length=4, widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '123'}))

