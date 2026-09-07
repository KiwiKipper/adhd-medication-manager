from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home") # calls views.py -> home function -> returns httpResponse
]