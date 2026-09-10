"""Tests for the session-auth endpoints under /auth/.

Run from web/backend/ with:

    DB_ENGINE=sqlite py manage.py test

No VMs and no postgres required -- Django builds a throwaway database and
calls the views in-process.
"""

from django.contrib.auth.models import User
from django.test import TestCase


class RegisterTests(TestCase):

    def test_register_creates_user_and_starts_a_session(self):
        response = self.client.post(
            "/auth/register/",
            {"username": "ada", "email": "ada@example.com", "password": "correct-horse-9"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["username"], "ada")
        self.assertTrue(User.objects.filter(username="ada").exists())

        # Registering logs you straight in, so /auth/me/ works without a
        # separate login round-trip.
        self.assertEqual(self.client.get("/auth/me/").status_code, 200)

    def test_password_is_hashed_not_stored_verbatim(self):
        self.client.post(
            "/auth/register/",
            {"username": "ada", "password": "correct-horse-9"},
            content_type="application/json",
        )
        user = User.objects.get(username="ada")
        self.assertNotEqual(user.password, "correct-horse-9")
        self.assertTrue(user.check_password("correct-horse-9"))

    def test_weak_password_is_rejected(self):
        response = self.client.post(
            "/auth/register/",
            {"username": "ada", "password": "123"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json())
        self.assertFalse(User.objects.filter(username="ada").exists())

    def test_duplicate_username_is_rejected(self):
        User.objects.create_user(username="ada", password="correct-horse-9")
        response = self.client.post(
            "/auth/register/",
            {"username": "ada", "password": "another-good-1"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.filter(username="ada").count(), 1)

    def test_duplicate_email_is_rejected_case_insensitively(self):
        User.objects.create_user(
            username="ada", email="ada@example.com", password="correct-horse-9"
        )
        response = self.client.post(
            "/auth/register/",
            {"username": "ada2", "email": "ADA@example.com", "password": "another-good-1"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json())


class LoginTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="ada", email="ada@example.com", password="correct-horse-9"
        )

    def _login(self, identifier, password):
        return self.client.post(
            "/auth/login/",
            {"username": identifier, "password": password},
            content_type="application/json",
        )

    def test_login_with_username(self):
        response = self._login("ada", "correct-horse-9")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "ada")

    def test_login_with_email(self):
        # login_view falls back to an email lookup when the identifier
        # contains an "@" and isn't a username.
        response = self._login("ada@example.com", "correct-horse-9")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "ada")

    def test_login_with_ambiguous_email_is_refused(self):
        # Two accounts sharing an email can't be told apart, so neither is
        # logged in rather than picking one arbitrarily.
        User.objects.create_user(
            username="ada2", email="ada@example.com", password="correct-horse-9"
        )
        response = self._login("ada@example.com", "correct-horse-9")
        self.assertEqual(response.status_code, 401)

    def test_wrong_password_is_401(self):
        response = self._login("ada", "not-the-password")
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.json())

    def test_unknown_user_is_401(self):
        self.assertEqual(self._login("nobody", "correct-horse-9").status_code, 401)


class SessionTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="ada", email="ada@example.com", password="correct-horse-9"
        )

    def test_me_requires_authentication(self):
        self.assertEqual(self.client.get("/auth/me/").status_code, 403)

    def test_logout_requires_authentication(self):
        self.assertEqual(self.client.post("/auth/logout/").status_code, 403)

    def test_me_returns_the_signed_in_user(self):
        self.client.force_login(self.user)
        response = self.client.get("/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "ada")
        self.assertEqual(response.json()["email"], "ada@example.com")

    def test_logout_ends_the_session(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post("/auth/logout/").status_code, 200)
        self.assertEqual(self.client.get("/auth/me/").status_code, 403)

    def test_csrf_endpoint_sets_the_cookie(self):
        response = self.client.get("/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)


class DeleteAccountTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="ada", password="correct-horse-9")
        self.client.force_login(self.user)

    def _delete(self, password):
        return self.client.delete(
            "/auth/me/", {"password": password}, content_type="application/json"
        )

    def test_correct_password_deletes_the_account(self):
        response = self._delete("correct-horse-9")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(User.objects.filter(username="ada").exists())

    def test_wrong_password_keeps_the_account(self):
        response = self._delete("not-the-password")
        self.assertEqual(response.status_code, 401)
        self.assertTrue(User.objects.filter(username="ada").exists())

    def test_missing_password_keeps_the_account(self):
        response = self.client.delete("/auth/me/", content_type="application/json")
        self.assertEqual(response.status_code, 401)
        self.assertTrue(User.objects.filter(username="ada").exists())
