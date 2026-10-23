from django.urls import path
from django.conf import settings
from django.conf.urls.static import static


from .views import main, payment, dashboard

urlpatterns = [
    path("healthz/", main.healthz, name="healthz"),
    path("", main.index, name="index"),
    path("search/", main.search, name="search"),
    path("category/<str:category>", main.category, name="category"),
    path("product/<int:product_id>/", main.product_detail, name="product_detail"),
    path("product/<str:category>/<str:product>", main.product, name="product"),
    path("cart/", payment.cart, name="cart"),
    path("cart/add/<int:product_id>/", payment.add_to_cart, name="add_to_cart"),
    path("cart/update/<int:product_id>/", payment.update_cart_item, name="update_cart_item"),
    path("cart/remove/<int:product_id>/", payment.remove_cart_item, name="remove_cart_item"),
    path("checkout/", payment.checkout, name="checkout"),
    path("orders/<int:order_id>/confirmation/", payment.order_confirmation, name="order_confirmation"),
    path("orders/", dashboard.orders, name="orders"),
    path("orders/<int:order_id>/ship/", dashboard.ship_order, name="ship_order"),
    path("analytics/", dashboard.analytics, name="analytics"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)

