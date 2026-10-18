/* Product-detail interactions; localStorage format remains compatible with cart.html. */
(function () {
  "use strict";

  const root = document.getElementById("product-detail");
  if (!root) return;

  const quantityInput = document.getElementById("product-quantity");
  const addButton = document.getElementById("add-to-cart");
  const feedback = document.getElementById("cart-feedback");
  const productId = String(root.dataset.productId);
  const productName = root.dataset.productName || "";
  const productPrice = Number(root.dataset.productPrice);
  const productImage = root.dataset.productImage || "";
  const stock = Number.parseInt(root.dataset.productStock || "0", 10);

  function readCart() {
    try {
      const parsed = window.localStorage.getItem("cart");
      if (!parsed) return [];
      const value = JSON.parse(parsed);
      return Array.isArray(value) ? value : [];
    } catch (_error) {
      return [];
    }
  }

  function saveCart(cart) {
    try {
      window.localStorage.setItem("cart", JSON.stringify(cart));
      return true;
    } catch (_error) {
      return false;
    }
  }

  function setFeedback(message, type) {
    if (!feedback) return;
    feedback.textContent = message;
    feedback.classList.toggle("is-success", type === "success");
    feedback.classList.toggle("is-error", type === "error");
  }

  function normaliseQuantity() {
    if (!quantityInput) return 1;
    const min = 1;
    const max = Math.max(1, stock);
    const entered = Number.parseInt(quantityInput.value, 10);
    const quantity = Number.isFinite(entered) ? Math.min(max, Math.max(min, entered)) : 1;
    quantityInput.value = String(quantity);
    return quantity;
  }

  document.querySelectorAll("[data-quantity-step]").forEach(function (button) {
    button.addEventListener("click", function () {
      if (!quantityInput) return;
      const step = Number.parseInt(button.dataset.quantityStep || "0", 10);
      const current = normaliseQuantity();
      quantityInput.value = String(Math.min(Math.max(1, stock), Math.max(1, current + step)));
      setFeedback("", "");
    });
  });

  if (quantityInput) {
    quantityInput.addEventListener("change", normaliseQuantity);
    quantityInput.addEventListener("input", function () {
      setFeedback("", "");
    });
  }

  if (!addButton) return;

  addButton.addEventListener("click", function () {
    const quantity = normaliseQuantity();
    if (!root.dataset.productAvailable || root.dataset.productAvailable !== "true" || stock < 1) {
      setFeedback("This product is currently unavailable.", "error");
      return;
    }

    const cart = readCart();
    const existingIndex = cart.findIndex(function (item) {
      return item && String(item.Id) === productId;
    });
    const existingQuantity = existingIndex >= 0 ? Number(cart[existingIndex].Qty) || 0 : 0;

    if (existingQuantity + quantity > stock) {
      setFeedback("There are not enough units in stock for that quantity.", "error");
      return;
    }

    const item = {
      Id: productId,
      Product: productName,
      Price: productPrice,
      Qty: existingQuantity + quantity,
      Img: productImage
    };

    if (existingIndex >= 0) {
      cart[existingIndex] = item;
    } else {
      cart.push(item);
    }

    if (!saveCart(cart)) {
      setFeedback("Your browser could not save the cart. Check its storage settings and try again.", "error");
      return;
    }

    setFeedback("Added to cart.", "success");
  });
})();
