# GUÍA DE DEFENSA EN VIVO — FitLife (EVA 3 Backend)
**Estudiante:** Benjamin Gomez  
**Sección:** AP-N4-C1  
**Asignatura:** Desarrollo Backend — INACAP  
**Centro Evaluado:** FitLife Centro Deportivo  

---

## 1. Arquitectura en 1 Minuto

### Diagrama del Stack Tecnológico
```text
[ Cliente / Navegador Web ] (HTML5, CSS3, Vanilla JS, Chart.js, html5-qrcode)
            │  HTTP (Puerto 80)
            ▼
   [ Servidor Nginx (Proxy Inverso) ]
   ├── Sirve estáticos directamente: /static/ y /media/
   └── Redirige tráfico dinámico vía socket UNIX o proxy HTTP
            ▼
   [ Servidor de Aplicación Gunicorn (WSGI) ]
   └── Maneja procesos worker de Python/Django
            ▼
   [ Framework Django 5.x / DRF ]
   ├── config/ (settings, urls, wsgi, asgi)
   ├── apps/accounts/    -> Usuarios, roles (ADMIN, RECEPTION, MEMBER), perfiles, RUT
   ├── apps/memberships/ -> Planes comerciales, membresías, estados, pagos
   ├── apps/access/      -> Pases QR, bitácora de accesos, cálculo de aforo en tiempo real
   ├── apps/classes/     -> Disciplinas, sesiones programadas, reservas con lista de espera
   └── apps/website/     -> Vistas públicas, checkout, panel socio, dashboards de staff
            ▼
   [ Base de Datos PostgreSQL 16 ] (Relacional, con índices, transacciones y constraints)
```

---

## 2. Guion de Demostración en Vivo (~8 Minutos)

| Paso | Tiempo | Qué Mostrar / Qué Hacer | Usuario / Credencial | Qué Explicar al Docente |
|---|---|---|---|---|
| **1. Portada y Planes** | 0:00 - 1:00 | Abrir `http://<IP_EC2>/`, mostrar diseño amarillo/negro inspirado en gimnasios modernos, catálogo de planes en CLP y carrusel de clases. | Público (anónimo) | "Desarrollé la interfaz con HTML5 y CSS3 mobile-first propio, sin React ni Vue, optimizado para carga rápida en cualquier dispositivo." |
| **2. Registro y Checkout Simulado** | 1:00 - 2:15 | Clic en "¡Inscríbete ya!", registrar un socio de prueba con RUT chileno válido. Elegir plan FitLife Black. En checkout, probar tarjeta terminada en `0000` (se rechaza con mensaje bancario) y luego tarjeta válida (se aprueba en transacción atómica). | Registro nuevo | "El formulario valida el dígito verificador del RUT con Módulo 11. El pago simula la pasarela dentro de un bloque `transaction.atomic()` que activa la membresía." |
| **3. Mi Pase QR y Mi Espacio** | 2:15 - 3:15 | Ir a `/mi-cuenta/`. Mostrar badge de membresía ACTIVA, días restantes, bitácora de pagos y el **Pase QR dinámico** generado en base64 con la librería `qrcode`. | Socio recién registrado | "Cada socio tiene un UUID indexado e inmutable. El QR codifica exclusivamente ese token, evitando exponer datos personales en el código visual." |
| **4. Recepción: Validación QR y Toggle IN/OUT** | 3:15 - 4:45 | Iniciar sesión como recepcionista (`recepcion` / `RecepcionFitLife2026!`). Ir a `/recepcion/acceso/`. Usar el selector demo para probar: (1) `carlos.silva` (PERMITIDO - Entrada), (2) segundo escaneo de `carlos.silva` (PERMITIDO - Salida, toggle automático), (3) `maria.gonzalez` (DENEGADO - Membresía Vencida), (4) `juan.perez` (DENEGADO - Membresía Congelada). | `recepcion`<br>`RecepcionFitLife2026!` | "El endpoint `/api/access/validate/` ejecuta una consulta optimizada con `select_related`. Si el último acceso permitido fue Entrada, el siguiente registra automáticamente Salida." |
| **5. Reserva de Spinning y Lista de Espera** | 4:45 - 6:00 | Entrar como socio activo (`valentina.munoz` / `SocioFitLife2026!`). Ir a `/clases/reservar/`. Intentar reservar la sesión de Spinning (cupo 5/5 lleno). El sistema asigna cupo en Lista de Espera (#2). Luego, desde otra ventana o admin, cancelar una reserva confirmada y mostrar cómo Valentina es promovida automáticamente a CONFIRMADA y recibe una notificación interna. | `valentina.munoz`<br>`SocioFitLife2026!` | "Para prevenir condiciones de carrera, la reserva y cancelación usan `select_for_update()` sobre la sesión dentro de una transacción atómica. La cancelación hasta 2 horas antes promueve al primer socio activo de la lista." |
| **6. Dashboard de Aforo en Tiempo Real** | 6:00 - 6:45 | Ir a `/dashboard/aforo/`. Mostrar gráfico de ingresos por hora del día con Chart.js, porcentaje, color de semáforo y tabla de personas adentro. Explicar el refresco asíncrono cada 5 segundos mediante `fetch('/api/aforo/')`. | `recepcion` o `admin` | "El aforo se calcula en base al último registro `IN` sin `OUT` posterior. Si supera el 85%, el semáforo pasa a rojo y activa la alerta de sobrecupo." |
| **7. Django Admin Personalizado** | 6:45 - 7:30 | Ir a `/admin/` con `admin` / `Admin#FitLife2026`. Mostrar branding amarillo/negro FitLife, métricas de la portada, columnas calculadas con badges de colores, vista previa del QR en la ficha del socio y acciones por lote (congelar, exportar CSV). | `admin`<br>`Admin#FitLife2026` | "Personalicé los templates de admin con `base_site.html`, `index.html`, `change_list.html` y `change_form.html`. Todos los modelos del dominio están registrados." |
| **8. Evidencia PostgreSQL en EC2** | 7:30 - 8:00 | En la terminal SSH de AWS EC2, ejecutar `python manage.py dbinfo`. Mostrar motor `POSTGRESQL`, versión del servidor, 25 migraciones aplicadas y conteo de filas persistidas. | Terminal SSH EC2 | "Cumpliendo el Criterio 1, la base de datos es PostgreSQL en Ubuntu, sin SQLite, con integridad referencial y migraciones versionadas." |

---

## 3. Preguntas Típicas del Docente y Respuestas Clave

### Q1: ¿Por qué usaste `select_for_update()` en las reservas y cancelaciones?
> **Respuesta:** "Para evitar condiciones de carrera (*race conditions*). Si dos socios intentan reservar el último cupo simultáneamente, sin bloqueo ambos leerían que hay 1 cupo disponible y se crearía un sobrecupo. `select_for_update()` bloquea la fila de la sesión en PostgreSQL a nivel de base de datos hasta que la transacción termina; la segunda petición espera y, al ejecutarse, detecta que la sala ya está llena y la manda a lista de espera."

### Q2: ¿Cómo se calcula el aforo actual de la sede?
> **Respuesta:** "Con una subconsulta optimizada que obtiene el `id` máximo (`Max('id')`) de los registros permitidos por socio. Si el registro más reciente de ese socio tiene dirección `IN`, significa que ingresó y no ha registrado salida. El aforo es la cuenta de esos socios."

### Q3: ¿Por qué usas sesiones para la web y JWT para la API?
> **Respuesta:** "Porque las sesiones de Django con cookies `HttpOnly` y protección CSRF son el estándar más seguro para navegación web en navegadores tradicionales. Por su parte, JWT (`simplejwt`) es ideal para consumo de API sin estado (*stateless*), lo que permitiría conectar fácilmente una aplicación móvil futura."

### Q4: ¿Cómo evitan que un socio vea los datos o reservas de otro socio (IDOR)?
> **Respuesta:** "En las vistas de Django se filtra siempre por `request.user` (`member=request.user`). En la API DRF, `get_queryset()` verifica el rol: si es socio común, solo devuelve sus propios registros, y la clase de permiso `IsOwnerOrStaff` impide que mediante `/api/memberships/{id}/` o `/api/bookings/{id}/` un usuario consulte objetos ajenos."

### Q5: ¿Cómo funciona la validación del RUT chileno?
> **Respuesta:** "Implementé el algoritmo Módulo 11 en `apps/accounts/validators.py`. Limpia puntos y guiones, calcula la suma ponderada con secuencia 2 a 7 de derecha a izquierda, y compara el residuo contra el dígito verificador ingresado (manejando el caso de 'K' y '0'). Se valida tanto en los formularios como en los modelos."

### Q6: ¿Qué hace el comando `update_memberships`?
> **Respuesta:** "Es un comando por lotes idempotente que busca membresías con estado `ACTIVE` cuya `end_date` ya pasó y las cambia a `EXPIRED`. Está pensado para ejecutarse diariamente vía cron job en el servidor Linux, pero además el sistema reevalúa la fecha en cada intento de acceso o reserva para no depender únicamente del cron."

### Q7: ¿Por qué PostgreSQL y no SQLite en producción?
> **Respuesta:** "SQLite bloquea la base de datos completa al escribir y no soporta alta concurrencia ni bloqueos a nivel de fila (`SELECT FOR UPDATE`). PostgreSQL maneja transacciones concurrentes con control de concurrencia multiversión (MVCC), tipos de datos avanzados como JSONField, índices parciales y constraints condicionales como `UniqueConstraint(condition=...)`."

---

## 4. Mapa de Código de las 4 Funcionalidades Clave

| Funcionalidad | Modelo (`models.py`) | Lógica de Negocio (`services.py`) | Vista Web / API (`views.py` / `api_views.py`) | Template / JS |
|---|---|---|---|---|
| **1. Planes, Pagos y Membresías** | `Plan`, `Membership`, `Payment` (`apps/memberships/`) | `process_subscription_payment`, `renew_membership`, `freeze_membership`, `unfreeze_membership` | `checkout_view`, `renew_view`, `reception_freeze_membership_view` / `MembershipViewSet`, `PaymentViewSet` | `templates/website/plans.html`, `checkout.html`, `renew.html`, `reception_member_detail.html` |
| **2. Control de Acceso QR** | `AccessLog`, `FacilitySetting` (`apps/access/`), `MemberProfile` (`apps/accounts/`) | `validate_and_record_access` (`apps/access/services.py`) | `reception_access_view` / `QRValidationView` (`POST /api/access/validate/`) | `templates/website/reception_access.html` + `static/js/reception.js` |
| **3. Reservas y Lista de Espera** | `ClassType`, `ClassSession`, `Booking` (`apps/classes/`) | `book_class_session`, `cancel_booking`, `admin_cancel_session` (`apps/classes/services.py`) | `booking_calendar_view`, `book_session_action`, `cancel_booking_action` / `BookingViewSet` | `templates/website/booking_calendar.html`, `profile.html` |
| **4. Dashboard de Aforo** | `AccessLog`, `FacilitySetting` (`apps/access/`) | `get_facility_occupancy_data`, `get_facility_occupancy_count` | `dashboard_aforo_view` / `FacilityOccupancyView` (`/api/aforo/`), `FacilityOccupancySummaryView` (`/api/aforo/resumen/`) | `templates/website/dashboard_aforo.html` + `static/js/aforo.js` (Chart.js) |

---

## 5. Plan B ante Contingencias en Vivo

1. **Si la IP pública de AWS Academy cambió al reiniciar el laboratorio:**
   - Edita el archivo `.env` en la EC2: actualiza `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS` con la nueva IP.
   - Reinicia Gunicorn: `sudo systemctl restart gunicorn`.
2. **Si el escáner de cámara no abre en el navegador:**
   - Explica: *"Por políticas de seguridad de los navegadores modernos, la API de cámara web (`MediaDevices.getUserMedia`) exige HTTPS o localhost. En despliegues por IP pública HTTP no encriptada, el navegador bloquea la cámara."*
   - Solución demostrativa: usa inmediatamente el panel **Simulación Manual por Token**, o el selector **"Simular con socio demo"** que rellena automáticamente los tokens de prueba.
3. **Si Gunicorn no responde:**
   - Revisa el log: `sudo journalctl -u gunicorn -n 50 --no-pager`.
   - Verifica permisos de socket: `sudo systemctl status gunicorn`.
   - Comprueba conexión a PostgreSQL: `sudo -u postgres psql -c "\l"`.

