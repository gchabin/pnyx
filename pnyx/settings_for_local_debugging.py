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

# SECRET items (must *NEVER* be deployed to any public repository)
SECRET_KEY = '' # SECURITY WARNING: keep the secret key used in production secret!
EMAIL_HOST_PASSWORD = ''
RECAPTCHA_PRIVATE_KEY = ''
REGISTRATION_RECAPTCHA_PRIVATE_KEY = ''

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

TEMPLATE_DEBUG = True

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)

# ALLOWED_HOSTS = ['vmbichler25.informatik.tu-muenchen.de','pnyx.dss.in.tum.de']

# SSL use only
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# ReCaptcha settings (for anything but user registration)
RECAPTCHA_PUBLIC_KEY = '6Lc5hggTAAAAAEzzqZZNDjAPTD-D6sQVeM1zgDp8'
RECAPTCHA_USE_SSL = True
NOCAPTCHA = True
# ReCaptcha custom settings (for user registration)
REGISTRATION_RECAPTCHA_PUBLIC_KEY = '6Lc5hggTAAAAAEzzqZZNDjAPTD-D6sQVeM1zgDp8'

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
    'easy_timezones_custom',
    'formtools', #for form wizard
    'kronos',
    'captcha',
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    #'easy_timezones.middleware.EasyTimezoneMiddleware',
    'easy_timezones_custom.middleware.TimezoneMiddleware',
)

ROOT_URLCONF = 'pnyx.urls'

WSGI_APPLICATION = 'pnyx.wsgi.application'

#Email settings
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = "587"
EMAIL_HOST_USER = 'team.pnyx@gmail.com'
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
TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True
#IP geolocalisation
GEOIP_DATABASE = os.path.join(BASE_DIR, "GeoLiteCity.dat")

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/
STATIC_URL = '/static/'

MEDIA_URL = '/media/'
STATIC_ROOT = os.path.join(BASE_DIR, "static", "static-only")
MEDIA_ROOT = os.path.join(BASE_DIR, "static", "media ")

#Performance optimizations
CONN_MAX_AGE = 600
TEMPLATE_LOADERS = ('django.template.loaders.filesystem.Loader',
 'django.template.loaders.app_directories.Loader')

#Login URL for redirection
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
