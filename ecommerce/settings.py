"""
Django settings for the ecommerce project.

The project uses environment variables for secrets and deployment-specific
configuration. A local .env file is loaded when present.
"""

import os
from pathlib import Path
from urllib.parse import urlparse

from botocore.config import Config
from dotenv import load_dotenv
import dj_database_url

# ---------------------------------------------------------------------------
# Paths / environment
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local environment variables from BASE_DIR/.env.
# In production (e.g. Render), real environment variables are supplied by
# the platform and take precedence.
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required.")

DEBUG = env_bool("DEBUG", False)

ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost",
)

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# Render and other reverse proxies terminate HTTPS before forwarding requests
# to Django. This tells Django to trust the forwarded HTTPS header.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "storages",
    "app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ecommerce.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "ecommerce.wsgi.application"
ASGI_APPLICATION = "ecommerce.asgi.application"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

# Render provides DATABASE_URL automatically. For local development, the
# .env.example/.env files use SQLite.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
)

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
    )
}


# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "UTC")

USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Django 5.1 uses STORAGES instead of the older STATICFILES_STORAGE setting.
# Static files stay on WhiteNoise; the "default" (media) storage is switched
# to Neon Object Storage below when it is configured.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}


# ---------------------------------------------------------------------------
# Media files (product images) -> Neon Object Storage
# ---------------------------------------------------------------------------

# Neon Object Storage is S3-compatible, so we use django-storages' S3 backend.
# Product images live in a *public_read* bucket: anyone can read them, only
# holders of the credential below can write.
#
# If these variables are not all set (e.g. quick local development), media
# files fall back to the local ./media folder.

AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "")
AWS_ENDPOINT_URL_S3 = os.getenv("AWS_ENDPOINT_URL_S3", "")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "")

USE_NEON_STORAGE = all(
    [
        AWS_STORAGE_BUCKET_NAME,
        AWS_ENDPOINT_URL_S3,
        AWS_ACCESS_KEY_ID,
        AWS_SECRET_ACCESS_KEY,
        AWS_REGION,
    ]
)

if USE_NEON_STORAGE:
    # Objects in a public_read bucket are served at:
    #   https://<branch-endpoint-host>/<bucket>/<object-key>
    _neon_host = urlparse(AWS_ENDPOINT_URL_S3).netloc

    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "endpoint_url": AWS_ENDPOINT_URL_S3,
            "region_name": AWS_REGION,
            "access_key": AWS_ACCESS_KEY_ID,
            "secret_key": AWS_SECRET_ACCESS_KEY,
            # Neon supports path-style addressing only.
            "addressing_style": "path",
            "signature_version": "s3v4",
            # Neon does not implement PutObjectAcl / PutBucketAcl: access is
            # controlled by the bucket's access level (public_read), so never
            # send an ACL with uploads.
            "default_acl": None,
            # Public bucket -> plain URLs, no signed query strings.
            "querystring_auth": False,
            "custom_domain": f"{_neon_host}/{AWS_STORAGE_BUCKET_NAME}",
            # Never overwrite: a duplicate file name gets a random suffix, so
            # an object's URL never changes content and is safe to cache.
            "file_overwrite": False,
            "object_parameters": {"CacheControl": "public, max-age=31536000"},
            # Only compute checksums when the S3 API requires them. Newer
            # boto3 versions add them by default, which some S3-compatible
            # services reject.
            "client_config": Config(
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        },
    }
else:
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"


# ---------------------------------------------------------------------------
# Project-specific settings
# ---------------------------------------------------------------------------

PAYEER_SHOP_ID = os.getenv("PAYEER_SHOP_ID", "12345")


# ---------------------------------------------------------------------------
# Admin notifications
# ---------------------------------------------------------------------------

ADMIN_NAME = os.getenv("ADMIN_NAME", "Bassam")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")

ADMINS = []
if ADMIN_EMAIL:
    ADMINS = [(ADMIN_NAME, ADMIN_EMAIL)]


# ---------------------------------------------------------------------------
# Default primary key field type
# ---------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
