from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()


class RegistrationForm(UserCreationForm):
    """
    Registration form for the custom email-based User model.
    """

    phone = forms.CharField(
        max_length=30,
        required=False,
        strip=True,
    )

    class Meta:
        model = User
        fields = (
            "email",
            "first_name",
            "last_name",
        )

        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "autocomplete": "email",
                    "placeholder": "you@example.com",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "autocomplete": "given-name",
                    "placeholder": "First name",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "autocomplete": "family-name",
                    "placeholder": "Last name",
                }
            ),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().casefold()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email address already exists."
            )

        return email

    def save(self, commit=True):
        user = super().save(commit=False)

        user.email = self.cleaned_data["email"]

        if commit:
            user.save()
            self.save_m2m()

        return user
