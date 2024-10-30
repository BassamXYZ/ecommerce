from django.db import models
from datetime import datetime


class Category(models.Model):
    name = models.CharField(max_length=70)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.FloatField()
    image = models.ImageField(default=0)
    catigory = models.ForeignKey(Category, on_delete=models.SET_NULL)
    quantity = models.IntegerField(default=0)

    def __str__(self):
        return self.name


class Item(models.Model):
    product = models.ForeignKey(Product)
    quantity = models.IntegerField()


class Order(models.Model):
    client_name = models.CharField(max_length=200)
    client_email = models.EmailField(max_length=50)
    client_country = models.CharField(max_length=50)
    client_city = models.CharField(max_length=50)
    client_street = models.CharField(max_length=50)
    client_postal_code = models.CharField(max_length=50)
    items = models.ManyToManyField(Item)
    total = models.FloatField()
    payed = models.BooleanField(default=False)
    shipped = models.BooleanField(default=False)
    date = models.DateField(default=datetime.now)
