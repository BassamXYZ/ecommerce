import json
import binascii
from math import ceil
from hashlib import sha256
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.forms.models import model_to_dict
from django.conf import settings

from .models import Category, Product, Order, Item
from .functions import get_client_ip


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
        data = json.loads(request.body)
        items = []
        total = 0
        for item in data["items"]:
            product = Product.objects.get(id=item["product_id"])
            db_item = Item(product=product, quantity=item["quantity"])
            db_item.save()
            items.append(db_item)
            total = total + product.price * item["quantity"]

        order = Order(client_name=data["client_name"],
                      client_email=data["client_email"],
                      client_country=data["client_country"],
                      client_city=data["client_city"],
                      client_street=data["client_street"],
                      client_postal_code=data["client_postal_code"],
                      total=total,
                      items=items)
        order.save()

        return redirect("checkout", order_id=order.id)
    categories = Category.objects.all()
    return render(request, 'cart.html', {"categories": categories})


def checkout(request, order_id):
    order = Order.objects.get(id=order_id)
    if order.payed == True:
        return
    m_shop = settings.PAYEER_SHOP_ID
    m_orderid = order_id
    m_amount = order[0].total
    m_curr = "USD"
    description = "Test"
    m_desc = binascii.b2a_base64(description.encode('utf8'))[:-1].decode()
    m_key = settings.SECRET_KEY
    list_of_value_for_sign = map(
        str, [m_shop, m_orderid, m_amount, m_curr, m_desc, m_key])
    result_string = ":".join(list_of_value_for_sign)
    sign_hash = sha256(result_string)
    m_sign = sign_hash.hexdigest().upper()
    return render(request, 'checkout.html', {"m_orderid": m_orderid, "m_amount": m_amount, "m_desc": m_desc, "m_sign": m_sign})


def payment_processor(request):
    ip = get_client_ip(request)
    if ip not in ['185.71.65.92', '185.71.65.189', '149.202.17.210']:
        return
    
    if 'm_operation_id' in request.POST and 'm_sign' in request.POST:
        m_key = settings.SECRET_KEY
        list_of_value_for_sign = map(str, [request.POST.get('m_operation_id'),
                                           request.POST.get('m_operation_ps'),
                                           request.POST.get('m_operation_date'),
                                           request.POST.get('m_operation_pay_date'),
                                           request.POST.get('m_shop'),
                                           request.POST.get('m_orderid'),
                                           request.POST.get('m_amount'),
                                           request.POST.get('m_curr'),
                                           request.POST.get('m_desc'),
                                           request.POST.get('m_status'),
                                           m_key])
        result_string = ":".join(list_of_value_for_sign)
        sign_hash = sha256(result_string)
        m_sign = sign_hash.hexdigest().upper()
        if request.POST.get('m_sign') == m_sign and request.POST.get('m_status') == 'success':
            order = Order.objects.get(id=request.POST.get('m_orderid'))
            order.payed = True
            order.save()
            return

    return


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