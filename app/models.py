from decimal import Decimal

from django.conf import settings
from django.core.validators import (
    MinValueValidator,
    RegexValidator,
)
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

# ============================================================
# CATEGORY
# ============================================================


class Category(models.Model):
    name = models.CharField(
        max_length=70,
        unique=True,
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


# ============================================================
# PRODUCT
# ============================================================


class Product(models.Model):
    name = models.CharField(
        max_length=200,
    )

    description = models.TextField(
        blank=True,
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
    )

    image = models.ImageField(
        upload_to="products/",
        blank=True,
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )

    quantity = models.PositiveIntegerField(
        default=0,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["name"]

        indexes = [
            models.Index(
                fields=["category", "name"],
                name="product_category_name_idx",
            ),
            models.Index(
                fields=["is_active", "quantity"],
                name="product_availability_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=0),
                name="product_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=0),
                name="product_quantity_nonnegative",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def is_in_stock(self):
        return self.quantity > 0

    @property
    def is_available(self):
        return self.is_active and self.quantity > 0


# ============================================================
# CUSTOMER
# ============================================================


class Customer(models.Model):
    """
    Customer profile for the commerce domain.

    The optional user relationship prepares the application
    for future Django authentication integration.

    Guest customers can exist without a user account.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_profile",
    )

    first_name = models.CharField(
        max_length=100,
    )

    last_name = models.CharField(
        max_length=100,
    )

    email = models.EmailField(
        max_length=254,
        db_index=True,
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


# ============================================================
# COUPON
# ============================================================


class Coupon(models.Model):
    """
    Reusable discount definition.

    The actual discount applied to an order is recorded
    separately on the Order model.
    """

    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage"
        FIXED = "fixed", "Fixed amount"

    code = models.CharField(
        max_length=50,
        unique=True,
    )

    discount_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,
    )

    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
    )

    is_active = models.BooleanField(
        default=True,
    )

    starts_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    max_uses = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum total uses. Leave blank for unlimited uses.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["code"]

        constraints = [
            models.CheckConstraint(
                condition=Q(value__gte=0),
                name="coupon_value_nonnegative",
            ),
            models.CheckConstraint(
                condition=(~Q(discount_type="percentage") | Q(value__lte=100)),
                name="coupon_percentage_max_100",
            ),
            models.CheckConstraint(
                condition=(
                    Q(starts_at__isnull=True)
                    | Q(expires_at__isnull=True)
                    | Q(expires_at__gt=F("starts_at"))
                ),
                name="coupon_valid_date_range",
            ),
        ]

    def __str__(self):
        return self.code

    def is_valid(self, at=None):
        """
        Check basic coupon eligibility.

        This does not enforce usage limits, customer eligibility,
        minimum order values, or concurrent redemption safety.
        Those belong in the checkout service.
        """
        at = at or timezone.now()

        if not self.is_active:
            return False

        if self.starts_at and at < self.starts_at:
            return False

        if self.expires_at and at >= self.expires_at:
            return False

        return True


# ============================================================
# ORDER
# ============================================================


class Order(models.Model):
    """
    Customer order with immutable-in-practice checkout snapshots.

    Monetary totals are persisted and should be calculated by
    the checkout service rather than trusted from the client.
    """

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    class FulfillmentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    # --------------------------------------------------------
    # Customer relationship
    # --------------------------------------------------------

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders",
    )

    # --------------------------------------------------------
    # Customer and shipping snapshots
    #
    # These fields preserve the details used at checkout,
    # even if the customer's profile changes later.
    # --------------------------------------------------------

    client_name = models.CharField(
        max_length=200,
    )

    client_email = models.EmailField(
        max_length=254,
    )

    client_country = models.CharField(
        max_length=100,
    )

    client_city = models.CharField(
        max_length=100,
    )

    client_street = models.CharField(
        max_length=200,
    )

    client_postal_code = models.CharField(
        max_length=20,
    )

    # --------------------------------------------------------
    # Coupon relationship
    # --------------------------------------------------------

    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )

    # --------------------------------------------------------
    # Financial breakdown
    # --------------------------------------------------------

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
    )

    shipping_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
    )

    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
    )

    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
    )

    currency = models.CharField(
        max_length=3,
        default="EUR",
        validators=[
            RegexValidator(
                regex=r"^[A-Z]{3}$",
                message="Currency must be a three-letter uppercase code.",
            ),
        ],
    )

    # --------------------------------------------------------
    # Payment and fulfillment
    # --------------------------------------------------------

    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )

    fulfillment_status = models.CharField(
        max_length=20,
        choices=FulfillmentStatus.choices,
        default=FulfillmentStatus.PENDING,
    )

    # --------------------------------------------------------
    # Timestamps
    # --------------------------------------------------------

    created_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["payment_status", "created_at"],
                name="order_payment_created_idx",
            ),
            models.Index(
                fields=["fulfillment_status", "created_at"],
                name="order_fulfill_created_idx",
            ),
            models.Index(
                fields=["customer", "created_at"],
                name="order_customer_created_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(subtotal__gte=0),
                name="order_subtotal_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(shipping_cost__gte=0),
                name="order_shipping_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(discount_amount__gte=0),
                name="order_discount_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(tax_amount__gte=0),
                name="order_tax_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(total__gte=0),
                name="order_total_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(discount_amount__lte=F("subtotal")),
                name="order_discount_not_over_subtotal",
            ),
        ]

    def __str__(self):
        return f"Order #{self.pk}"

    @property
    def calculated_total(self):
        """
        Calculate the expected total from stored components.

        This property does not save the result or enforce
        consistency between the stored total and its components.
        """
        return (
            self.subtotal + self.shipping_cost + self.tax_amount - self.discount_amount
        )


# ============================================================
# ORDER ITEM
# ============================================================


class OrderItem(models.Model):
    """
    A product line belonging to a specific order.

    unit_price preserves the price charged at checkout,
    even if the current product price changes later.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="order_items",
    )

    quantity = models.PositiveIntegerField(
        validators=[
            MinValueValidator(1),
        ],
    )

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gte=1),
                name="order_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0),
                name="order_item_price_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    @property
    def subtotal(self):
        return self.unit_price * self.quantity


# ============================================================
# ORDER TAX
# ============================================================


class OrderTax(models.Model):
    """
    Tax snapshot associated with an order.

    Supports multiple tax components when necessary.
    Order.tax_amount should equal the sum of the associated
    OrderTax amounts when this model is used.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="taxes",
    )

    name = models.CharField(
        max_length=100,
    )

    jurisdiction = models.CharField(
        max_length=150,
        blank=True,
    )

    taxable_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
    )

    rate = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        validators=[
            MinValueValidator(Decimal("0.0000")),
        ],
        help_text="Tax rate as a percentage, e.g. 20.0000 for 20%.",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
    )

    class Meta:
        ordering = ["id"]

        constraints = [
            models.CheckConstraint(
                condition=Q(taxable_amount__gte=0),
                name="order_tax_base_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(rate__gte=0),
                name="order_tax_rate_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(amount__gte=0),
                name="order_tax_amount_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.name}: {self.amount}"
