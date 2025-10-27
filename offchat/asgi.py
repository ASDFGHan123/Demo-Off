"""
ASGI config for offchat project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
import django
from django.conf import settings

# Setup Django
if not settings.configured:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'offchat.settings')
    django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
import chat.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter(
        chat.routing.websocket_urlpatterns
    ),
})
