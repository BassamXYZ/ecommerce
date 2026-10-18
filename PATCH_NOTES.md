# Catalogue template + HTMX patch

## Scope

This patch migrates the home, search, category, and product-detail pages to the existing shared `base.html`. It uses Bootstrap classes plus the project's `site.css`, and HTMX for search-result refresh plus category sorting, in-stock filtering, and pagination. Cart, checkout, order-history, and analytics pages are intentionally unchanged.

## Key files changed

- `app/views/main.py`: active-product filtering, robust search, safe category pagination, partial responses for HTMX requests, and a canonical product-detail view.
- `app/urls.py`: adds `product_detail` at `/product/<id>/` while retaining the old named `product` route.
- `app/templates/index.html`, `search.html`, `category.html`, `product.html`: redesigned full-page templates extending `base.html`.
- `app/templates/includes/product_grid.html`: shared product-card grid for home, search, and category results.
- `app/templates/includes/category_results.html`: grid plus pagination, suitable for full-page and HTMX responses.
- `app/static/css/site.css`: hero, category, catalog, pagination, and product-detail styles.
- `app/static/js/product-detail.js`: product quantity and add-to-localStorage behavior. It retains the cart's existing `Id`, `Product`, `Price`, `Qty`, `Img` data keys.
- `app/static/js/site.js`: toggles `aria-busy` around HTMX requests.
- `accounts/views.py` and `accounts/templates/accounts/register.html`: correct the namespaced login route reference.
- `app/tests.py`: adds catalogue, HTMX, legacy URL, and URL-reversal tests.

## URL and template context contract

| Route name | Purpose | View/context |
|---|---|---|
| `index` | Home | `categories`; each category receives `featured_products` (up to eight active products). |
| `search` | Search page and search fragment | `q`, `products`. An `HX-Request: true` request receives `includes/product_grid.html`; normal requests receive `search.html`. |
| `category` | Legacy category path | `category`, `name` (compatibility alias), `products`, `page_obj`, `sort`, `in_stock`, `empty_message`. HTMX requests receive `includes/category_results.html`. |
| `product_detail` | Canonical product URL by primary key | `product`. Used by new product cards so duplicate product names don't produce ambiguous links. |
| `product` | Backwards-compatible category/name URL | Still resolves older links; new templates no longer generate this potentially ambiguous URL. |
| `cart`, `checkout`, `orders`, `analytics` | Existing pages | Their routes and views are unchanged. |
| `accounts:login`, `accounts:register`, `accounts:logout`, `accounts:password_reset` | Existing account routes | Names are namespaced as `accounts`; the registration redirect/template now use that namespace. |

## Template retirement decision

**Safe to remove:** `app/templates/catigory.html`. It was the misspelled category template used by the previous category view. The view now renders `category.html`, and repository references to `catigory.html` have been checked.

**Do not remove yet:** `cart.html`, `checkout.html`, `orders.html`, or `analytics.html`. Their views still render them and those pages are explicitly out of this migration scope. `base.html` and the shared `includes/` templates are in use. The product page's obsolete inline script was removed from `product.html` and replaced by `static/js/product-detail.js`.

## Validation

AST parsing completed successfully for all Python source files. A source scan found no active-code references to the retired `catigory.html`, no `product.catigory` field access, no unnamespaced login URL, and no hard-coded `/product/...` or `/category/...` links. The retired filename appears here only to document its removal.

Run in the project's configured virtual environment before merging:

```bash
python manage.py check
python manage.py test
```

The Django system check and test suite could not be executed in this packaging environment because Django and the project's dependencies are not installed, and package installation is blocked by unavailable network access. No database migrations were added or changed.

## Next stage

After these tests pass locally, check the home/search/category/product pages in a browser at desktop and mobile widths. Do not start cart/checkout redesign until the catalogue behavior is accepted; those pages have separate existing order-processing issues and should be handled in their own stage.
