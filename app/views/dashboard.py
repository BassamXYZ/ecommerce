import json
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.forms.models import model_to_dict

from ..models import Category, Order


@login_required
def orders(request):
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


@login_required
def analytics(request):
    categories = Category.objects.all()
    return render(request, 'analytics.html', {"categories": categories})
