from django.test import TestCase
from django.urls import reverse

from .models import Category, Product


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
