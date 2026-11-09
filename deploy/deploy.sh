#!/bin/bash
# ==============================================================================
# Script de Despliegue Automatizado para FitLife en AWS EC2 (Ubuntu 22.04 LTS)
# Basado en la Receta Oficial INACAP para Django REST Framework con Gunicorn y Nginx
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

echo "=== 5. Recolectando archivos estáticos para Nginx (/static/) ==="
python manage.py collectstatic --noinput

echo "=== 6. Actualizando estado de membresías vencidas ==="
python manage.py update_memberships

echo "=== 7. Ajustando permisos de directorios y socket (Receta INACAP ETAPA 5-6) ==="
sudo usermod -aG www-data ubuntu 2>/dev/null || true
sudo usermod -aG ubuntu www-data 2>/dev/null || true
sudo chmod 755 /home/ubuntu
sudo chmod 775 "$PROJECT_DIR"
sudo chown -R ubuntu:www-data "$PROJECT_DIR"
sudo chmod -R 755 "$PROJECT_DIR/staticfiles"
if [ -d "$PROJECT_DIR/media" ]; then
    sudo chmod -R 775 "$PROJECT_DIR/media"
fi

echo "=== 8. Reiniciando servicio Gunicorn ==="
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
sudo systemctl enable gunicorn

# Asegurar permisos correctos sobre el socket recién creado por Gunicorn
sleep 1
if [ -S "$PROJECT_DIR/fitlife.sock" ]; then
    sudo chown ubuntu:www-data "$PROJECT_DIR/fitlife.sock"
    sudo chmod 660 "$PROJECT_DIR/fitlife.sock"
    echo "✓ Socket fitlife.sock verificado con permisos ubuntu:www-data rw-rw----"
fi

echo "=== 9. Validando y recargando servidor Nginx ==="
sudo nginx -t
sudo systemctl restart nginx

echo "=============================================================================="
echo " ¡Despliegue de FitLife completado exitosamente según Receta INACAP!"
echo " Accede a tu plataforma desde cualquier navegador usando la IP de tu EC2:"
echo "   • Portal Web: http://<TU_IP_PUBLICA>/"
echo "   • Panel Admin: http://<TU_IP_PUBLICA>/admin/"
echo "   • API REST:   http://<TU_IP_PUBLICA>/api/"
echo "=============================================================================="
