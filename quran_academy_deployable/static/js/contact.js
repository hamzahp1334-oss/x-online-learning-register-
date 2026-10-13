// Contact form submission with inline errors.
(function () {
  "use strict";
  var form = document.getElementById("contactForm");
  if (!form) return;
  var submitBtn = form.querySelector('button[type="submit"]');
  var statusEl = document.getElementById("contactStatus");
  submitBtn.dataset.originalText = submitBtn.textContent;

  function fieldError(name, msg) {
    var el = form.querySelector('[data-error-for="' + name + '"]');
    if (el) {
      el.textContent = msg || "";
      el.classList.toggle("show", !!msg);
    }
    var input = form.querySelector('[name="' + name + '"]');
    if (input) input.classList.toggle("invalid", !!msg);
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    form.querySelectorAll(".field-error").forEach(function (el) {
      el.textContent = ""; el.classList.remove("show");
    });
    form.querySelectorAll(".invalid").forEach(function (el) { el.classList.remove("invalid"); });

    var payload = {};
    ["name", "email", "phone", "message"].forEach(function (k) {
      var el = form.querySelector('[name="' + k + '"]');
      if (el) payload[k] = el.value.trim();
    });

    submitBtn.disabled = true;
    submitBtn.classList.add("loading");
    statusEl.textContent = "Sending…";
    statusEl.className = "form-status";

    apiRequest("POST", "/api/contact", payload)
      .then(function (data) {
        form.reset();
        statusEl.textContent = data.message || "Message sent.";
        statusEl.className = "form-status ok";
      })
      .catch(function (err) {
        if (err.fieldErrors) {
          Object.keys(err.fieldErrors).forEach(function (k) { fieldError(k, err.fieldErrors[k]); });
        }
        statusEl.textContent = err.message || "Failed to send. Please try again.";
        statusEl.className = "form-status err";
      })
      .finally(function () {
        submitBtn.disabled = false;
        submitBtn.classList.remove("loading");
        submitBtn.textContent = submitBtn.dataset.originalText;
      });
  });

  form.addEventListener("input", function (e) {
    if (e.target.name) fieldError(e.target.name, "");
  });
})();
