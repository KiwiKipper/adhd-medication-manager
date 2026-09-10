from django.urls import path

from . import views

urlpatterns = [
    path("health", views.health, name="health"),
    path("timeline", views.timeline, name="timeline"),
    path("adherence", views.adherence, name="adherence"),
]
