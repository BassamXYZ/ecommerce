from django.contrib import admin
from django.urls import include, path
from django.contrib.auth.models import User

urlpatterns = [
    path("", include("app.urls")),
    path('admin/', admin.site.urls)
]