from django.contrib import admin
from django.urls import path, include

"""
Specfic URLS will be used for the backend
For each URL, a corresponding view is provided
Return the data (or template) to the frontend as a response
"""

urlpatterns = [
    path('admin/', admin.site.urls),
    path("auth/", include("users.urls")),
    path("api/", include("tracker.urls")),
]
