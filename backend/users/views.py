from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .serializers import RegisterSerializer


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf_view(request) -> Response:
    """Visiting this sets the csrftoken cookie the SPA needs before its first POST."""
    return Response({"detail": "CSRF cookie set"})


@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request) -> Response:
    serializer = RegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = serializer.save()
    login(request, user)

    return Response(
        {"username": user.username, "email": user.email},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request) -> Response:
    identifier = request.data.get("username")
    password = request.data.get("password")

    user = authenticate(request, username=identifier, password=password)

    if user is None and identifier and "@" in identifier:
        matches = User.objects.filter(email__iexact=identifier)
        if matches.count() == 1:
            user = authenticate(
                request, username=matches.first().username, password=password
            )

    if user is None:
        return Response(
            {"error": "Invalid username or password"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    login(request, user)
    return Response({"username": user.username, "email": user.email})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request) -> Response:
    logout(request)
    return Response({"detail": "User logged out"})


@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def me_view(request) -> Response:
    user = request.user

    if request.method == "DELETE":
        # Require the current password so a hijacked session (or a stray
        # click) can't wipe the account without proving who's asking.
        if not user.check_password(request.data.get("password", "")):
            return Response(
                {"error": "Incorrect password"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        logout(request)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    return Response(
        {
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
        }
    )
