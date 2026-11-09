#!/bin/bash
# ==============================================================================
# Script de Instalación Inicial de Servicios Gunicorn y Nginx (Receta INACAP)
# Ejecutar una sola vez en la instancia EC2:
#   chmod +x deploy/install_services.sh
#   ./deploy/install_services.sh
# ==============================================================================

set -e

PROJECT_DIR="/home/ubuntu/EVA3_BACKEND_Fitlife"

echo "=== 1. Instalando servicio Systemd de Gunicorn ==="
sudo cp "$PROJECT_DIR/deploy/gunicorn.service" /etc/systemd/system/gunicorn.service
sudo systemctl daemon-reload
sudo systemctl enable gunicorn

echo "=== 2. Configurando Nginx como Proxy Inverso ==="
sudo cp "$PROJECT_DIR/deploy/nginx.conf" /etc/nginx/sites-available/fitlife
sudo ln -sf /etc/nginx/sites-available/fitlife /etc/nginx/sites-enabled/fitlife
sudo rm -f /etc/nginx/sites-enabled/default

echo "=== 3. Ajustando permisos de grupos ubuntu y www-data (Receta INACAP) ==="
sudo usermod -aG www-data ubuntu 2>/dev/null || true
sudo usermod -aG ubuntu www-data 2>/dev/null || true
sudo chmod 755 /home/ubuntu
sudo chmod 775 "$PROJECT_DIR"
sudo chown -R ubuntu:www-data "$PROJECT_DIR"

echo "=== 4. Iniciando y validando servicios ==="
sudo systemctl start gunicorn
sudo nginx -t
sudo systemctl restart nginx

echo "=== 5. Estado de los servicios ==="
sudo systemctl status gunicorn --no-pager -l || true
sudo systemctl status nginx --no-pager -l || true

echo "=============================================================================="
echo " ¡Servicios instalados y configurados según la Receta Oficial INACAP!"
echo "=============================================================================="

