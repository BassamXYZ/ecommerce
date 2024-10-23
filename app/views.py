import json
import binascii
from math import ceil
from hashlib import sha256
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.forms.models import model_to_dict

from .models import Category, Product, Order


def index(request):
    categories = Category.objects.all()
    return render(request, 'index.html', {"categories": categories})


def category(request, category):
    page = int(request.GET.get('page', 1))
    categories = Category.objects.all()
    products = Category.objects.get(name=category).product_set.all()
    pages_number = ceil(products.count()/40)
    products = products[(page-1)*40:page*40]
    name = category
    prev_page = page - 1
    next_page = page + 1
    if page == pages_number:
        next_page = 0
    return render(request, "catigory.html", {"name": name, "products": products, "categories": categories, "prev_page": prev_page, "next_page": next_page})


def product(request, category, product):
    categories = Category.objects.all()
    product = Product.objects.get(name=product)
    return render(request, 'product.html', {"product": product, "categories": categories})


def search(request):
    q = request.GET.get('q')
    categories = Category.objects.all()
    products = Product.objects.filter(name__contains=q)
    return render(request, 'search.html', {"products": products, "categories": categories})


def cart(request):
    if request.method == "POST":
        order = Order(order=json.loads(request.body))
        order.save()
        return redirect("checkout", foo="bar")
    categories = Category.objects.all()
    return render(request, 'cart.html', {"categories": categories})


def checkout(request):
    m_shop = "12345"
    m_orderid = "1"
    m_amount = "1.00"
    m_curr = "USD"
    description = "Test"
    m_key = "Secret key"
    m_desc = binascii.b2a_base64(description.encode('utf8'))[:-1].decode()
    list_of_value_for_sign = map(
        str, [m_shop, m_orderid, m_amount, m_curr, m_desc, m_key])
    result_string = ":".join(list_of_value_for_sign)
    sign_hash = sha256(result_string)
    sign = sign_hash.hexdigest().upper()
    return render(request, 'checkout.html')


@login_required
def dashboard(request):
    if request.method == "POST":
        order_compleated = Order.objects.get(
            id=json.loads(request.body)['order_id'])
        order_compleated.done = True
        order_compleated.save()
        orders = Order.objects.filter(done=False).all()
        if len(orders) > 19:
            order = orders[19]
            order = model_to_dict(order)
        else:
            order = None
        return JsonResponse(order, safe=False)
    categories = Category.objects.all()
    orders = Order.objects.filter(done=False).all()
    orders = orders[:20]
    return render(request, 'orders.html', {"orders": orders, "categories": categories})
