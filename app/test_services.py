from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from . import services
from .models import Category, Order, Product

SHIPPING = {
    "first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.com",
    "phone": "", "street": "1 Engine Way", "city": "London",
    "postal_code": "N1 1AA", "country": "UK",
}


class ServiceTestBase(TestCase):
    def setUp(self):
        cat = Category.objects.create(name="Shoes")
        self.a = Product.objects.create(name="A", price="19.99", category=cat, quantity=5)
        self.b = Product.objects.create(name="B", price="0.10", category=cat, quantity=2)

    def make_order(self, cart=None):
        return services.create_order(
            cart=cart or {str(self.a.pk): 2, str(self.b.pk): 1}, shipping=SHIPPING
        )

    def stock(self, product):
        product.refresh_from_db()
        return product.quantity


class CreateOrderTests(ServiceTestBase):
    def test_totals_come_from_database_prices_and_stock_is_reserved(self):
        order = self.make_order()
        self.assertEqual(order.subtotal, Decimal("40.08"))
        self.assertEqual(order.total, order.calculated_total)
        self.assertEqual(order.total, Decimal("40.08"))
        self.assertEqual(self.stock(self.a), 3)
        self.assertEqual(self.stock(self.b), 1)
        self.assertEqual({i.unit_price for i in order.items.all()}, {Decimal("19.99"), Decimal("0.10")})

    def test_order_keeps_price_snapshot_when_product_price_changes(self):
        order = self.make_order()
        self.a.price = Decimal("99.00")
        self.a.save()
        order.refresh_from_db()
        self.assertEqual(order.total, Decimal("40.08"))
        self.assertEqual(order.items.get(product=self.a).unit_price, Decimal("19.99"))

    def test_insufficient_stock_creates_nothing(self):
        with self.assertRaises(services.CheckoutError):
            self.make_order({str(self.a.pk): 6})
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(self.stock(self.a), 5)

    def test_one_bad_line_rolls_back_the_good_ones(self):
        with self.assertRaises(services.CheckoutError):
            self.make_order({str(self.a.pk): 1, str(self.b.pk): 3})
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(self.stock(self.a), 5)

    def test_inactive_unknown_and_invalid_quantities_are_rejected(self):
        self.b.is_active = False
        self.b.save()
        for cart in ({str(self.b.pk): 1}, {"999999": 1}, {str(self.a.pk): 0},
                     {str(self.a.pk): -1}, {str(self.a.pk): 100}, {}):
            with self.subTest(cart=cart), self.assertRaises(services.CheckoutError):
                self.make_order(cart)
        self.assertEqual(Order.objects.count(), 0)

    def test_database_rejects_inconsistent_totals(self):
        order = self.make_order()
        order.total = Decimal("1.00")
        with self.assertRaises(IntegrityError), transaction.atomic():
            order.save()


class PaymentStateTests(ServiceTestBase):
    def test_mark_paid_is_idempotent(self):
        order = self.make_order()
        services.mark_paid(order)
        services.mark_paid(order)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)

    def test_failed_order_releases_stock_exactly_once(self):
        order = self.make_order()
        services.mark_failed(order)
        services.mark_failed(order)  # retry must not restock twice
        self.assertEqual(self.stock(self.a), 5)
        self.assertEqual(self.stock(self.b), 2)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.FAILED)
        self.assertEqual(order.fulfillment_status, Order.FulfillmentStatus.CANCELLED)

    def test_failed_order_cannot_be_paid_later(self):
        order = self.make_order()
        services.mark_failed(order)
        with self.assertRaises(services.InvalidTransition):
            services.mark_paid(order)

    def test_paid_order_cannot_be_failed_only_refunded(self):
        order = self.make_order()
        services.mark_paid(order)
        with self.assertRaises(services.InvalidTransition):
            services.mark_failed(order)
        self.assertEqual(self.stock(self.a), 3)

    def test_refund_before_shipping_cancels_and_restocks(self):
        order = self.make_order()
        services.mark_paid(order)
        services.mark_refunded(order)
        services.mark_refunded(order)
        self.assertEqual(self.stock(self.a), 5)
        order.refresh_from_db()
        self.assertEqual(order.fulfillment_status, Order.FulfillmentStatus.CANCELLED)

    def test_refund_after_shipping_does_not_restock(self):
        order = self.make_order()
        services.mark_paid(order)
        services.mark_shipped(order)
        services.mark_refunded(order)
        self.assertEqual(self.stock(self.a), 3)
        order.refresh_from_db()
        self.assertEqual(order.fulfillment_status, Order.FulfillmentStatus.SHIPPED)

    def test_cannot_ship_unpaid_order(self):
        order = self.make_order()
        with self.assertRaises(services.InvalidTransition):
            services.mark_shipped(order)

    def test_fulfillment_must_follow_order(self):
        order = self.make_order()
        services.mark_paid(order)
        with self.assertRaises(services.InvalidTransition):
            services.mark_delivered(order)  # not shipped yet
        services.mark_shipped(order)
        services.mark_delivered(order)
        with self.assertRaises(services.InvalidTransition):
            services.mark_processing(order)


class ExpiryTests(ServiceTestBase):
    def test_only_stale_unpaid_orders_expire(self):
        stale = self.make_order({str(self.a.pk): 1})
        fresh = self.make_order({str(self.a.pk): 1})
        paid = self.make_order({str(self.a.pk): 1})
        services.mark_paid(paid)
        old = timezone.now() - timedelta(hours=2)
        Order.objects.filter(pk__in=[stale.pk, paid.pk]).update(created_at=old)

        self.assertEqual(services.expire_stale_orders(), 1)

        for order, status in ((stale, "failed"), (fresh, "pending"), (paid, "paid")):
            order.refresh_from_db()
            self.assertEqual(order.payment_status, status)
        self.assertEqual(self.stock(self.a), 3)  # 5 - fresh - paid; stale returned
