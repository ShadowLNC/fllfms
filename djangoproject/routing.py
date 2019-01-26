from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

import fllfms.urls

application = ProtocolTypeRouter({
    # http -> Django views is automatically added.
    'websocket': AllowedHostsOriginValidator(AuthMiddlewareStack(
        URLRouter(fllfms.urls.websocket_urlpatterns)))
})
