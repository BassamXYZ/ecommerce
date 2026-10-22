/* Small site-wide behaviors. Business logic remains server-side in Django. */
(function () {
  "use strict";

  function readCookie(name) {
    const prefix = `${name}=`;
    const cookies = document.cookie ? document.cookie.split(";") : [];
    for (const cookie of cookies) {
      const value = cookie.trim();
      if (value.startsWith(prefix)) {
        return decodeURIComponent(value.slice(prefix.length));
      }
    }
    return null;
  }

  // Send Django's CSRF cookie on HTMX requests; HTMX swaps remain HTML fragments.
  document.addEventListener("htmx:configRequest", function (event) {
    const csrfToken = readCookie("csrftoken");
    if (csrfToken) {
      event.detail.headers["X-CSRFToken"] = csrfToken;
    }
  });


  // Keep live result regions accessible while HTMX is updating them.
  document.addEventListener("htmx:beforeRequest", function (event) {
    const target = event.detail && event.detail.target;
    if (target && target.hasAttribute("aria-busy")) {
      target.setAttribute("aria-busy", "true");
    }
  });

  document.addEventListener("htmx:afterRequest", function (event) {
    const target = event.detail && event.detail.target;
    if (target && target.hasAttribute("aria-busy")) {
      target.setAttribute("aria-busy", "false");
    }
  });

  // Make failed HTMX responses visible without exposing server exception details.
  document.addEventListener("htmx:responseError", function (event) {
    const target = event.detail && event.detail.target;
    if (!target) return;
    const notice = document.createElement("p");
    notice.className = "small text-danger mt-2";
    notice.setAttribute("role", "status");
    notice.textContent = "That update could not be completed. Please try again.";
    target.appendChild(notice);
  });
})();

