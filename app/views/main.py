from math import ceil
from django.shortcuts import render

from ..models import Category, Product


def index(request):
    categories = Category.objects.all()
    return render(request, 'index.html', {"categories": categories})


def search(request):
    q = request.GET.get('q')
    categories = Category.objects.all()
    products = Product.objects.filter(name__contains=q)
    return render(request, 'search.html', {"products": products, "categories": categories})


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
