import os
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import urlparse

# Build paths: BASE_DIR points to project root d:\SDC_backend
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from the project root
load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-secret-key-replace-me')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', '*').split(',') if host.strip()]

# Application definition
INSTALLED_APPS = [
    'django.contrib.staticfiles',
    
    # Third-party applications
    'corsheaders',
    
    # Modular domain applications
    'features.signals',
    'features.deals',
    'features.companydata',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Put CorsMiddleware at the top
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'frontend' / 'dist'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

def build_database_settings(database_url: str, database_name_override: str = ""):
    if database_url.startswith(('mongodb://', 'mongodb+srv://')):
        parsed_url = urlparse(database_url)
        database_name = database_name_override or parsed_url.path.lstrip('/') or 'sdc_backend'
        return {
            'default': {
                'ENGINE': 'django_mongodb_backend',
                'HOST': database_url,
                'NAME': database_name,
            }
        }

    if database_url.startswith('postgres://') or database_url.startswith('postgresql://'):
        parsed_url = urlparse(database_url)
        return {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': parsed_url.path[1:],
                'USER': parsed_url.username,
                'PASSWORD': parsed_url.password,
                'HOST': parsed_url.hostname,
                'PORT': parsed_url.port or '',
            }
        }

    sqlite_db_name = database_url.replace('sqlite:///', '')
    return {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / sqlite_db_name,
        }
    }


def resolve_database_config() -> tuple[str, str]:
    database_url = os.getenv('DATABASE_URL', '').strip()
    if database_url:
        return database_url, ''

    mongodb_uri = os.getenv('MONGODB_URI', '').strip()
    mongo_db_name = os.getenv('MONGO_DB_NAME', '').strip()
    if mongodb_uri and mongo_db_name:
        return mongodb_uri, mongo_db_name

    if mongodb_uri:
        return mongodb_uri, ''

    return 'mongodb://localhost:27017/sdc_backend', ''


# Database configuration with dynamic engine resolver
DATABASE_URL, DATABASE_NAME_OVERRIDE = resolve_database_config()
DATABASES = build_database_settings(DATABASE_URL, DATABASE_NAME_OVERRIDE)

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
# STATICFILES_DIRS = [BASE_DIR / 'frontend' / 'dist']  # Uncomment when frontend is built

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django_mongodb_backend.fields.ObjectIdAutoField'

# CORS Configurations
CORS_ALLOW_ALL_ORIGINS = True  # Set to False in production and specify CORS_ALLOWED_ORIGINS
CORS_ALLOW_CREDENTIALS = True

# Media files (for dynamically generated documents)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
