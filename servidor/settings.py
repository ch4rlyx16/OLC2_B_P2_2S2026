"""
Configuración de Django para OxigenScript.

Está recortada a propósito. Un `django-admin startproject` normal trae admin,
sesiones, autenticación y ORM; acá no se usa NADA de eso: el intérprete no
guarda estado entre peticiones, así que no hay base de datos ni usuarios.
Dejar esas apps activadas solo agregaría migraciones que nunca se corren.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Solo para desarrollo local. Si esto se publicara en internet habría que
# generar una llave real y sacarla del código.
SECRET_KEY = 'desarrollo-local-oxigenscript'
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'web',
]

MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
]

ROOT_URLCONF = 'servidor.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.csrf',
            ],
        },
    },
]

WSGI_APPLICATION = 'servidor.wsgi.application'

STATIC_URL = 'static/'

LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Guatemala'
USE_TZ = True
