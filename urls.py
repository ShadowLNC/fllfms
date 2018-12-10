from django.urls import path

from . import views

urlpatterns = [
    # General pages.
    path("", views.schedule_basic, name='schedule_basic'),
    path("rankings/<int:tournament>/", views.rankings, name='rankings'),
]
