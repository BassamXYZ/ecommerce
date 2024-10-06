from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=70)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.FloatField()
    image = models.ImageField(default=0)
    sales = models.IntegerField(default=0)
    catigory = models.ForeignKey(Category, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Order(models.Model):
    order = models.JSONField()
    done = models.BooleanField(default=False)
