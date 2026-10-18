from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render

from app.models import Customer
from .forms import RegistrationForm

User = get_user_model()


def register(request):
    """
    Register a new authentication user and customer profile.

    Both records are created atomically.
    """

    if request.user.is_authenticated:
        return redirect("index")

    if request.method == "POST":
        form = RegistrationForm(request.POST)

        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()

                    Customer.objects.create(
                        user=user,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        email=user.email,
                        phone=form.cleaned_data["phone"],
                    )

            except IntegrityError:
                # The transaction has already rolled back.
                form.add_error(
                    "email",
                    "We couldn't create an account with this email. "
                    "Please check the address and try again.",
                )
            else:
                messages.success(
                    request,
                    "Your account has been created. You can now log in.",
                )

                return redirect("accounts:login")

    else:
        form = RegistrationForm()

    return render(
        request,
        "accounts/register.html",
        {"form": form},
    )
