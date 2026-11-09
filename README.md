# FitLife — Plataforma de Control de Asistencia y Reserva de Clases
**Evaluación 3 (100% Individual) — Asignatura: Desarrollo Backend — INACAP**  
**Estudiante:** Benjamin Gomez  
**Sección:** AP-N4-C1  
**Profesor Evaluador:** Evaluación Presencial / Defensa en Vivo  
**Fecha:** Noviembre 2026  

---

```
================================================================================
                    IP PÚBLICA DE AWS EC2 (AWS ACADEMY):
                         http://[TU_IP_PUBLICA_AQUI]
================================================================================
```
> **Nota para la defensa en AWS Academy:** Las instancias de AWS Academy no poseen Elastic IP fija por defecto; cada vez que se inicia el laboratorio, AWS asigna una nueva IP pública. Al desplegar o reiniciar la máquina, actualiza este recuadro y las variables `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS` en el archivo `.env`.

---

## 0. Cumplimiento de la Rúbrica Oficial EVA 3 (100 Puntos)

| # | Criterio de Evaluación | Puntaje | Dónde y Cómo se Cumple en el Código |
|---|---|:---:|---|
| **1** | **Base de Datos PostgreSQL** | 20 pts | PostgreSQL 16 como motor obligatorio en producción con `psycopg2-binary`. 25 migraciones relacionales aplicadas, normalización e integridad referencial, índices en UUIDs y fechas, y comando auditor `python manage.py dbinfo`. |
| **2** | **Administrador de Django** | 20 pts | 12 modelos del dominio registrados con filtros, búsquedas y jerarquías. Templates sobreescritos (`base_site.html`, `index.html`, `change_list.html`, `change_form.html`) con paleta FitLife amarillo/negro, badges calculados, vista previa de Pase QR e inlines. |
| **3** | **CRUD y Reglas de Negocio** | 20 pts | Implementadas en `services.py`: Planes/Membresías/Pagos con transacción atómica, validación QR con alternancia IN/OUT en milisegundos, concurrencia segura en reservas con `select_for_update()` y lista de espera con auto-promoción, y aforo en tiempo real con semáforo. |
| **4** | **Seguridad, Sesiones e IA** | 20 pts | Sesiones `HttpOnly` + `SameSite=Lax`, JWT para API REST, protección IDOR con `IsOwnerOrStaff`, logout por `POST` con CSRF, redirección de URLs inexistentes al inicio, y documento `prompts_ia.md` con 8 entradas estructuradas y tabla de errores corregidos. |
| **5** | **Despliegue en EC2 y Defensa** | 20 pts | Despliegue en Ubuntu EC2 con Nginx + Gunicorn + PostgreSQL local. Scripts listos en `deploy/`, soporte de contexto seguro para cámara web, selector de pruebas demo, y guía de estudio `DEFENSA.md` con guion de 8 minutos y preguntas docentes. |

---

## 1. Descripción del Proyecto

**FitLife** es una plataforma integral desarrollada en Django y Django REST Framework para resolver las problemáticas operativas de un centro deportivo de alta afluencia:
1. **Control de Membresías y Pagos:** Gestión de suscripciones activas, congeladas y vencidas con pasarela de pago simulada y transacciones atómicas.
2. **Validación y Registro de Acceso por QR:** Lectura ultra rápida mediante cámara web o simulador por token UUID, control de alternancia automática Entrada/Salida (toggle IN/OUT) e integridad de acceso.
3. **Reserva Concurrente de Clases Grupales:** Cupos garantizados sin sobreventa mediante bloqueos a nivel de fila (`select_for_update`) con lista de espera dinámica y promoción automática tras cancelaciones.
4. **Dashboard de Aforo en Tiempo Real:** Monitor continuo que calcula los socios dentro del recinto, alerta mediante semáforo de ocupación y grafica ingresos por hora con Chart.js cada 5 segundos.
5. **Django Admin Personalizado:** Portal administrativo con identidad visual FitLife (amarillo `#FFC400` y negro `#111111`), métricas en vivo en la portada y acciones por lote.

---

## 2. Stack Tecnológico

| Capa | Tecnología |
|---|---|
| **Lenguaje** | Python 3.11+ / Python 3.14 |
| **Framework Backend** | Django 5.x / 6.x |
| **API REST** | Django REST Framework + `django-filter` |
| **Autenticación** | Sesiones Django (Web) + JWT `djangorestframework-simplejwt` (API) |
| **Base de Datos** | PostgreSQL (Producción EC2 y Entorno Local) |
| **Generación QR** | `qrcode[pil]` (Data URI Base64 en memoria sin archivos temporales) |
| **Frontend** | HTML5 semántico, CSS3 Vanilla (Mobile-first, paleta Smart Fit), JavaScript Vanilla |
| **Librerías CDN** | `html5-qrcode` (Lector de cámara web), `Chart.js` (Gráficos), FontAwesome 6 |
| **Servidor Web / WSGI** | Gunicorn + Nginx como proxy inverso |
| **Infraestructura Cloud** | Instancia única EC2 Ubuntu (AWS Academy) |

---

## 3. Estructura del Código

```text
EVA3_BACKEND_Fitlife/
├── manage.py
├── config/                  # Configuración central (settings, urls, wsgi, asgi, api_urls, middleware)
├── apps/
│   ├── accounts/            # User personalizado (AbstractUser), roles, perfil socio, RUT, QR token, dbinfo
│   ├── memberships/         # Planes comerciales, membresías, pagos simulados, servicios
│   ├── access/              # Registros de acceso (AccessLog), configuración de aforo (FacilitySetting)
│   ├── classes/             # Disciplinas, sesiones programadas, reservas con concurrencia
│   └── website/             # Vistas públicas, portal del socio, escáner de recepción y dashboard
├── templates/               # base.html, 404, 403, 500, website/, admin/ (overrides con branding)
├── static/                  # css/ (style.css, admin_custom.css), js/ (aforo.js, reception.js), img/ (logo.svg)
├── deploy/                  # gunicorn.service, nginx.conf, deploy.sh
├── tests/                   # Suite de pruebas automatizadas (20 pruebas unitarias y de integración)
├── DEFENSA.md               # Guía paso a paso para la defensa en vivo (guion 8 min y preguntas del docente)
├── requirements.txt         # Dependencias con versiones fijadas
├── prompts_ia.md            # Registro formal de evidencia de uso de IA (Rúbrica INACAP)
├── .env.example             # Plantilla de variables de entorno seguras
└── .gitignore               # Exclusión de venv, .env, __pycache__, estáticos y medios
```

---

## 4. Usuarios Demo y Credenciales para la Defensa en Vivo

Para facilitar la evaluación docente, se incluye el comando idempotente:
```bash
python manage.py seed_demo
```
Dicho comando crea los siguientes perfiles de usuario listos para probar:

| Rol | Usuario / Correo | Contraseña | Propósito en la Defensa |
|---|---|---|---|
| **Administrador** | `admin` / `admin@fitlife.cl` | `Admin#FitLife2026` | Acceso completo al Django Admin (`/admin/`), métricas vivas, gestión de planes y sesiones. |
| **Recepción** | `recepcion` / `recepcion@fitlife.cl` | `RecepcionFitLife2026!` | Operador de torniquete QR (`/recepcion/acceso/`), monitor de aforo, congelar/descongelar y pago manual. |
| **Socio ACTIVO** | `carlos.silva` | `SocioFitLife2026!` | Membresía activa (FitLife Black). Valida **ACCESO PERMITIDO**. |
| **Socio VENCIDO** | `maria.gonzalez` | `SocioFitLife2026!` | Membresía vencida. Simula y prueba **ACCESO DENEGADO (EXPIRED)**. |
| **Socio CONGELADO** | `juan.perez` | `SocioFitLife2026!` | Membresía pausada. Simula y prueba **ACCESO DENEGADO (FROZEN)**. |
| **Socio LISTA ESPERA** | `valentina.munoz` | `SocioFitLife2026!` | Inscrita en lista de espera de Spinning. Permite demostrar la **promoción automática**. |

> **Tarjeta Demo en el Login (`SHOW_DEMO_CREDENTIALS`):**  
> Cuando `SHOW_DEMO_CREDENTIALS=True` en `.env`, aparece una tarjeta debajo del formulario de login con un botón **"Autocompletar"** para rellenar usuario y contraseña automáticamente. En despliegues públicos fuera de la defensa evaluativa, debe configurarse en `False`.

---

## 5. Comandos de Gestión Personalizados

FitLife incluye comandos específicos para auditar y administrar el sistema:

### 1. Auditoría de Base de Datos (`dbinfo`)
Imprime en consola el motor ORM conectado, versión del servidor, host, puerto, cantidad de migraciones aplicadas y conteo de filas de las 8 tablas principales:
```bash
python manage.py dbinfo
```

### 2. Poblamiento de Datos Demo (`seed_demo`)
```bash
# Ejecución estándar idempotente (no destruye datos existentes):
python manage.py seed_demo

# Sincronizar o forzar actualización de contraseñas de los usuarios demo:
python manage.py seed_demo --reset-passwords

# Limpiar y regenerar sesiones y membresías demo (requiere --force si DEBUG=False):
python manage.py seed_demo --reset --force
```

### 3. Vencimiento por Lotes de Membresías (`update_memberships`)
Evalúa todas las membresías con fecha anterior a hoy y las pasa a estado `EXPIRED`. Es idempotente:
```bash
python manage.py update_memberships
```

---

## 6. Despliegue en AWS EC2 (AWS Academy)

### Paso 1: Configurar la Instancia Ubuntu
- Security Group con puertos:
  - `22` (SSH)
  - `80` (HTTP)

### Paso 2: Instalar Paquetes Base del Sistema
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv postgresql postgresql-contrib nginx git libpq-dev
```

### Paso 3: Configurar PostgreSQL
```bash
sudo -u postgres psql
```
Dentro de la consola PostgreSQL:
```sql
CREATE DATABASE fitlife_db;
CREATE USER fitlife_user WITH PASSWORD 'fitlife_secure_password_2026';
ALTER ROLE fitlife_user SET client_encoding TO 'utf8';
ALTER ROLE fitlife_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE fitlife_user SET timezone TO 'America/Santiago';
GRANT ALL PRIVILEGES ON DATABASE fitlife_db TO fitlife_user;
ALTER DATABASE fitlife_db OWNER TO fitlife_user;
-- Permiso CREATEDB para ejecutar la suite de pruebas automatizadas:
ALTER USER fitlife_user CREATEDB;
\q
```

### Paso 4: Clonar Proyecto y Crear Entorno Virtual
```bash
cd /home/ubuntu
git clone <URL_DE_TU_REPOSITORIO> EVA3_BACKEND_Fitlife
cd EVA3_BACKEND_Fitlife

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Paso 5: Permisos de Directorios para Nginx
Para evitar el error 403 Forbidden de Nginx al servir archivos estáticos desde `/home/ubuntu`:
```bash
sudo chmod o+x /home/ubuntu
sudo chown -R ubuntu:www-data /home/ubuntu/EVA3_BACKEND_Fitlife
```

### Paso 6: Configurar Variables de Entorno de Producción
```bash
cp .env.example .env
nano .env
```
Genera una clave secreta segura con:
```bash
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```
Configura tu `.env`:
```ini
SECRET_KEY=tu-clave-generada-aqui
DEBUG=False
ALLOWED_HOSTS=TU_IP_PUBLICA_EC2,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://TU_IP_PUBLICA_EC2,http://localhost
DB_ENGINE=django.db.backends.postgresql
DB_NAME=fitlife_db
DB_USER=fitlife_user
DB_PASSWORD=fitlife_secure_password_2026
DB_HOST=localhost
DB_PORT=5432
SHOW_DEMO_CREDENTIALS=True
```

### Paso 7: Migraciones, Estáticos y Seed
```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py seed_demo --reset-passwords
python manage.py dbinfo
```

### Paso 8: Configurar Gunicorn y Nginx
```bash
# Gunicorn systemd
sudo cp deploy/gunicorn.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start gunicorn
sudo systemctl enable gunicorn

# Nginx reverse proxy
sudo cp deploy/nginx.conf /etc/nginx/sites-available/fitlife
sudo ln -s /etc/nginx/sites-available/fitlife /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

### Paso 9: Cron Job para Vencimiento Diario de Membresías
Para automatizar la ejecución del comando `update_memberships` a las 00:05 cada noche:
```bash
crontab -e
```
Agrega la siguiente línea al final:
```text
5 0 * * * /home/ubuntu/EVA3_BACKEND_Fitlife/venv/bin/python /home/ubuntu/EVA3_BACKEND_Fitlife/manage.py update_memberships >> /home/ubuntu/EVA3_BACKEND_Fitlife/cron.log 2>&1
```

---

## 7. Batería de Pruebas Automatizadas

Se construyó una suite de 20 pruebas unitarias y de integración que validan el 100% de las reglas críticas:
```bash
python manage.py test tests
```

### Cómo Correr los Tests con PostgreSQL
Para que Django pueda crear la base de datos de pruebas (`test_fitlife_db`), el usuario de PostgreSQL requiere el permiso `CREATEDB`:
```sql
ALTER USER fitlife_user CREATEDB;
```

### Resumen de Pruebas Incluidas:
1. `test_access_denied_with_expired_membership`: Rechazo automático por membresía vencida (HTTP 403).
2. `test_access_denied_with_frozen_membership`: Rechazo automático por membresía congelada (HTTP 403).
3. `test_access_allowed_and_toggle_in_out`: Alternancia Entrada / Salida en un solo token QR.
4. `test_access_denied_when_facility_capacity_full`: Bloqueo inmediato al superar aforo máximo.
5. `test_booking_quota_and_waitlist_order`: Cupo confirmado y asignación de posición en lista de espera.
6. `test_automatic_promotion_on_cancellation`: Promoción atómica y notificación interna al cancelar reserva.
7. `test_cancellation_deadline_within_two_hours`: Restricción estricta de cancelación con < 2 horas.
8. `test_nonexistent_web_urls_redirect_to_home`: Redirección 302 a `/` ante cualquier URL web inexistente.
9. `test_admin_nonexistent_url_redirects_when_staff_logged_in`: Redirección a `/` en rutas de admin erróneas.
10. `test_nonexistent_api_url_returns_404_json`: La API responde con JSON 404 estructurado sin redirigir a HTML.
11. `test_login_with_username_redirects_to_admin`: Inicio de sesión exitoso por username (`admin`).
12. `test_login_with_email_redirects_to_admin`: Inicio de sesión exitoso por correo (`admin@fitlife.cl`).
13. `test_login_demo_card_visibility_when_enabled`: Renderizado de tarjeta demo con autocompletar.
14. `test_member_forbidden_create_membership`: Socio recibe 403 al intentar crear membresías por API.
15. `test_member_forbidden_edit_membership`: Socio recibe 403 al intentar modificar membresías por API.
16. `test_member_forbidden_create_payment`: Socio recibe 403 al intentar registrar pagos por API.
17. `test_booking_disallows_patch_and_delete`: Endpoint de reservas bloquea métodos PATCH y DELETE (405).
18. `test_member_forbidden_detailed_aforo_and_access_logs`: Socio recibe 403 en `/api/aforo/` y logs detallados.
19. `test_idor_protection_member_cannot_see_other_member_data`: Control IDOR probado entre dos socios distintos.
20. `test_skip_inactive_member_on_waitlist_promotion`: Salto y cancelación de socios vencidos en lista de espera.

---

## 8. Archivos Excluidos del Control de Versiones (`.gitignore`)

Los siguientes elementos **nunca** deben subirse al repositorio Git:
- `.env` (contiene secretos y contraseñas de producción)
- `venv/` (entorno virtual local)
- `*.sqlite3` (bases de datos locales de desarrollo)
- `staticfiles/` (recolectados dinámicamente con `collectstatic`)
- `media/` (archivos subidos por usuarios)
- `__pycache__/` y `*.pyc`

---

## 9. Pie de Firma y Autoría Obligatoria

En cumplimiento con los requerimientos de la evaluación de INACAP, el pie de página institucional se encuentra implementado tanto en el portal web de usuarios como en el Django Admin:

`Desarrollado por Benjamin Gomez · Sección AP-N4-C1 · INACAP · EVA 3 Desarrollo Backend`
