from django.urls import path
from django.conf import settings
from django.conf.urls.static import static


from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("dashboard/", views.orders, name="dashboard"),
    path("cart/", views.cart, name="cart"),
    path("cart/", views.checkout, name="checkout"),
    path("search/", views.search, name="search"),
    path("category/<str:category>", views.category, name="category"),
    path("product/<str:category>/<str:product>", views.product, name="product"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
