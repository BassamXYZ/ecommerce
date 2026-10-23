from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.db import connection
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render

from ..models import Category, Product


PRODUCTS_PER_PAGE = 24
FEATURED_PRODUCTS_PER_CATEGORY = 8


def _is_htmx_request(request):
    """Return True for an HTMX request so views can respond with HTML fragments."""
    return request.headers.get("HX-Request", "").lower() == "true"


def _active_products():
    return Product.objects.filter(is_active=True).select_related("category")


def index(request):
    featured_products = (
        Product.objects.filter(is_active=True)
        .select_related("category")
        .order_by("name")[:FEATURED_PRODUCTS_PER_CATEGORY]
    )
    categories = (
        Category.objects.filter(products__is_active=True)
        .distinct()
        .prefetch_related(
            Prefetch(
                "products",
                queryset=featured_products,
                to_attr="featured_products",
            )
        )
    )
    return render(request, "index.html", {"categories": categories})


def search(request):
    query = request.GET.get("q", "").strip()
    products = _active_products()

    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )
    else:
        # Do not return the entire catalogue for an empty search request.
        products = products.none()

    context = {
        "products": products,
        "q": query,
    }

    if _is_htmx_request(request):
        return render(request, "includes/product_grid.html", context)

    return render(request, "search.html", context)


def category(request, category):
    category_obj = get_object_or_404(Category, name=category)

    sort = request.GET.get("sort", "name")
    sort_fields = {
        "name": ("name", "pk"),
        "price_asc": ("price", "name", "pk"),
        "price_desc": ("-price", "name", "pk"),
    }
    if sort not in sort_fields:
        sort = "name"

    in_stock = request.GET.get("in_stock") in {"1", "true", "on"}
    product_list = category_obj.products.filter(is_active=True).select_related("category")
    if in_stock:
        product_list = product_list.filter(quantity__gt=0)
    product_list = product_list.order_by(*sort_fields[sort])

    page_obj = Paginator(product_list, PRODUCTS_PER_PAGE).get_page(
        request.GET.get("page", 1)
    )

    context = {
        "category": category_obj,
        "name": category_obj.name,  # Retained for compatibility with older templates.
        "products": page_obj.object_list,
        "page_obj": page_obj,
        "sort": sort,
        "in_stock": in_stock,
        "empty_message": "There are no active products matching these filters.",
    }

    if _is_htmx_request(request):
        return render(request, "includes/category_results.html", context)

    return render(request, "category.html", context)


def _render_product_detail(request, product_obj):
    return render(request, "product.html", {"product": product_obj})


def product_detail(request, product_id):
    """Canonical product URL: identify a product by its stable primary key."""
    product_obj = get_object_or_404(_active_products(), pk=product_id)
    return _render_product_detail(request, product_obj)


def product(request, category, product):
    """
    Backwards-compatible name/category route for existing product links.

    Product names are not unique in the model, so new templates use the
    product_detail route keyed by primary key instead.
    """
    product_obj = (
        _active_products()
        .filter(category__name=category, name=product)
        .order_by("pk")
        .first()
    )
    if product_obj is None:
        raise Http404("Product not found.")
    return _render_product_detail(request, product_obj)


def healthz(request):
    """Liveness/readiness probe for the hosting platform: checks the database."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "error"}, status=503)
    return JsonResponse({"status": "ok"})
