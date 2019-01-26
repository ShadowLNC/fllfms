from django.urls import path

from . import views, consumers

urlpatterns = [
    # General pages.
    path("", views.schedule_basic, name='schedule_basic'),
    path("rankings/<int:tournament>/", views.rankings, name='rankings'),
]

websocket_urlpatterns = [
    path("websocket/timercontrol/<path:object_id>/", consumers.TimerConsumer),
]
