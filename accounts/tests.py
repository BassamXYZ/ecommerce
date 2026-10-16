import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.core import mail

User = get_user_model()


class AuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.email = "customer@example.com"
        cls.password = "A-strong-test-password-482!"
        cls.user = User.objects.create_user(
            email=cls.email,
            password=cls.password,
        )

    def test_login_with_email_and_password(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": self.email,
                "password": self.password,
            },
        )

        self.assertRedirects(
            response,
            reverse("index"),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            self.client.session.get("_auth_user_id"),
            str(self.user.pk),
        )

    def test_invalid_password_does_not_log_in(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": self.email,
                "password": "incorrect-password",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_post(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("accounts:logout"))

        self.assertEqual(response.status_code, 405)

    def test_logout_clears_session(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("accounts:logout"))

        self.assertRedirects(
            response,
            reverse("index"),
            fetch_redirect_response=False,
        )
        self.assertNotIn("_auth_user_id", self.client.session)


class PasswordResetFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.email = "reset-customer@example.com"
        cls.old_password = "Initial-password-483!"
        cls.user = User.objects.create_user(
            email=cls.email,
            password=cls.old_password,
        )

    def test_request_sends_reset_email(self):
        response = self.client.post(
            reverse("accounts:password_reset"),
            {"email": self.email},
        )

        self.assertRedirects(
            response,
            reverse("accounts:password_reset_done"),
            fetch_redirect_response=False,
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            self.email,
            mail.outbox[0].body,
        )
        self.assertIn(
            "/accounts/password-reset/",
            mail.outbox[0].body,
        )

    def test_unknown_email_does_not_disclose_account_existence(self):
        response = self.client.post(
            reverse("accounts:password_reset"),
            {"email": "not-registered@example.com"},
        )

        self.assertRedirects(
            response,
            reverse("accounts:password_reset_done"),
            fetch_redirect_response=False,
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_link_changes_password(self):
        self.client.post(
            reverse("accounts:password_reset"),
            {"email": self.email},
        )

        self.assertEqual(len(mail.outbox), 1)

        match = re.search(
            r"http://testserver/accounts/password-reset/"
            r"(?P<uidb64>[^/\s]+)/(?P<token>[^/\s]+)",
            mail.outbox[0].body,
        )
        self.assertIsNotNone(match)

        reset_url = reverse(
            "accounts:password_reset_confirm",
            kwargs=match.groupdict(),
        )

        # Opening the emailed URL validates the token and redirects
        # to Django's protected password-setting URL.
        response = self.client.get(reset_url)
        self.assertEqual(response.status_code, 302)

        new_password = "New-and-strong-password-927!"

        response = self.client.post(
            response["Location"],
            {
                "new_password1": new_password,
                "new_password2": new_password,
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:password_reset_complete"),
            fetch_redirect_response=False,
        )

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertFalse(self.user.check_password(self.old_password))
