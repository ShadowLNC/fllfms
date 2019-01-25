"""
Django settings for djangoproject project.

Generated by 'django-admin startproject' using Django 2.2.dev20181015211541.

For more information on this file, see
https://docs.djangoproject.com/en/dev/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/dev/ref/settings/
"""

import os
from tzlocal import get_localzone
from django.core.management.utils import get_random_secret_key

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

FLLFMS = {
    'SCORESHEET': 'fllfms.scoresheets.intoorbit2018',
    'EVENT_NAME': "My FLL Event",

    # ########### WARNING ########### #
    # ONCE YOU HAVE POPULATED YOUR DATABASE
    # IF YOU EDIT THESE VALUES, ONLY ADD, DO NOT REORDER OR REMOVE ANY
    # DOING SO WILL ALTER THE EXISTING ENUMERATED VALUES
    # BUT IT WILL NOT UPDATE THE DATABASE, LEADING TO INVALID DATA.
    # Alternatively, manually specify the choice numbers, and eliminate the
    # enumeration altogether. e.g. [(1, "playoff"), (3, "qualification")]

    # Table pairs, named after FRC fields.
    'FIELDS': list(enumerate([
        "A",
        "B",
        "C",
    ])),

    # Table sides, named after player stations from FRC.
    'STATIONS': list(enumerate([
        "1",
        "2",
    ])),

    # Only keep the tournaments you intend to use at an event. Place them in
    # in reverse order, so the first tournament is at the bottom of the list.
    # This is used to sort them automatically. Names are again inspired by FRC.
    # These should be capitalised as you intend them to appear.
    'TOURNAMENTS': list(enumerate([
        # "Finals",
        "Ranking",
        "Practice",
    ])),
}


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/dev/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# NOTE: The filepath needs to be untracked by .gitignore.
keyfile = os.path.join(BASE_DIR, ".secret_key")
try:
    # Read from the file if it exists.
    with open(keyfile) as f:
        SECRET_KEY = f.read()
except FileNotFoundError:
    # Else generate a key and create the file using that key.
    SECRET_KEY = get_random_secret_key()
    with open(keyfile, 'w') as f:
        f.write(SECRET_KEY)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: wildcards allow websockets from any website, but we don't
#                   know your IP. Besides, you might be using a reverse proxy.
ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'channels',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'fllfms.apps.FLLFMSConfig',
    'reversion',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'reversion.middleware.RevisionMiddleware',
]

ROOT_URLCONF = 'fllfms.djangoproject.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

ASGI_APPLICATION = 'fllfms.djangoproject.routing.application'
WSGI_APPLICATION = 'fllfms.djangoproject.wsgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
        'CONFIG': {},
    },
}

# Database
# https://docs.djangoproject.com/en/dev/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/dev/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = get_localzone().zone

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/dev/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, "static")
