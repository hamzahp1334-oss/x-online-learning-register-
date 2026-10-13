// Registration form: client validation, guardian logic for minors,
// live program/price summary, duplicate-submit protection.
(function () {
  "use strict";
  var form = document.getElementById("registerForm");
  if (!form) return;

  var PROGRAMS = [];
  document.querySelectorAll(".program-option").forEach(function (opt) {
    var input = opt.querySelector("input");
    PROGRAMS.push({
      slug: input.value,
      name: opt.querySelector(".program-option-name").textContent.trim(),
      priceText: opt.querySelector(".program-option-price").textContent.trim(),
    });
  });

  var submitBtn = document.getElementById("submitBtn");
  var statusEl = document.getElementById("formStatus");
  var summaryBody = document.getElementById("summaryBody");
  var ageInput = document.getElementById("rf-age");
  var guardianFields = ["rf-pname", "rf-pphone"];
  var guardianNote = document.getElementById("guardianNote");
  var submitting = false;

  function fieldError(name, msg) {
    var el = form.querySelector('[data-error-for="' + name + '"]');
    if (el) {
      el.textContent = msg || "";
      el.classList.toggle("show", !!msg);
    }
    var input = form.querySelector('[name="' + name + '"]');
    if (input) input.classList.toggle("invalid", !!msg);
  }

  function clearAllErrors() {
    form.querySelectorAll(".field-error").forEach(function (el) {
      el.textContent = "";
      el.classList.remove("show");
    });
    form.querySelectorAll(".invalid").forEach(function (el) {
      el.classList.remove("invalid");
    });
  }

  function selectedProgram() {
    var input = form.querySelector('input[name="program_slug"]:checked');
    if (!input) return null;
    return PROGRAMS.find(function (p) { return p.slug === input.value; }) || null;
  }

  function updateSummary() {
    if (!summaryBody) return;
    var p = selectedProgram();
    if (!p) {
      summaryBody.innerHTML = '<p class="muted">Choose a program to see its monthly price here.</p>';
      return;
    }
    var nameEl = document.getElementById("rf-name");
    var levelEl = document.getElementById("rf-level");
    summaryBody.innerHTML =
      '<div class="summary-line"><span>Program</span><strong></strong></div>' +
      '<div class="summary-line"><span>Monthly price</span><strong></strong></div>' +
      '<div class="summary-line"><span>Student</span><strong></strong></div>' +
      '<div class="summary-line"><span>Level</span><strong></strong></div>';
    var lines = summaryBody.querySelectorAll(".summary-line strong");
    lines[0].textContent = p.name;
    lines[1].textContent = p.priceText;
    lines[2].textContent = nameEl.value.trim() || "—";
    lines[3].textContent = levelEl.value || "—";
  }

  function updateGuardianRequired() {
    var age = parseInt(ageInput.value, 10);
    var minor = !isNaN(age) && age > 0 && age < 18;
    guardianFields.forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.required = minor;
    });
    if (guardianNote) {
      guardianNote.textContent = minor
        ? "(required — the student is under 18)"
        : "(required for students under 18)";
    }
  }

  function clientValidate() {
    var errors = {};
    var get = function (name) {
      var el = form.querySelector('[name="' + name + '"]');
      return el ? el.value.trim() : "";
    };
    if (!get("full_name")) errors.full_name = "Student's full name is required.";
    var age = get("age");
    if (!age) errors.age = "Student's age is required.";
    else if (!(+age >= 3 && +age <= 110)) errors.age = "Age must be between 3 and 110.";
    if (!get("country")) errors.country = "Country is required.";
    if (!get("city")) errors.city = "City or location is required.";
    var phone = get("phone");
    if (!phone) errors.phone = "Phone number is required.";
    else if (!/^\+?[0-9][0-9\s\-()]{6,19}$/.test(phone) || phone.replace(/\D/g, "").length < 7)
      errors.phone = "Enter a valid phone number including country code (e.g. +251912345678).";
    if (!get("reading_level")) errors.reading_level = "Please select the current reading level.";
    if (!get("preferred_schedule")) errors.preferred_schedule = "Please select a preferred schedule.";
    if (+age >= 3 && +age < 18) {
      if (!get("parent_name")) errors.parent_name = "Required for students under 18.";
      if (!get("parent_phone")) errors.parent_phone = "Required for students under 18.";
    }
    if (!selectedProgram()) errors.program = "Please select a program.";
    return errors;
  }

  function setLoading(on, msg) {
    submitting = on;
    submitBtn.disabled = on;
    submitBtn.classList.toggle("loading", on);
    if (!on) submitBtn.textContent = submitBtn.dataset.originalText;
    if (msg !== undefined) {
      statusEl.textContent = msg || "";
      statusEl.className = "form-status" + (msg ? (on ? "" : " err") : "");
    }
  }

  submitBtn.dataset.originalText = submitBtn.textContent;

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (submitting) return; // duplicate-click protection

    clearAllErrors();
    statusEl.textContent = "";
    statusEl.className = "form-status";

    var errors = clientValidate();
    var hasError = false;
    Object.keys(errors).forEach(function (k) { fieldError(k, errors[k]); hasError = true; });
    if (hasError) {
      statusEl.textContent = "Please correct the highlighted fields.";
      statusEl.className = "form-status err";
      var firstInvalid = form.querySelector(".invalid") ||
        form.querySelector(".field-error.show");
      if (firstInvalid && firstInvalid.scrollIntoView)
        firstInvalid.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }

    setLoading(true);
    statusEl.textContent = "Submitting your registration…";
    statusEl.className = "form-status";

    var payload = {};
    ["full_name", "age", "country", "city", "phone", "whatsapp", "email", "gender",
     "reading_level", "preferred_schedule", "class_format", "parent_name",
     "parent_phone", "previous_experience", "learning_goals", "referral_source"]
      .forEach(function (k) {
        var el = form.querySelector('[name="' + k + '"]');
        if (el) payload[k] = el.value.trim();
      });
    var prog = selectedProgram();
    if (prog) payload.program_slug = prog.slug;

    apiRequest("POST", "/api/register", payload)
      .then(function (data) {
        if (data.redirect) window.location.href = data.redirect;
        else window.location.href = "/register/success/" + data.reg_id;
      })
      .catch(function (err) {
        clearAllErrors();
        if (err.fieldErrors) {
          Object.keys(err.fieldErrors).forEach(function (k) {
            fieldError(k, err.fieldErrors[k]);
          });
        }
        setLoading(false, err.message || "Something went wrong. Please try again.");
        // Submitted values stay in the form so nothing is lost.
      });
  });

  form.addEventListener("input", function (e) {
    var name = e.target.name;
    if (name) fieldError(name, "");
  });

  form.querySelectorAll('input[name="program_slug"]').forEach(function (input) {
    input.addEventListener("change", function () {
      fieldError("program", "");
      updateSummary();
    });
  });
  if (ageInput) ageInput.addEventListener("input", updateGuardianRequired);
  ["rf-name", "rf-level"].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener("input", updateSummary);
  });

  updateGuardianRequired();
  updateSummary();
})();
