#!/bin/bash
# ==============================================================================
# Script de Despliegue Automatizado para FitLife en AWS EC2 (Ubuntu)
# Estudiante: Benjamin Gomez · Sección AP-N4-C1 · INACAP · EVA 3 Backend
# ==============================================================================

set -e

PROJECT_DIR="/home/ubuntu/EVA3_BACKEND_Fitlife"
VENV_DIR="$PROJECT_DIR/venv"

echo "=== 1. Ingresando al directorio del proyecto ==="
cd "$PROJECT_DIR"

echo "=== 2. Actualizando código fuente desde Git ==="
git pull origin main || echo "Git pull omitido (modo local)"

echo "=== 3. Activando entorno virtual e instalando dependencias ==="
source "$VENV_DIR/bin/activate"
pip install -r requirements.txt

echo "=== 4. Ejecutando migraciones de la base de datos PostgreSQL ==="
python manage.py migrate --noinput

echo "=== 5. Recolectando archivos estáticos ==="
python manage.py collectstatic --noinput

echo "=== 6. Actualizando estado de membresías vencidas ==="
python manage.py update_memberships

echo "=== 7. Reiniciando servicio Gunicorn ==="
sudo systemctl restart gunicorn

echo "=== 8. Verificando estado del servidor Nginx ==="
sudo nginx -t && sudo systemctl reload nginx

echo "=============================================================================="
echo " ¡Despliegue de FitLife completado exitosamente en AWS EC2!"
echo " Recuerda verificar que la IP pública esté incluida en ALLOWED_HOSTS de .env"
echo "=============================================================================="

