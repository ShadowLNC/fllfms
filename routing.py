from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("websocket/timercontrol/<path:object_id>/", consumers.TimerConsumer),
]
