from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ..forms import CheckoutForm
from ..models import Category, Customer, Order, OrderItem, Product

CART_SESSION_KEY = "cart"
GUEST_ORDERS_SESSION_KEY = "guest_order_ids"
MAX_CART_QUANTITY = 99


def _get_session_cart(request):
    """Return a sanitized {product_id: quantity} cart from the session."""
    raw_cart = request.session.get(CART_SESSION_KEY, {})
    if not isinstance(raw_cart, dict):
        raw_cart = {}
    cart = {}
    for raw_id, raw_quantity in raw_cart.items():
        try:
            product_id = str(int(raw_id))
            quantity = int(raw_quantity)
        except (TypeError, ValueError, OverflowError):
            continue
        if quantity > 0 and quantity <= MAX_CART_QUANTITY:
            cart[product_id] = quantity
    if cart != raw_cart:
        request.session[CART_SESSION_KEY] = cart
    return cart


def _build_cart(request):
    """Resolve session lines against current products and current stock."""
    cart = _get_session_cart(request)
    ids = [int(product_id) for product_id in cart]
    products = Product.objects.filter(pk__in=ids).select_related("category")
    product_by_id = {str(product.pk): product for product in products}
    lines = []
    issues = []
    changed = False

    for product_id, quantity in list(cart.items()):
        product = product_by_id.get(product_id)
        if product is None or not product.is_active:
            cart.pop(product_id, None)
            changed = True
            issues.append("A product in your cart is no longer available and was removed.")
            continue
        available = product.quantity
        line_issues = []
        if available <= 0:
            line_issues.append("This product is out of stock.")
        elif quantity > available:
            line_issues.append(f"Only {available} unit(s) are currently available.")
        lines.append({
            "product": product,
            "quantity": quantity,
            "line_total": product.price * quantity,
            "available_quantity": available,
            "issues": line_issues,
        })
        issues.extend(line_issues)

    if changed:
        request.session[CART_SESSION_KEY] = cart
        request.session.modified = True
    total = sum((line["line_total"] for line in lines), Decimal("0.00"))
    return lines, total, issues


def cart(request):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    categories = Category.objects.all()
    cart_items, cart_total, cart_issues = _build_cart(request)
    return render(request, "cart.html", {
        "categories": categories,
        "cart_items": cart_items,
        "cart_total": cart_total,
        "cart_issues": cart_issues,
        "cart_is_empty": not cart_items,
        "cart_has_issues": bool(cart_issues),
    })


@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    try:
        quantity = int(request.POST.get("quantity", "1"))
    except (TypeError, ValueError):
        messages.error(request, "Enter a valid quantity.")
        return redirect("product", category=product.category.name, product=product.name)

    if quantity < 1 or quantity > MAX_CART_QUANTITY:
        messages.error(request, f"Quantity must be between 1 and {MAX_CART_QUANTITY}.")
    elif product.quantity < 1:
        messages.error(request, "This product is out of stock.")
    elif quantity > product.quantity:
        messages.error(request, f"Only {product.quantity} unit(s) are currently available.")
    else:
        cart = _get_session_cart(request)
        key = str(product.pk)
        new_quantity = cart.get(key, 0) + quantity
        if new_quantity > product.quantity:
            messages.error(request, f"Your cart cannot contain more than {product.quantity} unit(s) of this product.")
        elif new_quantity > MAX_CART_QUANTITY:
            messages.error(request, f"A maximum of {MAX_CART_QUANTITY} units per product is allowed.")
        else:
            cart[key] = new_quantity
            request.session[CART_SESSION_KEY] = cart
            request.session.modified = True
            messages.success(request, f"Added {product.name} to your cart.")
    return redirect("product", category=product.category.name, product=product.name)


@require_POST
def update_cart_item(request, product_id):
    cart = _get_session_cart(request)
    key = str(product_id)
    if key not in cart:
        messages.error(request, "That item is no longer in your cart.")
        return redirect("cart")
    try:
        quantity = int(request.POST.get("quantity", ""))
    except (TypeError, ValueError):
        messages.error(request, "Enter a valid quantity.")
        return redirect("cart")
    if quantity < 1 or quantity > MAX_CART_QUANTITY:
        messages.error(request, f"Quantity must be between 1 and {MAX_CART_QUANTITY}.")
        return redirect("cart")
    product = Product.objects.filter(pk=product_id, is_active=True).first()
    if product is None:
        cart.pop(key, None)
        request.session[CART_SESSION_KEY] = cart
        request.session.modified = True
        messages.warning(request, "That product is no longer available and was removed.")
    elif quantity > product.quantity:
        messages.error(request, f"Only {product.quantity} unit(s) are currently available.")
    else:
        cart[key] = quantity
        request.session[CART_SESSION_KEY] = cart
        request.session.modified = True
        messages.success(request, "Cart updated.")
    return redirect("cart")


@require_POST
def remove_cart_item(request, product_id):
    cart = _get_session_cart(request)
    cart.pop(str(product_id), None)
    request.session[CART_SESSION_KEY] = cart
    request.session.modified = True
    messages.success(request, "Item removed from your cart.")
    return redirect("cart")


def checkout(request):
    cart_items, cart_total, cart_issues = _build_cart(request)
    if not cart_items:
        messages.info(request, "Your cart is empty. Add a product before checking out.")
        return redirect("cart")
    if cart_issues:
        for issue in dict.fromkeys(cart_issues):
            messages.warning(request, issue)
        return redirect("cart")

    if request.method == "GET":
        initial = {}
        if request.user.is_authenticated:
            initial["email"] = request.user.email
            customer = Customer.objects.filter(user=request.user).first()
            if customer:
                initial.update(first_name=customer.first_name, last_name=customer.last_name, phone=customer.phone)
        return render(request, "checkout.html", {
            "categories": Category.objects.all(),
            "form": CheckoutForm(initial=initial),
            "cart_items": cart_items,
            "cart_total": cart_total,
        })
    if request.method != "POST":
        return HttpResponseNotAllowed(["GET", "POST"])

    form = CheckoutForm(request.POST)
    if not form.is_valid():
        return render(request, "checkout.html", {
            "categories": Category.objects.all(),
            "form": form,
            "cart_items": cart_items,
            "cart_total": cart_total,
        }, status=400)

    cleaned = form.cleaned_data
    cart = _get_session_cart(request)
    order = None
    inventory_errors = []

    # Lock products and validate stock again in the same transaction that creates
    # the order and decrements inventory. This prevents ordinary concurrent
    # checkouts from selling the same final unit on databases supporting row locks.
    with transaction.atomic():
        ids = [int(product_id) for product_id in cart]
        locked_products = Product.objects.select_for_update().filter(pk__in=ids).order_by("pk")
        product_by_id = {str(product.pk): product for product in locked_products}
        for product_id, quantity in cart.items():
            product = product_by_id.get(product_id)
            if product is None or not product.is_active:
                inventory_errors.append("A product is no longer available. Review your cart.")
            elif quantity < 1 or quantity > MAX_CART_QUANTITY:
                inventory_errors.append("A cart quantity is invalid. Review your cart.")
            elif product.quantity < quantity:
                inventory_errors.append(f"Only {product.quantity} unit(s) of {product.name} remain. Review your cart.")

        if not inventory_errors:
            subtotal = sum(
                (product_by_id[product_id].price * quantity for product_id, quantity in cart.items()),
                Decimal("0.00"),
            )
            customer = None
            if request.user.is_authenticated:
                customer, _ = Customer.objects.get_or_create(
                    user=request.user,
                    defaults={
                        "first_name": cleaned["first_name"],
                        "last_name": cleaned["last_name"],
                        "email": cleaned["email"],
                        "phone": cleaned["phone"],
                    },
                )
                # Keep the profile current, but order snapshots below remain stable.
                customer.first_name = cleaned["first_name"]
                customer.last_name = cleaned["last_name"]
                customer.email = cleaned["email"]
                customer.phone = cleaned["phone"]
                customer.save(update_fields=["first_name", "last_name", "email", "phone", "updated_at"])

            order = Order.objects.create(
                customer=customer,
                client_name=f"{cleaned['first_name']} {cleaned['last_name']}".strip(),
                client_email=cleaned["email"],
                client_country=cleaned["country"],
                client_city=cleaned["city"],
                client_street=cleaned["street"],
                client_postal_code=cleaned["postal_code"],
                subtotal=subtotal,
                total=subtotal,
                currency="EUR",
                payment_status=Order.PaymentStatus.PENDING,
                fulfillment_status=Order.FulfillmentStatus.PENDING,
            )
            for product_id, quantity in cart.items():
                product = product_by_id[product_id]
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    unit_price=product.price,
                )
                product.quantity -= quantity
                product.save(update_fields=["quantity", "updated_at"])

    if inventory_errors:
        for issue in dict.fromkeys(inventory_errors):
            messages.error(request, issue)
        return redirect("cart")

    # A guest may revisit the confirmation only from the same session. Authenticated
    # customers are authorized through the Customer -> User relationship.
    if not request.user.is_authenticated:
        guest_order_ids = request.session.get(GUEST_ORDERS_SESSION_KEY, [])
        guest_order_ids = [int(value) for value in guest_order_ids if str(value).isdigit()]
        guest_order_ids.append(order.pk)
        request.session[GUEST_ORDERS_SESSION_KEY] = guest_order_ids[-20:]
    request.session.pop(CART_SESSION_KEY, None)
    request.session.modified = True
    messages.success(request, f"Order #{order.pk} was created. Payment is pending.")
    return redirect("order_confirmation", order_id=order.pk)


def order_confirmation(request, order_id):
    order = get_object_or_404(Order.objects.select_related("customer", "customer__user").prefetch_related("items__product"), pk=order_id)
    is_owner = (
        request.user.is_authenticated
        and order.customer_id is not None
        and order.customer.user_id == request.user.pk
    )
    guest_order_ids = request.session.get(GUEST_ORDERS_SESSION_KEY, [])
    is_guest_session_owner = (
        not request.user.is_authenticated
        and order.customer_id is None
        and str(order.pk) in {str(value) for value in guest_order_ids}
    )
    if not (is_owner or is_guest_session_owner):
        raise Http404
    return render(request, "order_confirmation.html", {
        "categories": Category.objects.all(),
        "order": order,
        "order_items": order.items.all(),
    })
