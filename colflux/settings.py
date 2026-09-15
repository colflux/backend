import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-secret-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0").split(",")

# URL pública del frontend React (colflux/frontend) — a donde apunta este
# backend cuando redirige/enlaza hacia la app, ya que el backend dejó de
# servir UI propia (ver retiro de docs/pages).
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# Versión del backend, mostrada en la página raíz ("/") junto al enlace al
# frontend. Se bumpea a mano en cada release, igual que el VERSION del
# prototipo en docs/assets/js/layout.js.
BACKEND_VERSION = "1.1.0"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "app",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "colflux.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "colflux.wsgi.application"

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL no está seteada. Este proyecto usa Postgres vía Docker "
        "(ver docker-compose.yml) — no hay fallback a sqlite."
    )

from urllib.parse import unquote, urlparse

db = urlparse(DATABASE_URL)
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": db.path.lstrip("/"),
        "USER": unquote(db.username) if db.username else db.username,
        "PASSWORD": unquote(db.password) if db.password else db.password,
        "HOST": db.hostname,
        "PORT": db.port or 5432,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = True  # el prototipo en docs consume esta API desde otro origen

# ── DRF ───────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    # Solo limita el scope "login" (fuerza bruta de contraseña); el resto de la
    # API sigue sin throttling global, consistente con AllowAny en DataPortalModelViewSet.
    "DEFAULT_THROTTLE_RATES": {
        "login": "5/min",
    },
}
