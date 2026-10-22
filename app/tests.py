from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from .models import Category, Product, Customer, Order, OrderItem, Product


class CataloguePageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name="Garden")
        cls.product = Product.objects.create(
            name="Desk Lamp",
            description="A warm light for a reading corner.",
            price="24.50",
            category=cls.category,
            quantity=5,
            is_active=True,
        )
        cls.hidden_product = Product.objects.create(
            name="Hidden Lamp",
            description="This product is not public.",
            price="18.00",
            category=cls.category,
            quantity=5,
            is_active=False,
        )
        cls.out_of_stock_product = Product.objects.create(
            name="Garden Gloves",
            description="Gloves for outdoor work.",
            price="8.00",
            category=cls.category,
            quantity=0,
            is_active=True,
        )

    def test_home_uses_shared_base_and_featured_products(self):
        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "index.html")
        self.assertContains(response, "Desk Lamp")
        self.assertNotContains(response, "Hidden Lamp")
        self.assertContains(response, reverse("category", args=[self.category.name]))

    def test_search_full_page_uses_q_and_only_active_products(self):
        response = self.client.get(reverse("search"), {"q": "lamp"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "search.html")
        self.assertContains(response, "Desk Lamp")
        self.assertNotContains(response, "Hidden Lamp")
        self.assertEqual(response.context["q"], "lamp")

    def test_empty_search_does_not_list_all_products(self):
        response = self.client.get(reverse("search"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a search term")
        self.assertNotContains(response, "Desk Lamp")

    def test_htmx_search_returns_only_the_product_grid_partial(self):
        response = self.client.get(
            reverse("search"),
            {"q": "lamp"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "includes/product_grid.html")
        self.assertTemplateNotUsed(response, "base.html")
        self.assertContains(response, "Desk Lamp")
        self.assertNotContains(response, "<html")

    def test_category_page_handles_invalid_page_number(self):
        response = self.client.get(
            reverse("category", args=[self.category.name]),
            {"page": "not-a-number"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "category.html")
        self.assertContains(response, "Desk Lamp")
        self.assertEqual(response.context["page_obj"].number, 1)

    def test_category_filter_can_show_only_in_stock_items(self):
        response = self.client.get(
            reverse("category", args=[self.category.name]),
            {"in_stock": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Desk Lamp")
        self.assertNotContains(response, "Garden Gloves")
        self.assertTrue(response.context["in_stock"])

    def test_category_sort_is_whitelisted_and_applied(self):
        response = self.client.get(
            reverse("category", args=[self.category.name]),
            {"sort": "price_asc"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [product.name for product in response.context["products"]],
            ["Garden Gloves", "Desk Lamp"],
        )

        invalid_sort = self.client.get(
            reverse("category", args=[self.category.name]),
            {"sort": "unexpected-field"},
        )
        self.assertEqual(invalid_sort.status_code, 200)
        self.assertEqual(invalid_sort.context["sort"], "name")

    def test_htmx_category_request_returns_category_results_partial(self):
        response = self.client.get(
            reverse("category", args=[self.category.name]),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "includes/category_results.html")
        self.assertTemplateNotUsed(response, "base.html")
        self.assertContains(response, "Desk Lamp")

    def test_category_pagination_supports_htmx_page_two(self):
        for index in range(24):
            Product.objects.create(
                name=f"Product {index:02d}",
                description="Test catalogue item",
                price="1.00",
                category=self.category,
                quantity=1,
                is_active=True,
            )

        response = self.client.get(
            reverse("category", args=[self.category.name]),
            {"page": "2"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page 2 of 2")
        self.assertContains(response, "hx-get=")
        self.assertNotContains(response, "Product 00")

    def test_product_detail_uses_real_category_field_and_named_urls(self):
        response = self.client.get(
            reverse("product_detail", args=[self.product.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "product.html")
        self.assertContains(response, "Desk Lamp")
        self.assertContains(
            response,
            reverse("category", args=[self.category.name]),
        )
        self.assertContains(response, "Add to cart")

        legacy_response = self.client.get(
            reverse("product", args=[self.category.name, self.product.name])
        )
        self.assertEqual(legacy_response.status_code, 200)

    def test_product_must_match_category_and_be_active(self):
        wrong_category = Category.objects.create(name="Office")
        missing = self.client.get(
            reverse("product", args=[wrong_category.name, self.product.name])
        )
        inactive = self.client.get(
            reverse("product", args=[self.category.name, self.hidden_product.name])
        )

        self.assertEqual(missing.status_code, 404)
        self.assertEqual(inactive.status_code, 404)


class RouteNameValidationTests(TestCase):
    def test_shared_header_and_account_route_names_reverse(self):
        names_and_args = [
            ("index", []),
            ("search", []),
            ("cart", []),
            ("category", ["Garden"]),
            ("product_detail", [1]),
            ("product", ["Garden", "Desk Lamp"]),
            ("accounts:login", []),
            ("accounts:register", []),
            ("accounts:logout", []),
            ("accounts:password_reset", []),
        ]

        for name, args in names_and_args:
            with self.subTest(name=name):
                self.assertTrue(reverse(name, args=args))


class CartCheckoutFlowTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Accessories")
        self.product = Product.objects.create(
            name="Canvas bag",
            description="A sturdy bag",
            price=Decimal("12.50"),
            category=self.category,
            quantity=5,
            is_active=True,
        )
        self.checkout_data = {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
            "phone": "",
            "street": "1 Analytical Engine Way",
            "city": "London",
            "postal_code": "N1 1AA",
            "country": "United Kingdom",
        }

    def add_product(self, quantity=1):
        return self.client.post(
            reverse("add_to_cart", args=[self.product.pk]),
            {"quantity": str(quantity)},
            follow=True,
        )

    def test_add_to_cart_checkout_order_and_confirmation(self):
        response = self.add_product(2)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session["cart"][str(self.product.pk)], 2)

        response = self.client.post(reverse("checkout"), self.checkout_data)
        order = Order.objects.get()
        self.assertRedirects(response, reverse("order_confirmation", args=[order.pk]))
        self.assertEqual(order.total, Decimal("25.00"))
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.get().unit_price, Decimal("12.50"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 3)
        self.assertNotIn("cart", self.client.session)

        confirmation = self.client.get(reverse("order_confirmation", args=[order.pk]))
        self.assertEqual(confirmation.status_code, 200)
        self.assertContains(confirmation, "Thank you for your order")

    def test_empty_cart_cannot_checkout(self):
        response = self.client.get(reverse("checkout"))
        self.assertRedirects(response, reverse("cart"))
        self.assertEqual(Order.objects.count(), 0)

    def test_invalid_quantity_is_rejected(self):
        response = self.add_product(0)
        self.assertNotIn(str(self.product.pk), self.client.session.get("cart", {}))
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_rejects_insufficient_stock(self):
        self.add_product(4)
        self.product.quantity = 2
        self.product.save(update_fields=["quantity"])
        response = self.client.post(reverse("checkout"), self.checkout_data)
        self.assertRedirects(response, reverse("cart"))
        self.assertEqual(Order.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 2)

    def test_deleted_product_is_removed_from_cart(self):
        product_id = self.product.pk
        self.client.session["cart"] = {str(product_id): 1}
        self.client.session.save()
        self.product.delete()
        response = self.client.get(reverse("cart"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(str(product_id), self.client.session.get("cart", {}))
        self.assertContains(response, "no longer available")

    def test_guest_cannot_view_another_orders_confirmation(self):
        order = Order.objects.create(
            client_name="Someone Else",
            client_email="other@example.com",
            client_country="NL",
            client_city="Delft",
            client_street="Other Street 1",
            client_postal_code="2611AA",
            subtotal=Decimal("12.50"),
            total=Decimal("12.50"),
        )
        response = self.client.get(reverse("order_confirmation", args=[order.pk]))
        self.assertEqual(response.status_code, 404)

    def test_authenticated_order_is_only_visible_to_owner(self):
        User = get_user_model()
        owner = User.objects.create_user(email="owner@example.com", password="test-pass-123")
        customer = Customer.objects.create(
            user=owner,
            first_name="Order",
            last_name="Owner",
            email="owner@example.com",
        )
        order = Order.objects.create(
            customer=customer,
            client_name="Order Owner",
            client_email="owner@example.com",
            client_country="NL",
            client_city="Delft",
            client_street="Owner Street 1",
            client_postal_code="2611AA",
            subtotal=Decimal("0.00"),
            total=Decimal("0.00"),
        )
        other = User.objects.create_user(email="other@example.com", password="test-pass-123")
        self.client.force_login(other)
        response = self.client.get(reverse("order_confirmation", args=[order.pk]))
        self.assertEqual(response.status_code, 404)

    def test_product_must_be_active_to_add_to_cart(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])
        response = self.client.post(reverse("add_to_cart", args=[self.product.pk]), {"quantity": 1})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(OrderItem.objects.count(), 0)
