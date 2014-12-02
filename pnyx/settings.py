"""
Django settings for pnyx project.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.6/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
TEMPLATE_DIRS = [os.path.join(BASE_DIR, 'templates')]
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.6/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '^l#hcga^%x7ls=5lbz@)5*)ket5*vp)!@kiqqqhzojr1*587ol'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

TEMPLATE_DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'polls',
    'vote',
    'accounts',
    'about',
    'django.contrib.formtools', #for form wizzard
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'pnyx.urls'

WSGI_APPLICATION = 'pnyx.wsgi.application'

#Email settings
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = "587"
EMAIL_HOST_USER = 'pnyx.test@gmail.com'
EMAIL_HOST_PASSWORD = 'pnyx12345'
EMAIL_USE_TLS = True

DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
SERVER_EMAIL = EMAIL_HOST_USER

# Database
# https://docs.djangoproject.com/en/1.6/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# Internationalization
# https://docs.djangoproject.com/en/1.6/topics/i18n/

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Europe/Berlin'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/
STATIC_URL = '/static/'

if DEBUG:
    MEDIA_URL = '/media/'
    STATIC_ROOT = os.path.join(BASE_DIR, "static", "static-only")
    MEDIA_ROOT = os.path.join(BASE_DIR, "static", "media ")


#Login URL for rederiction
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL  = '/polls/'

#LOGGING CONF
if DEBUG:
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format' : "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
                'datefmt' : "%d/%b/%Y %H:%M:%S"
            },
            'simple': {
                'format': '%(levelname)s %(message)s'
            },
        },
        'handlers': {
            'file_all': {
                'level': 'DEBUG',
                'class': 'logging.FileHandler',
                'filename': 'log_all.log',
                'formatter': 'verbose'
            },
            'file_selected': {
                'level': 'DEBUG',
                'class': 'logging.FileHandler',
                'filename': 'log_selected.log',
                'formatter': 'verbose'
            },
        },
        'loggers': {
            'django': {
                'handlers':['file_all'],
                'propagate': True,
                'level':'DEBUG',
            },
            'accounts': {
                'handlers': ['file_all', 'file_selected'],
                'level': 'DEBUG',
            },
            'polls': {
                'handlers': ['file_all','file_selected'],
                'level': 'DEBUG',
            },
            'pnyx': {
                'handlers': ['file_all', 'file_selected'],
                'level': 'DEBUG',
            },
            'vote': {
                'handlers': ['file_all','file_selected'],
                'level': 'DEBUG',
            },
        }
}