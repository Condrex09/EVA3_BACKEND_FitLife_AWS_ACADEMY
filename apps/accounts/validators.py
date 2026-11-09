import re
from django.core.exceptions import ValidationError

def clean_rut(rut: str) -> str:
    """Elimina puntos y guiones y pasa el dígito verificador a mayúscula."""
    if not rut:
        return ""
    return re.sub(r'[^0-9kK]', '', str(rut)).upper()

def calculate_dv(rut_body: int) -> str:
    """Calcula el dígito verificador chileno usando Módulo 11."""
    multiplier = 2
    total = 0
    for digit in reversed(str(rut_body)):
        total += int(digit) * multiplier
        multiplier = 2 if multiplier == 7 else multiplier + 1
    mod = 11 - (total % 11)
    if mod == 11:
        return '0'
    elif mod == 10:
        return 'K'
    return str(mod)

def validate_rut(value: str):
    """
    Valida un RUT chileno según el algoritmo oficial de Módulo 11.
    Acepta formatos con o sin puntos y con o sin guión (ej: 12.345.678-5 o 123456785).
    """
    cleaned = clean_rut(value)
    if len(cleaned) < 8 or len(cleaned) > 9:
        raise ValidationError('El RUT ingresado no tiene un largo válido (ejemplo: 12.345.678-5).')
    
    body = cleaned[:-1]
    dv = cleaned[-1]

    if not body.isdigit():
        raise ValidationError('El cuerpo del RUT debe contener solo números.')

    expected_dv = calculate_dv(int(body))
    if dv != expected_dv:
        raise ValidationError(f'El dígito verificador es incorrecto para el RUT ingresado (esperado: {expected_dv}).')

def format_rut(rut: str) -> str:
    """Formatea un RUT a formato estándar XX.XXX.XXX-X."""
    cleaned = clean_rut(rut)
    if len(cleaned) < 2:
        return cleaned
    body = cleaned[:-1]
    dv = cleaned[-1]
    # Invertir para agregar puntos cada 3 dígitos
    reversed_body = body[::-1]
    chunks = [reversed_body[i:i+3] for i in range(0, len(reversed_body), 3)]
    formatted_body = '.'.join(chunks)[::-1]
    return f"{formatted_body}-{dv}"

