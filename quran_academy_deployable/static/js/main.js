// Shared site behaviour: navigation toggle.
(function () {
  "use strict";
  var toggle = document.getElementById("navToggle");
  var nav = document.getElementById("mainNav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      toggle.classList.toggle("open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }
})();

// Shared fetch helper for JSON APIs (same-origin, CSRF-safe methods included).
window.apiRequest = function (method, url, body) {
  var opts = {
    method: method,
    headers: { "X-Requested-With": "XMLHttpRequest" },
    credentials: "same-origin",
  };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  return fetch(url, opts).then(function (resp) {
    return resp
      .json()
      .catch(function () { return {}; })
      .then(function (data) {
        if (!resp.ok) {
          var err = new Error(data.error || "Request failed (" + resp.status + ")");
          err.status = resp.status;
          err.fieldErrors = data.field_errors || null;
          throw err;
        }
        return data;
      });
  });
};

// Toast helper used across pages.
window.showToast = function (message, kind) {
  var wrap = document.querySelector(".toast-wrap");
  if (!wrap) {
    wrap = document.createElement("div");
    wrap.className = "toast-wrap";
    document.body.appendChild(wrap);
  }
  var el = document.createElement("div");
  el.className = "toast " + (kind || "");
  el.textContent = message;
  wrap.appendChild(el);
  setTimeout(function () { el.remove(); }, 4200);
};
