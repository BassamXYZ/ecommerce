from django.urls import path
from django.conf import settings
from django.conf.urls.static import static


from views import main, payment, dashboard

urlpatterns = [
    path("", main.index, name="index"),
    path("search/", main.search, name="search"),
    path("category/<str:category>", main.category, name="category"),
    path("product/<str:category>/<str:product>", main.product, name="product"),
    path("cart/", payment.cart, name="cart"),
    path("checkout/", payment.checkout, name="checkout"),
    path("orders/", dashboard.orders, name="dashboard"),
    path("analytics/", dashboard.analytics, name="analytics"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
