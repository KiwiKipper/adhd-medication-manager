from django.urls import path
from . import views

"""
GET  /auth/csrf/       set the CSRF cookie (call once before the first POST)
POST /auth/register/   create an account + start a session
POST /auth/login/      authenticate + start a session
POST /auth/logout/     end the session
GET    /auth/me/       the signed-in user, or 401 if not signed in
DELETE /auth/me/       delete the signed-in user's account (requires "password" in the body)
"""

urlpatterns = [
    path("csrf/", views.csrf_view),
    path("register/", views.register_view),
    path("login/", views.login_view),
    path("logout/", views.logout_view),
    path("me/", views.me_view),
]
