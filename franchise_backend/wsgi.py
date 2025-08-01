"""
WSGI config for franchise_backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/wsgi/
"""



import os

# Read ENV_CLASSIFICATION environment variable to determine environment
environment = os.getenv('ENV_CLASSIFICATION', 'local')
print(f"Initializing WSGI environment: {environment}")

# Dynamically set settings module based on environment
if environment == 'prod':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'franchise_backend.settings-prod')
elif environment == 'test':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'franchise_backend.settings-test')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'franchise_backend.settings')

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()