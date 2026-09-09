from django.urls import path
from . import views

urlpatterns = [
    path("medications/", views.medications_view),
    path("my-medication/", views.my_medication_view),
    path("doses/", views.doses_view),
    path("notes/", views.notes_view),
]
