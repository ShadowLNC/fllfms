import os

import django
from django.core.wsgi import get_wsgi_application
from channels.routing import get_default_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                      'fllfms.djangoproject.settings')

# get_wsgi_application also calls django.setup, albeit with set_prefix=False.
django.setup()
wsgi = get_wsgi_application()
asgi = get_default_application()
