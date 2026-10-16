from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserManager(BaseUserManager):
    """
    Custom manager for email-based authentication.
    """

    use_in_migrations = True

    @staticmethod
    def normalize_email_address(email):
        if not email:
            raise ValueError("An email address is required.")

        return email.strip().casefold()

    def get_by_natural_key(self, username):
        """
        Normalize the email entered at login so that
        capitalization does not affect account lookup.
        """
        email = self.normalize_email_address(username)

        return self.get(**{self.model.USERNAME_FIELD: email})

    def create_user(self, email, password=None, **extra_fields):
        """
        Create an ordinary user.

        Passwords are hashed using Django's password
        handling mechanisms.
        """
        email = self.normalize_email_address(email)

        user = self.model(
            email=email,
            **extra_fields,
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create a Django superuser.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_superuser=True.")

        if extra_fields.get("is_active") is not True:
            raise ValueError("A superuser must have is_active=True.")

        return self.create_user(
            email=email,
            password=password,
            **extra_fields,
        )


class User(AbstractUser):
    """
    Custom authentication user.

    Email is the unique login identifier.
    Django manages password hashing, sessions, groups,
    permissions, staff status, and superuser status.
    """

    username = None

    email = models.EmailField(
        "email address",
        unique=True,
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().casefold()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.email
