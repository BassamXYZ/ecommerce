"""
Order and payment-state business logic.

Views, the admin and (later) the Stripe webhook should all go through these
functions instead of editing ``Order`` fields directly. That keeps three
invariants in one place:

* prices, totals and stock are always computed on the server, inside a
  transaction that holds row locks;
* stock is reserved when an order is created and returned exactly once if the
  order fails, expires or is refunded before shipping;
* payment and fulfillment statuses only move along allowed transitions, and
  every transition is idempotent (safe to retry, e.g. when a payment
  provider re-sends a webhook).
"""

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Customer, Order, OrderItem, Product

MAX_CART_QUANTITY = 99
CENT = Decimal("0.01")
ZERO = Decimal("0.00")

# Unpaid orders keep their stock reserved for this long.
PENDING_ORDER_TTL = timedelta(minutes=30)


class CheckoutError(Exception):
    """The cart cannot be turned into an order. ``messages`` are user-safe."""

    def __init__(self, messages):
        self.messages = list(dict.fromkeys(messages))
        super().__init__("; ".join(self.messages))


class InvalidTransition(Exception):
    """The requested payment/fulfillment change is not allowed."""


def money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Order creation
# ---------------------------------------------------------------------------


def create_order(*, cart, shipping, user=None):
    """
    Create a pending order from ``cart`` ({product_id: quantity}).

    Nothing from the client is trusted except product ids and quantities:
    unit prices come from the locked product rows, totals are computed here,
    and stock is validated and decremented in the same transaction.

    ``shipping`` holds the validated checkout form data.
    Raises CheckoutError when the cart is no longer purchasable.
    """
    if not cart:
        raise CheckoutError(["Your cart is empty."])

    try:
        wanted = {int(pid): int(qty) for pid, qty in cart.items()}
    except (TypeError, ValueError):
        raise CheckoutError(["Your cart is invalid. Please review it."])

    with transaction.atomic():
        products = {
            p.pk: p
            for p in Product.objects.select_for_update()
            .filter(pk__in=wanted)
            .order_by("pk")
        }

        errors = []
        for pid, qty in wanted.items():
            product = products.get(pid)
            if product is None or not product.is_active:
                errors.append("A product is no longer available. Review your cart.")
            elif qty < 1 or qty > MAX_CART_QUANTITY:
                errors.append("A cart quantity is invalid. Review your cart.")
            elif product.quantity < qty:
                errors.append(
                    f"Only {product.quantity} unit(s) of {product.name} remain. "
                    "Review your cart."
                )
        if errors:
            raise CheckoutError(errors)

        subtotal = sum(
            (money(products[pid].price) * qty for pid, qty in wanted.items()), ZERO
        )
        shipping_cost = ZERO  # Phase 3: shipping rules
        tax_amount = ZERO  # Phase 3: tax rules
        discount_amount = ZERO  # Phase 3: coupon redemption
        total = subtotal + shipping_cost + tax_amount - discount_amount

        customer = _sync_customer(user, shipping) if user else None

        order = Order.objects.create(
            customer=customer,
            client_name=f"{shipping['first_name']} {shipping['last_name']}".strip(),
            client_email=shipping["email"],
            client_country=shipping["country"],
            client_city=shipping["city"],
            client_street=shipping["street"],
            client_postal_code=shipping["postal_code"],
            subtotal=subtotal,
            shipping_cost=shipping_cost,
            tax_amount=tax_amount,
            discount_amount=discount_amount,
            total=total,
            currency="EUR",
            payment_status=Order.PaymentStatus.PENDING,
            fulfillment_status=Order.FulfillmentStatus.PENDING,
        )

        OrderItem.objects.bulk_create(
            OrderItem(
                order=order,
                product=products[pid],
                quantity=qty,
                unit_price=money(products[pid].price),
            )
            for pid, qty in wanted.items()
        )

        for pid, qty in wanted.items():
            products[pid].quantity -= qty
        Product.objects.bulk_update(products.values(), ["quantity", "updated_at"])

    return order


def _sync_customer(user, shipping):
    customer, _ = Customer.objects.get_or_create(
        user=user,
        defaults={
            "first_name": shipping["first_name"],
            "last_name": shipping["last_name"],
            "email": shipping["email"],
            "phone": shipping.get("phone", ""),
        },
    )
    customer.first_name = shipping["first_name"]
    customer.last_name = shipping["last_name"]
    customer.email = shipping["email"]
    customer.phone = shipping.get("phone", "")
    customer.save(
        update_fields=["first_name", "last_name", "email", "phone", "updated_at"]
    )
    return customer


# ---------------------------------------------------------------------------
# Payment and fulfillment transitions
# ---------------------------------------------------------------------------

Pay = Order.PaymentStatus
Ful = Order.FulfillmentStatus


def _lock(order):
    return Order.objects.select_for_update().get(pk=order.pk)


def _restock(order):
    """Return reserved stock. Callers must hold the order lock."""
    for item in order.items.order_by("product_id"):
        Product.objects.filter(pk=item.product_id).update(
            quantity=F("quantity") + item.quantity
        )


def mark_paid(order):
    """pending -> paid. Idempotent. Call this from the payment webhook."""
    with transaction.atomic():
        order = _lock(order)
        if order.payment_status == Pay.PAID:
            return order
        if order.payment_status != Pay.PENDING:
            raise InvalidTransition(
                f"Order #{order.pk} is {order.payment_status}; it cannot be marked paid."
            )
        order.payment_status = Pay.PAID
        order.save(update_fields=["payment_status", "updated_at"])
    return order


def mark_failed(order):
    """
    pending -> failed, cancel fulfillment and release reserved stock.
    Idempotent. Used for payment failures, abandoned checkouts and
    cancelling an unpaid order.
    """
    with transaction.atomic():
        order = _lock(order)
        if order.payment_status == Pay.FAILED:
            return order
        if order.payment_status != Pay.PENDING:
            raise InvalidTransition(
                f"Order #{order.pk} is {order.payment_status}; only unpaid orders can fail. "
                "Refund paid orders instead."
            )
        order.payment_status = Pay.FAILED
        order.fulfillment_status = Ful.CANCELLED
        order.save(update_fields=["payment_status", "fulfillment_status", "updated_at"])
        _restock(order)
    return order


def mark_refunded(order):
    """
    paid -> refunded. If nothing has shipped yet the order is cancelled and
    its stock released. Idempotent.
    """
    with transaction.atomic():
        order = _lock(order)
        if order.payment_status == Pay.REFUNDED:
            return order
        if order.payment_status != Pay.PAID:
            raise InvalidTransition(
                f"Order #{order.pk} is {order.payment_status}; only paid orders can be refunded."
            )
        order.payment_status = Pay.REFUNDED
        fields = ["payment_status", "updated_at"]
        if order.fulfillment_status in (Ful.PENDING, Ful.PROCESSING):
            order.fulfillment_status = Ful.CANCELLED
            fields.append("fulfillment_status")
            _restock(order)
        order.save(update_fields=fields)
    return order


def _advance(order, target, allowed_from):
    with transaction.atomic():
        order = _lock(order)
        if order.fulfillment_status == target:
            return order
        if order.payment_status != Pay.PAID:
            raise InvalidTransition(
                f"Order #{order.pk} is not paid; it cannot be {target}."
            )
        if order.fulfillment_status not in allowed_from:
            raise InvalidTransition(
                f"Order #{order.pk} is {order.fulfillment_status}; it cannot become {target}."
            )
        order.fulfillment_status = target
        order.save(update_fields=["fulfillment_status", "updated_at"])
    return order


def mark_processing(order):
    return _advance(order, Ful.PROCESSING, {Ful.PENDING})


def mark_shipped(order):
    return _advance(order, Ful.SHIPPED, {Ful.PENDING, Ful.PROCESSING})


def mark_delivered(order):
    return _advance(order, Ful.DELIVERED, {Ful.SHIPPED})


def expire_stale_orders(max_age=PENDING_ORDER_TTL, now=None):
    """Fail unpaid orders older than ``max_age`` and release their stock."""
    cutoff = (now or timezone.now()) - max_age
    stale = Order.objects.filter(
        payment_status=Pay.PENDING, created_at__lt=cutoff
    ).values_list("pk", flat=True)
    expired = 0
    for pk in list(stale):
        try:
            order = Order.objects.get(pk=pk)
            mark_failed(order)
            expired += 1
        except (InvalidTransition, Order.DoesNotExist):
            continue  # paid or removed concurrently
    return expired
