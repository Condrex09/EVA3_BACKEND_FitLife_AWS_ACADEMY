"""
Django settings for FitLife project.
Evaluación 3 - Desarrollo Backend - INACAP
Estudiante: Benjamin Gomez - Sección: AP-N4-C1
"""

from pathlib import Path
from datetime import timedelta
import os
from decouple import config, Csv
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
SECRET_KEY = config('SECRET_KEY', default='django-insecure-fitlife-development-secret-key-2026')

DEBUG = config('DEBUG', default=False, cast=bool)

# Configuración de Hosts y Seguridad (según Receta AWS INACAP para DRF)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*', cast=Csv())

# Verificaciones de seguridad para producción
if not DEBUG and (not ALLOWED_HOSTS or ALLOWED_HOSTS == [''] or ALLOWED_HOSTS == []):
    ALLOWED_HOSTS = ['*']

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:8000,http://127.0.0.1:8000',
    cast=Csv()
)

SHOW_DEMO_CREDENTIALS = config('SHOW_DEMO_CREDENTIALS', default=True, cast=bool)

# Application definition
INSTALLED_APPS = [
    # Django Core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party Apps
    'rest_framework',
    'rest_framework_simplejwt',
    'django_filters',

    # Local Apps
    'apps.accounts.apps.AccountsConfig',
    'apps.memberships.apps.MembershipsConfig',
    'apps.access.apps.AccessConfig',
    'apps.classes.apps.ClassesConfig',
    'apps.website.apps.WebsiteConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'apps.website.middleware.DynamicCSRFTrustedOriginMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'apps.website.middleware.AdminAccessRestrictionMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.website.middleware.NotFoundRedirectMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.website.context_processors.site_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database Configuration (PostgreSQL por defecto según requerimiento de la evaluación)
DB_ENGINE = config('DB_ENGINE', default='django.db.backends.postgresql')
DB_NAME = config('DB_NAME', default='fitlife_db')
DB_USER = config('DB_USER', default='fitlife_user')
DB_PASSWORD = config('DB_PASSWORD', default='fitlife_secure_password_2026')
DB_HOST = config('DB_HOST', default='localhost')
DB_PORT = config('DB_PORT', default='5432')

if 'sqlite' in DB_ENGINE.lower():
    if not DEBUG:
        raise ImproperlyConfigured("FitLife requiere PostgreSQL en producción (SQLite no permitido con DEBUG=False).")
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / f"{DB_NAME}.sqlite3",
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': DB_NAME,
            'USER': DB_USER,
            'PASSWORD': DB_PASSWORD,
            'HOST': DB_HOST,
            'PORT': DB_PORT,
            'CONN_MAX_AGE': 60,
        }
    }

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Authentication Backends (soporte para login con usuario o correo indiferente)
AUTHENTICATION_BACKENDS = [
    'apps.accounts.backends.EmailOrUsernameModelBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 6},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Session and Auth Cookies (Configuración de Seguridad - Tarea 4)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
# CSRF_COOKIE_HTTPONLY en False para que el JS frontend pueda leer el csrftoken para fetch
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # 7 days
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/mi-cuenta/'
LOGOUT_REDIRECT_URL = '/'

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 15,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '120/min',
        'user': '600/min',
        'qr_validation': '120/min',
    }
}

# Simple JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=2),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
}
