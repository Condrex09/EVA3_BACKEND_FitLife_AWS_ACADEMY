# Registro de Prompts de Inteligencia Artificial — Proyecto FitLife
**Asignatura:** Desarrollo Backend (EVA 3) — INACAP  
**Estudiante:** Benjamin Gomez  
**Sección:** AP-N4-C1  
**Herramienta de IA utilizada:** Antigravity (Google DeepMind)  
**Fecha:** Noviembre 2026  

---

## Entrada 1 — Inicio y especificación del proyecto completo
- **Fecha:** 08-11-2026
- **Herramienta:** Antigravity (Google DeepMind)
- **Prompt / Consulta:**
  > "Actúa como un desarrollador backend senior en Django. Construye desde cero, completo y funcional, el proyecto FitLife: plataforma de control de asistencia y reserva de clases para un gimnasio. Es una evaluación universitaria (INACAP, asignatura Desarrollo Backend, EVA 3, 100% individual) que se defiende en vivo, así que el código debe ser claro, ordenado y fácil de explicar. No dejes TODOs ni funciones a medias: todo lo descrito aquí debe quedar operativo..." [Ver especificación completa de 14 secciones en `prompt_antigravity_fitlife.md`].
- **Qué se solicitó:**
  1. Estructura modular Django (`accounts`, `memberships`, `access`, `classes`, `website`).
  2. Modelo relacional con AbstractUser personalizado, roles (Admin, Recepción, Socio), perfiles con RUT y QR único.
  3. Capa de servicios (`services.py`) para reglas de negocio (membresías, pagos simulados, validación QR, aforo, reservas con cupos y lista de espera atómica).
  4. Django Admin personalizado con templates sobreescritos, branding FitLife amarillo/negro y métricas en vivo.
  5. API REST con DRF, JWT, filtros y throttling.
  6. Frontend responsivo (HTML5/CSS3/Vanilla JS) inspirado en Smart Fit sin copiar marcas de terceros.
  7. Comando de seed idempotente (`seed_demo`), tests unitarios automatizados y paquete de despliegue EC2 (`deploy/`).
- **Qué resultado entregó:**
  - Plan de arquitectura modular completa.
  - Implementación integral sin dependencias faltantes ni TODOs.
- **Ajustes manuales y supervisión del estudiante:**
  - Verificación del modelo de datos de acuerdo a los requerimientos de la rúbrica de INACAP.
  - Comprobación de los cálculos de aforo y promoción en lista de espera.
  - Validación del footer institucional obligatorio en todas las plantillas y en el Django Admin.

---

## Entrada 2 — Modelos de datos, autenticación y validación de RUT
- **Fecha:** 08-11-2026
- **Herramienta:** Antigravity (Google DeepMind)
- **Prompt / Consulta:**
  > "Genera los modelos para accounts y memberships con AbstractUser, roles ADMIN, RECEPTION, MEMBER, validación de RUT chileno con Módulo 11, y token UUID para el pase QR. En memberships crea Plan, Membership y Payment con restricción de una sola membresía activa o congelada por socio."
- **Qué se solicitó:**
  - `apps/accounts/models.py`: Modelo `User` con roles y email único, `MemberProfile` con RUT único, generador de QR en Data URI Base64.
  - `apps/accounts/validators.py`: Algoritmo de Módulo 11 chileno, limpiador y formateador de RUT.
  - `apps/memberships/models.py`: Modelo `Plan` con precios en CLP, `Membership` con clean() restrictivo y `Payment` con generación de códigos de referencia únicos.
- **Qué resultado entregó:**
  - Modelos relacionales con integridad referencial (`on_delete` apropiado), verbose names en español e índices en campos de consulta frecuente (`qr_token`, `timestamp`, `status`).
- **Ajustes manuales y supervisión del estudiante:**
  - Se probó el algoritmo de RUT con diversos formatos de entrada (con puntos, sin puntos, con dígito K en mayúscula y minúscula).

---

## Entrada 3 — Capa de servicios y reglas de negocio críticas
- **Fecha:** 08-11-2026
- **Herramienta:** Antigravity (Google DeepMind)
- **Prompt / Consulta:**
  > "Implementa los servicios en `services.py` para memberships, access y classes. Asegura transacciones atómicas con `select_for_update()` en reservas para evitar sobrecupo, validación de QR con alternancia Entrada/Salida en una sola consulta optimizada, control de aforo por umbrales y promoción automática del primero en lista de espera al cancelar una reserva con plazo de 2 horas."
- **Qué se solicitó:**
  - `apps/memberships/services.py`: `update_membership_status`, `freeze_membership`, `unfreeze_membership`, `process_subscription_payment` (con tarjeta terminada en 0000 para simular rechazo) y `renew_membership`.
  - `apps/access/services.py`: `validate_and_record_access` (validación de UUID, vigencia, toggle IN/OUT, tope de capacidad), y `get_facility_occupancy_data` (cálculo de personas dentro, porcentaje, distribución horaria).
  - `apps/classes/services.py`: `book_class_session` con bloqueo pesimista y `cancel_booking` con auto-promoción y reordenamiento de lista de espera.
- **Qué resultado entregó:**
  - Funciones de servicio puras, desacopladas de las vistas HTTP, altamente testeables y protegidas ante concurrencia.
- **Ajustes manuales y supervisión del estudiante:**
  - Se verificó que la subconsulta de personas dentro funcionara de manera óptima tanto en PostgreSQL como en entornos de prueba con Max('id') agrupado por socio.

---

## Entrada 4 — Personalización del Django Admin y Métricas en Tiempo Real
- **Fecha:** 08-11-2026
- **Herramienta:** Antigravity (Google DeepMind)
- **Prompt / Consulta:**
  > "Personaliza el Django Admin para cumplir con la rúbrica de INACAP: sobrescribe base_site.html e index.html con paleta FitLife amarillo/negro, logo SVG propio, tarjetas de métricas en vivo en la portada (socios activos, ingresos de hoy en CLP, aforo actual, reservas hoy) y pie de página institucional obligatorio."
- **Qué se solicitó:**
  - `templates/admin/base_site.html` y `templates/admin/index.html`.
  - `static/css/admin_custom.css` con estilos corporativos.
  - Template tag `get_admin_metrics` en `apps/website/templatetags/fitlife_tags.py`.
  - Badges de color en listados de modelos (verde, rojo, celeste, amarillo) y acciones personalizadas (congelar 30 días, marcar vencidas, aprobar pagos, cancelar sesión y notificar, exportar a CSV).
- **Qué resultado entregó:**
  - Panel administrativo profesional, con identidad de marca FitLife y métricas en vivo en la portada.
- **Ajustes manuales y supervisión del estudiante:**
  - Se constató que el footer reglamentario: `Desarrollado por Benjamin Gomez · Sección AP-N4-C1 · INACAP · EVA 3 Desarrollo Backend` se despliega en el pie del Admin y en todas las páginas web.

---

## Entrada 5 — Frontend responsivo, escáner QR de recepción y dashboard de aforo
- **Fecha:** 08-11-2026
- **Herramienta:** Antigravity (Google DeepMind)
- **Prompt / Consulta:**
  > "Construye los templates y el JavaScript para el portal web: portada inspirada en Smart Fit, catálogo de planes en CLP, horario semanal con filtros, portal del socio con pase QR y cancelación de reservas, escáner de recepción con cámara html5-qrcode y simulación por token, y dashboard de aforo con Chart.js y actualización cada 5 segundos sin recargar."
- **Qué se solicitó:**
  - `templates/website/`: `index.html`, `plans.html`, `classes.html`, `facility.html`, `contact.html`, `register.html`, `login.html`, `profile.html`, `checkout.html`, `renew.html`, `booking_calendar.html`, `reception_access.html`, `dashboard_aforo.html`, `reception_members.html`.
  - `static/css/style.css`: Paleta negro (`#111111`), amarillo (`#FFC400`) y grises, diseño mobile-first.
  - `static/js/aforo.js`: Consumo periódico de `/api/aforo/` cada 5s actualizando barra semáforo y gráfico.
  - `static/js/reception.js`: Integración de cámara web y simulador manual con respuesta visual verde/rojo.
- **Qué resultado entregó:**
  - Interfaz responsiva, rápida y moderna, sin dependencias de frameworks pesados (React/Vue).
- **Ajustes manuales y supervisión del estudiante:**
  - Se ajustaron los mensajes y etiquetas al español de Chile y se probó la respuesta visual de accesos permitidos y denegados.

---

## Entrada 6 — Pruebas unitarias, datos de demostración y paquete de despliegue en AWS EC2
- **Fecha:** 08-11-2026
- **Herramienta:** Antigravity (Google DeepMind)
- **Prompt / Consulta:**
  > "Crea el comando de seed idempotente `seed_demo`, los tests automatizados para las reglas críticas y los archivos de despliegue en `deploy/` (gunicorn.service, nginx.conf, deploy.sh) junto al README detallado para la defensa en vivo en AWS Academy."
- **Qué se solicitó:**
  - `apps/accounts/management/commands/seed_demo.py`: Creación de grupos, superusuario `admin`, recepcionista `recepcion`, 8 socios de prueba (incluyendo activos, vencidos, congelados y en lista de espera), 3 planes y sesiones de clases para 7 días.
  - `tests/test_business_logic.py`: 7 pruebas unitarias de casos de negocio críticos.
  - `deploy/`: Archivos de configuración para Ubuntu en EC2 con proxy Nginx y demonio Gunicorn.
  - `README.md`: Documentación completa, guía paso a paso y recuadro para la IP pública de EC2.
- **Qué resultado entregó:**
  - Ejecución de `python manage.py test tests`: 7 pruebas ejecutadas con resultado **OK**.
  - Ejecución de `python manage.py seed_demo`: Población completa de base de datos exitosa.
  - Ejecución de `python manage.py collectstatic`: 163 archivos estáticos listos para producción.
- **Ajustes manuales y supervisión del estudiante:**
  - Verificación final de todos los requisitos de la evaluación y preparación de la pauta para la defensa en vivo.


---

## Entrada 7 — Corrección de redirección de rutas inexistentes y credenciales demo en login
- **Fecha:** 08-11-2026
- **Herramienta:** Antigravity (Google DeepMind)
- **Prompt / Consulta:**
  > "Estoy probando el proyecto FitLife en local y encontré dos problemas: (1) aparece la página 404 al escribir una URL inexistente (ej. /logn/), debe redirigir automáticamente a /; (2) falta una cuenta de administrador que se pueda usar desde el login. Crea/actualiza la cuenta admin en seed_demo con clave Admin#FitLife2026, autenticación por usuario o correo indistintamente, redirección según rol, tarjeta demo con botón Autocompletar visible bajo SHOW_DEMO_CREDENTIALS, y enlace Panel Admin en el navbar cuando is_staff=True."
- **Qué se solicitó:**
  1. Vista `redirect_to_home` y configuración de `handler404` en `config/urls.py` más catch-all al final de `urlpatterns`.
  2. Endpoint `/api/.*` con respuesta JSON 404 (`{"detail": "No encontrado."}`) para no redirigir llamadas de API a HTML.
  3. Soporte en el login para autenticar por usuario o por correo electrónico indiferente mediante backend personalizado `EmailOrUsernameModelBackend`.
  4. Redirección post-login según rol: Admin a `/admin/`, Recepción a `/recepcion/acceso/`, Socio a `/mi-cuenta/`.
  5. Tarjeta de credenciales demo en `login.html` con botón JS "Autocompletar" condicional a `SHOW_DEMO_CREDENTIALS`.
  6. Enlace "Panel Admin" en el navbar para usuarios con `is_staff=True`.
- **Qué resultado entregó:**
  - Redirección 302 hacia `/` en todas las rutas web inexistentes y 404 JSON en la API.
  - Backend de autenticación dual (usuario/correo) completamente funcional.
  - Tarjeta de autocompletado en `/login/` y enlace de administración en la cabecera.
- **Ajustes manuales y supervisión del estudiante:**
  - (Completar por el estudiante: qué probó, qué corrigió o qué decidió)

---

## Entrada 8 — Auditoría de seguridad, permisos REST, PostgreSQL y preparación para la defensa (EVA 3)
- **Fecha:** 09-11-2026
- **Herramienta:** Antigravity (Google DeepMind)
- **Prompt / Consulta:**
  > "Revisión integral del código según los 5 criterios de la rúbrica oficial de la EVA 3: (1) Permisos estrictos en API REST (Memberships, Payments, Bookings sin PUT/PATCH/DELETE, Aforo restringido a staff y resumen público en /api/aforo/resumen/, restricción unique_current_membership_per_member); (2) Cuenta admin visible con autocompletar; (3) Rol Recepción operativo con permisos reales, acciones de congelar/descongelar y pago manual en ficha de socio; (4) Configuración segura (DEBUG=False por defecto, comprobación de SECRET_KEY y ALLOWED_HOSTS, logout por POST con CSRF, middleware de redirección 404); (5) PostgreSQL como base obligatoria en producción y comando dbinfo; (6) seed_demo idempotente con flags --reset y --reset-passwords; (7) Django Admin con templates change_list y change_form con branding y vista previa QR; (8) Promoción en lista de espera validando membresía activa; (9) Despliegue EC2 pulido con advertencia de contexto seguro para cámara web y selector demo; (10) prompts_ia.md; (11) DEFENSA.md con guion de 8 minutos y preguntas docentes; (12) README actualizado."
- **Qué se solicitó:**
  1. Corrección de matrices de permisos en ViewSets DRF (`get_permissions`) e inmutabilidad de reservas.
  2. Constraint de base de datos `unique_current_membership_per_member` en `Membership.Meta` y migración aplicada.
  3. Asignación de permisos al grupo `Recepcionistas` y nuevas vistas/rutas para congelar, descongelar y registrar pagos manuales.
  4. Comando `python manage.py dbinfo` para auditar la persistencia relacional en PostgreSQL.
  5. Idempotencia y seguridad en `seed_demo` con flags `--reset` (requiere `--force` si `DEBUG=False`) y `--reset-passwords`.
  6. Templates de administración `change_list.html` y `change_form.html` con ayuda contextual por modelo.
  7. Lógica de salto de socios con membresía inactiva durante la promoción automática de listas de espera.
  8. Detección de `isSecureContext` en el escáner QR de recepción y selector de prueba demo para la defensa.
  9. Documentos de estudio y entrega: `DEFENSA.md` y actualización de `README.md`.
- **Qué resultado entregó:**
  - Suite de pruebas ampliada a 20 tests unitarios y de integración (`python manage.py test tests`), todos aprobados exitosamente.
  - Comando `dbinfo` operativo mostrando 25 migraciones aplicadas y conteo de tablas.
  - Documentos `DEFENSA.md` y `README.md` alineados al 100% con la rúbrica de la evaluación.
- **Ajustes manuales y supervisión del estudiante:**
  - (Completar por el estudiante: qué probó, qué corrigió o qué decidió)

---

## Errores detectados y corregidos con ayuda de la IA

1. **Permisos de API REST desprotegidos:** `MembershipViewSet` y `PaymentViewSet` permitían escritura a cualquier usuario autenticado; se blindaron con `IsAdminRole` y `IsReceptionRole`, bloqueando modificaciones indebidas (Error 403).
2. **Manipulación de reservas vía API:** `BookingViewSet` permitía métodos PUT, PATCH y DELETE que eludían el control de cupos y lista de espera; se restringió a solo `['get', 'post', 'head', 'options']` canalizando cancelaciones por el servicio atómico.
3. **Exposición de datos personales en el aforo:** El endpoint `/api/aforo/` exponía nombres y RUTs de socios adentro a cualquier usuario autenticado; se restringió a staff de recepción y se creó `/api/aforo/resumen/` para métricas públicas anonimizadas.
4. **Seed demo destructivo:** Cada ejecución de `seed_demo` borraba todas las sesiones, reservas y accesos; se refactorizó para ser completamente idempotente con `get_or_create` y parámetros de seguridad `--reset` y `--force`.
5. **Grupos de Django sin permisos asignados:** Los grupos creados no tenían permisos en el Admin; se asignaron permisos específicos a `Recepcionistas` (sin permitir borrar planes ni usuarios) y permisos completos a `Administradores`.
6. **Descongelamiento extendía días de más:** `unfreeze_membership` aplicaba `max(1, ...)` extendiendo días innecesariamente en descongelamientos el mismo día; se corrigió a cálculo exacto `max(0, ...)`.
7. **Promoción de socios con membresía vencida en lista de espera:** Se validó que solo socios con membresía vigente sean promovidos a confirmados, cancelando y notificando al socio vencido y pasando al siguiente en cola.
8. **Logout inseguro por GET:** Se transformó el cierre de sesión a petición `POST` protegida con token CSRF para prevenir ataques de falsificación de peticiones.
9. **Desfase de contraseñas de admin demo en base de datos:** Al cambiar la clave demo a `Admin#FitLife2026`, la base de datos conservaba el hash previo; se sincronizó ejecutando `seed_demo --reset-passwords`.
