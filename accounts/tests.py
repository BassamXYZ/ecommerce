from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

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
