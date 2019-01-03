from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("websocket/timercontrol/<int:object_id>/", consumers.TimerConsumer),
]
