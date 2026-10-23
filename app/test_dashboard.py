from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from . import services
from .models import Category, Order, Product
from .test_services import SHIPPING


class StaffOnlyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.customer = User.objects.create_user("c@example.com", "pw-Str0ng!pass")
        cls.staff = User.objects.create_user("s@example.com", "pw-Str0ng!pass", is_staff=True)
        cat = Category.objects.create(name="Shoes")
        cls.product = Product.objects.create(name="A", price="10.00", category=cat, quantity=5)

    def make_order(self, paid=True):
        order = services.create_order(cart={str(self.product.pk): 1}, shipping=SHIPPING)
        if paid:
            services.mark_paid(order)
        return order

    def test_anonymous_users_are_sent_to_login(self):
        for name in ("orders", "analytics"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("accounts:login"), response["Location"])

    def test_regular_customers_get_403(self):
        self.client.force_login(self.customer)
        for name in ("orders", "analytics"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)
        order = self.make_order()
        response = self.client.post(reverse("ship_order", args=[order.pk]))
        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.fulfillment_status, Order.FulfillmentStatus.PENDING)

    def test_inactive_staff_cannot_use_dashboard(self):
        self.staff.is_active = False
        self.staff.save()
        self.client.force_login(self.staff)  # inactive users cannot stay logged in
        self.assertNotEqual(self.client.get(reverse("orders")).status_code, 200)

    def test_staff_sees_only_paid_unshipped_orders(self):
        paid = self.make_order()
        unpaid = self.make_order(paid=False)
        self.client.force_login(self.staff)
        response = self.client.get(reverse("orders"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Order #{paid.pk}")
        self.assertNotContains(response, f"Order #{unpaid.pk}")

    def test_staff_can_ship_a_paid_order(self):
        order = self.make_order()
        self.client.force_login(self.staff)
        response = self.client.post(reverse("ship_order", args=[order.pk]))
        self.assertRedirects(response, reverse("orders"))
        order.refresh_from_db()
        self.assertEqual(order.fulfillment_status, Order.FulfillmentStatus.SHIPPED)

    def test_shipping_an_unpaid_order_is_refused(self):
        order = self.make_order(paid=False)
        self.client.force_login(self.staff)
        self.client.post(reverse("ship_order", args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.fulfillment_status, Order.FulfillmentStatus.PENDING)

    def test_ship_requires_post(self):
        order = self.make_order()
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("ship_order", args=[order.pk])).status_code, 405)

    def test_admin_actions_use_state_rules(self):
        admin = get_user_model().objects.create_superuser("root@example.com", "pw-Str0ng!pass")
        self.client.force_login(admin)
        order = self.make_order(paid=False)
        data = {"action": "action_mark_failed", "_selected_action": [order.pk]}
        self.client.post(reverse("admin:app_order_changelist"), data)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.FAILED)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 5)

    def test_admin_order_page_is_read_only(self):
        admin = get_user_model().objects.create_superuser("root@example.com", "pw-Str0ng!pass")
        self.client.force_login(admin)
        order = self.make_order()
        response = self.client.get(reverse("admin:app_order_change", args=[order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="payment_status"')


class HealthCheckTests(TestCase):
    def test_healthz_reports_ok(self):
        response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
