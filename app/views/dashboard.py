from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from ..models import Order
from ..permissions import staff_required
from ..services import InvalidTransition, mark_shipped

ORDERS_PER_PAGE = 20


@staff_required
@require_GET
def orders(request):
    """Paid orders waiting to be shipped, oldest first."""
    to_ship = (
        Order.objects.filter(
            payment_status=Order.PaymentStatus.PAID,
            fulfillment_status__in=[
                Order.FulfillmentStatus.PENDING,
                Order.FulfillmentStatus.PROCESSING,
            ],
        )
        .prefetch_related("items__product")
        .order_by("created_at")[:ORDERS_PER_PAGE]
    )
    return render(request, "orders.html", {"orders": to_ship})


@staff_required
@require_POST
def ship_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    try:
        mark_shipped(order)
    except InvalidTransition as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Order #{order.pk} marked as shipped.")
    return redirect("orders")


@staff_required
@require_GET
def analytics(request):
    return render(request, "analytics.html")
