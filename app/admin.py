from django.contrib import admin, messages

from . import models, services


@admin.register(models.Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(models.Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "price", "quantity", "is_active"]
    list_filter = ["category", "is_active"]
    list_editable = ["price", "quantity", "is_active"]
    search_fields = ["name", "description"]


@admin.register(models.Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["email", "full_name", "phone", "user", "created_at"]
    search_fields = ["email", "first_name", "last_name"]


@admin.register(models.Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ["code", "discount_type", "value", "is_active", "starts_at", "expires_at", "max_uses"]
    list_filter = ["is_active", "discount_type"]
    search_fields = ["code"]


class ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class OrderItemInline(ReadOnlyInline):
    model = models.OrderItem


class OrderTaxInline(ReadOnlyInline):
    model = models.OrderTax


@admin.register(models.Order)
class OrderAdmin(admin.ModelAdmin):
    """
    Orders are records of what the customer was charged, so they are read-only.
    Status changes go through app.services (admin actions below) so stock is
    released exactly once and invalid transitions are refused.
    """

    list_display = [
        "id", "client_name", "total", "currency",
        "payment_status", "fulfillment_status", "created_at",
    ]
    list_filter = ["payment_status", "fulfillment_status", "created_at"]
    search_fields = ["id", "client_name", "client_email"]
    inlines = [OrderItemInline, OrderTaxInline]
    actions = [
        "action_mark_paid", "action_mark_failed", "action_mark_refunded",
        "action_mark_shipped", "action_mark_delivered",
    ]

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def _apply(self, request, queryset, func, label):
        done = 0
        for order in queryset:
            try:
                func(order)
                done += 1
            except services.InvalidTransition as exc:
                self.message_user(request, str(exc), messages.ERROR)
        if done:
            self.message_user(request, f"{done} order(s) {label}.", messages.SUCCESS)

    @admin.action(description="Mark selected orders as paid (manual / testing)")
    def action_mark_paid(self, request, queryset):
        self._apply(request, queryset, services.mark_paid, "marked as paid")

    @admin.action(description="Cancel selected unpaid orders and release stock")
    def action_mark_failed(self, request, queryset):
        self._apply(request, queryset, services.mark_failed, "cancelled")

    @admin.action(description="Refund selected paid orders")
    def action_mark_refunded(self, request, queryset):
        self._apply(request, queryset, services.mark_refunded, "refunded")

    @admin.action(description="Mark selected orders as shipped")
    def action_mark_shipped(self, request, queryset):
        self._apply(request, queryset, services.mark_shipped, "marked as shipped")

    @admin.action(description="Mark selected orders as delivered")
    def action_mark_delivered(self, request, queryset):
        self._apply(request, queryset, services.mark_delivered, "marked as delivered")
