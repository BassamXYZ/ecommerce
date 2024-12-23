import json
import binascii
from django.shortcuts import render, redirect
from django.conf import settings

from ..models import Category, Product, Order, Item
from ..functions import get_client_ip, hash_payeer_sign


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


def checkout(request):
    if request.method == "POST":
        ip = get_client_ip(request)
        if ip not in ['185.71.65.92', '185.71.65.189', '149.202.17.210']:
            return

        if 'm_operation_id' in request.POST and 'm_sign' in request.POST:
            m_key = settings.SECRET_KEY
            m_operation_id = request.POST.get('m_operation_id')
            m_operation_ps = request.POST.get('m_operation_ps')
            m_operation_date = request.POST.get('m_operation_date')
            m_operation_pay_date = request.POST.get('m_operation_pay_date')
            m_shop = request.POST.get('m_shop')
            m_orderid = request.POST.get('m_orderid')
            m_amount = request.POST.get('m_amount')
            m_curr = request.POST.get('m_curr')
            m_desc = request.POST.get('m_desc')
            m_status = request.POST.get('m_status')

            m_sign = hash_payeer_sign(
                m_key, m_operation_id, m_operation_ps, m_operation_date, m_operation_pay_date, m_shop, m_orderid, m_amount, m_curr, m_desc, m_status)

            if request.POST.get('m_sign') == m_sign and request.POST.get('m_status') == 'success':
                order = Order.objects.get(id=request.POST.get('m_orderid'))
                order.payed = True
                order.save()
                return

        return
    
    # prosses for GET requests
    order_id = request.GET.get('id')
    order = Order.objects.get(id=order_id)
    if order.payed == True:
        return
    m_shop = settings.PAYEER_SHOP_ID
    m_key = settings.SECRET_KEY
    m_orderid = order_id
    m_amount = order[0].total
    m_curr = "USD"
    description = "Test"
    m_desc = binascii.b2a_base64(description.encode('utf8'))[:-1].decode()
    m_sign = hash_payeer_sign(
        m_shop, m_orderid, m_amount, m_curr, m_desc, m_key)
    return render(request, 'checkout.html', {"m_orderid": m_orderid, "m_amount": m_amount, "m_desc": m_desc, "m_sign": m_sign})

