// Admin dashboard SPA. All data is fetched from /admin/api/* which requires
// an authenticated admin session (401 responses redirect to the login page).
(function () {
  "use strict";

  // ------------------------------------------------------------ helpers
  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function fmtDate(iso) {
    if (!iso) return "—";
    return iso.replace("T", " ").replace("Z", " UTC");
  }

  function fmtPrice(p, cur) {
    if (p === null || p === undefined || p === "") return "Contact us";
    return p + " " + (cur || "") + " / month";
  }

  var STATUS_BADGE = {
    new: "badge-new", contacted: "badge-contacted", confirmed: "badge-confirmed",
    active: "badge-active", rejected: "badge-rejected", cancelled: "badge-cancelled",
  };
  var SYNC_BADGE = {
    synced: "badge-synced", pending: "badge-pending", failed: "badge-failed",
    not_configured: "badge-not_configured",
  };

  function api(method, url, body) {
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
      return resp.json().catch(function () { return {}; }).then(function (data) {
        if (resp.status === 401) { window.location.href = "/admin/login"; throw new Error("unauthorized"); }
        if (!resp.ok) {
          var err = new Error(data.error || "Request failed (" + resp.status + ")");
          err.fieldErrors = data.field_errors || null;
          throw err;
        }
        return data;
      });
    });
  }

  function toast(msg, kind) {
    var wrap = $("#toastWrap");
    var el = document.createElement("div");
    el.className = "toast " + (kind || "");
    el.textContent = msg;
    wrap.appendChild(el);
    setTimeout(function () { el.remove(); }, 4500);
  }

  // ------------------------------------------------------------ modal
  var modalBackdrop = $("#modalBackdrop");
  var modalBox = $("#modalBox");

  function openModal(html, wide) {
    modalBox.className = "modal card" + (wide ? " modal-wide" : "");
    modalBox.innerHTML = html;
    modalBackdrop.hidden = false;
    var closeBtn = modalBox.querySelector(".modal-close");
    if (closeBtn) closeBtn.addEventListener("click", closeModal);
  }
  function closeModal() { modalBackdrop.hidden = true; modalBox.innerHTML = ""; }
  modalBackdrop.addEventListener("click", function (e) {
    if (e.target === modalBackdrop) closeModal();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !modalBackdrop.hidden) closeModal();
  });

  function confirmModal(title, text, okLabel, danger, onOk) {
    openModal(
      '<div class="modal-head"><h3>' + esc(title) + '</h3><button class="modal-close" type="button" aria-label="Close">&times;</button></div>' +
      '<p class="muted">' + esc(text) + '</p>' +
      '<div class="modal-actions">' +
      '<button class="btn btn-ghost" id="mCancel">Cancel</button>' +
      '<button class="btn ' + (danger ? "btn-danger" : "btn-primary") + '" id="mOk">' + esc(okLabel) + '</button></div>');
    $("#mCancel").addEventListener("click", closeModal);
    $("#mOk").addEventListener("click", function () { closeModal(); onOk(); });
  }

  // ------------------------------------------------------------ tabs
  var TITLES = {
    overview: "Overview", registrations: "Registrations", programs: "Programs",
    pricing: "Pricing", content: "Website Content", faqs: "FAQ",
    messages: "Messages", sheets: "Google Sheets", audit: "Audit Log",
    account: "Account",
  };
  $$(".admin-tab").forEach(function (tab) {
    tab.addEventListener("click", function () { switchTab(tab.dataset.tab); });
  });
  function switchTab(name) {
    $$(".admin-tab").forEach(function (t) { t.classList.toggle("active", t.dataset.tab === name); });
    $$(".admin-panel").forEach(function (p) { p.classList.toggle("active", p.id === "panel-" + name); });
    $("#adminTitle").textContent = TITLES[name] || name;
    $("#adminSidebar").classList.remove("open");
    loadPanel(name);
  }
  var menuToggle = $("#adminMenuToggle");
  if (menuToggle) menuToggle.addEventListener("click", function () {
    $("#adminSidebar").classList.toggle("open");
  });

  function loadPanel(name) {
    if (name === "overview") loadOverview();
    else if (name === "registrations") loadRegistrations();
    else if (name === "programs") loadPrograms();
    else if (name === "pricing") loadPricing();
    else if (name === "content") loadContent();
    else if (name === "faqs") loadFaqs();
    else if (name === "messages") loadMessages();
    else if (name === "sheets") loadSheets();
    else if (name === "audit") loadAudit();
  }

  // ------------------------------------------------------------ overview
  function loadOverview() {
    api("GET", "/admin/api/stats").then(function (s) {
      var stats = s.stats;
      var cards = [
        { num: stats.total, label: "Total registrations" },
        { num: stats.new, label: "New" },
        { num: stats.awaiting_contact, label: "Contacted — awaiting confirmation" },
        { num: stats.confirmed, label: "Confirmed" },
        { num: stats.active, label: "Active students" },
        { num: stats.rejected_cancelled, label: "Rejected / cancelled" },
        { num: stats.programs, label: "Programs open for registration" },
        { num: stats.archived, label: "Archived" },
      ];
      $("#statGrid").innerHTML = cards.map(function (c) {
        return '<div class="stat-card"><div class="stat-num">' + esc(c.num) + '</div>' +
               '<div class="stat-label">' + esc(c.label) + "</div></div>";
      }).join("");

      var max = Math.max.apply(null, stats.trend.map(function (t) { return t.count; }).concat([1]));
      $("#trendChart").innerHTML = stats.trend.map(function (t) {
        var h = Math.round((t.count / max) * 100);
        var label = t.day.slice(5).replace("-", "/");
        return '<div class="trend-bar" title="' + esc(t.day) + ": " + t.count + '">' +
          '<div class="bar-count">' + (t.count || "") + "</div>" +
          '<div class="bar" style="height:' + h + '%"></div>' +
          '<div class="bar-label">' + esc(label) + "</div></div>";
      }).join("");

      var sh = stats.sheets;
      var mail = stats.notifications;
      $("#integrationStatus").innerHTML =
        integrationRow("Google Sheets", sh.configured ? "Connected" : "Not configured",
          sh.configured ? "ok" : "err") +
        (sh.configured ? integrationRow("Pending sync jobs", sh.pending) +
          integrationRow("Failed jobs", sh.failed) +
          integrationRow("Last successful sync", sh.last_success_at ? fmtDate(sh.last_success_at) : "—") : "") +
        (sh.last_error ? integrationRow("Last sync error", sh.last_error, "err") : "") +
        integrationRow("Email notifications", mail.configured ? "Configured" : "Not configured",
          mail.configured ? "ok" : "");

      var recent = stats.recent || [];
      $("#recentTable").innerHTML = recent.length ? tableHTML(
        ["Registration ID", "Date", "Student", "Program", "Status"],
        recent.map(function (r) {
          return [
            '<span class="mono">' + esc(r.reg_id) + "</span>",
            esc(fmtDate(r.created_at)),
            esc(r.full_name) + (r.country ? '<div class="muted small">' + esc(r.country) + "</div>" : ""),
            esc(r.program_name),
            '<span class="badge ' + (STATUS_BADGE[r.status] || "") + '">' + esc(r.status) + "</span>",
          ];
        })) : '<p class="muted">No registrations yet.</p>';

      var newCount = $("#navNewCount");
      newCount.hidden = !stats.new;
      newCount.textContent = stats.new;
      var msgCount = $("#navMsgCount");
      msgCount.hidden = !stats.unread_messages;
      msgCount.textContent = stats.unread_messages;
    }).catch(function (e) { toast(e.message, "err"); });
  }

  function integrationRow(label, value, kind) {
    return '<div class="integration-row"><strong>' + esc(label) + "</strong>" +
      '<span class="' + (kind === "err" ? "badge badge-failed" : kind === "ok" ? "badge badge-active" : "") +
      '">' + esc(value) + "</span></div>";
  }

  function tableHTML(headers, rows) {
    return '<table class="data-table"><thead><tr>' +
      headers.map(function (h) { return "<th>" + esc(h) + "</th>"; }).join("") +
      "</tr></thead><tbody>" +
      rows.map(function (r) { return "<tr>" + r.map(function (c) { return "<td>" + c + "</td>"; }).join("") + "</tr>"; }).join("") +
      "</tbody></table>";
  }

  // ------------------------------------------------------------ registrations
  var regState = { offset: 0, limit: 25, selected: new Set() };

  function regQueryParams() {
    var p = new URLSearchParams();
    var q = $("#regSearch").value.trim();
    if (q) p.set("q", q);
    if ($("#regStatusFilter").value) p.set("status", $("#regStatusFilter").value);
    if ($("#regProgramFilter").value) p.set("program_id", $("#regProgramFilter").value);
    if ($("#regCountryFilter").value.trim()) p.set("country", $("#regCountryFilter").value.trim());
    if ($("#regDateFrom").value) p.set("date_from", $("#regDateFrom").value);
    if ($("#regDateTo").value) p.set("date_to", $("#regDateTo").value);
    p.set("sort", $("#regSort").value);
    if ($("#regArchived").checked) p.set("archived", "1");
    p.set("limit", regState.limit);
    p.set("offset", regState.offset);
    return p;
  }

  function loadRegistrations() {
    loadProgramFilter();
    var params = regQueryParams();
    api("GET", "/admin/api/registrations?" + params.toString()).then(function (data) {
      renderRegistrations(data);
    }).catch(function (e) { $("#registrationsTable").innerHTML = '<p class="muted">' + esc(e.message) + "</p>"; });
  }

  function loadProgramFilter() {
    var sel = $("#regProgramFilter");
    if (sel.dataset.loaded) return;
    api("GET", "/admin/api/programs").then(function (data) {
      sel.innerHTML = '<option value="">All programs</option>' + data.programs.map(function (p) {
        return '<option value="' + p.id + '">' + esc(p.name) + "</option>";
      }).join("");
      sel.dataset.loaded = "1";
    }).catch(function () {});
  }

  function renderRegistrations(data) {
    var regs = data.registrations || [];
    var archived = $("#regArchived").checked;
    var rows = regs.map(function (r) {
      var cb = '<input type="checkbox" class="reg-check" data-id="' + esc(r.reg_id) + '"' +
        (regState.selected.has(r.reg_id) ? " checked" : "") + ">";
      return [
        cb + '<span class="mono">' + esc(r.reg_id) + "</span>",
        esc(fmtDate(r.created_at)),
        esc(r.full_name) + ' <span class="muted small">(' + esc(r.age) + ")</span>" +
          '<div class="muted small">' + esc(r.country || "") + "</div>",
        '<span class="mono">' + esc(r.phone) + "</span>",
        esc(r.program_name) + (r.price !== null && r.price !== undefined
          ? '<div class="muted small">' + esc(fmtPrice(r.price, r.currency)) + "</div>" : ""),
        esc(r.preferred_schedule || "—"),
        '<span class="badge ' + (STATUS_BADGE[r.status] || "") + '">' + esc(r.status) + "</span>" +
          '<div class="muted small">Sheets: <span class="badge ' + (SYNC_BADGE[r.sheets_sync_status] || "") + '">' +
          esc(r.sheets_sync_status) + "</span></div>",
        '<div class="row-actions">' +
          '<button class="btn btn-ghost btn-sm act-view" data-id="' + esc(r.reg_id) + '">View</button>' +
          '<button class="btn btn-ghost btn-sm act-edit" data-id="' + esc(r.reg_id) + '">Edit</button>' +
          (archived
            ? '<button class="btn btn-ghost btn-sm act-unarchive" data-id="' + esc(r.reg_id) + '">Unarchive</button>'
            : '<button class="btn btn-ghost btn-sm act-archive" data-id="' + esc(r.reg_id) + '">Archive</button>') +
          "</div>",
      ];
    });
    $("#registrationsTable").innerHTML = rows.length ? tableHTML(
      ["", "Registration ID", "Date", "Student", "Phone", "Program", "Schedule", "Status", "Actions"], rows) :
      '<p class="muted">No registrations match the current filters.</p>';

    // pagination
    var total = data.total, page = Math.floor(regState.offset / regState.limit) + 1;
    var pages = Math.max(1, Math.ceil(total / regState.limit));
    $("#regPager").innerHTML =
      '<span class="muted small">' + total + " record" + (total === 1 ? "" : "s") +
      " · page " + page + " of " + pages + "</span>" +
      '<div class="pager-btns">' +
      '<button class="btn btn-ghost btn-sm" id="pgPrev"' + (page <= 1 ? " disabled" : "") + ">&larr; Previous</button>" +
      '<button class="btn btn-ghost btn-sm" id="pgNext"' + (page >= pages ? " disabled" : "") + ">Next &rarr;</button></div>";
    var prev = $("#pgPrev"), next = $("#pgNext");
    if (prev) prev.addEventListener("click", function () { regState.offset = Math.max(0, regState.offset - regState.limit); loadRegistrations(); });
    if (next) next.addEventListener("click", function () { regState.offset += regState.limit; loadRegistrations(); });

    bindRegActions();
    updateSelCount();
  }

  function bindRegActions() {
    $$(".reg-check").forEach(function (cb) {
      cb.addEventListener("change", function () {
        if (cb.checked) regState.selected.add(cb.dataset.id);
        else regState.selected.delete(cb.dataset.id);
        updateSelCount();
      });
    });
    $$(".act-view").forEach(function (b) {
      b.addEventListener("click", function () { viewRegistration(b.dataset.id); });
    });
    $$(".act-edit").forEach(function (b) {
      b.addEventListener("click", function () { editRegistration(b.dataset.id); });
    });
    $$(".act-archive").forEach(function (b) {
      b.addEventListener("click", function () {
        confirmModal("Archive registration", "Archive " + b.dataset.id + "? It is hidden from lists but kept in the database. Archiving is safer than deleting.", "Archive", false, function () {
          api("POST", "/admin/api/registrations/" + b.dataset.id + "/archive").then(function () {
            toast("Archived " + b.dataset.id, "ok"); loadRegistrations();
          }).catch(function (e) { toast(e.message, "err"); });
        });
      });
    });
    $$(".act-unarchive").forEach(function (b) {
      b.addEventListener("click", function () {
        api("POST", "/admin/api/registrations/" + b.dataset.id + "/unarchive").then(function () {
          toast("Restored " + b.dataset.id, "ok"); loadRegistrations();
        }).catch(function (e) { toast(e.message, "err"); });
      });
    });
  }

  function updateSelCount() {
    $("#selCount").textContent = regState.selected.size;
    $("#exportSelectedBtn").disabled = regState.selected.size === 0;
  }

  ["regSearch", "regStatusFilter", "regProgramFilter", "regCountryFilter",
   "regDateFrom", "regDateTo", "regSort", "regArchived"].forEach(function (id) {
    var el = document.getElementById(id);
    if (!el) return;
    var evt = el.tagName === "SELECT" || el.type === "checkbox" || el.type === "date" ? "change" : "input";
    var debounce = null;
    el.addEventListener(evt, function () {
      clearTimeout(debounce);
      debounce = setTimeout(function () { regState.offset = 0; loadRegistrations(); }, 350);
    });
  });

  $("#exportFilteredBtn").addEventListener("click", function () {
    var params = regQueryParams();
    params.delete("limit"); params.delete("offset");
    window.location.href = "/admin/api/export.csv?" + params.toString();
  });
  $("#exportSelectedBtn").addEventListener("click", function () {
    if (!regState.selected.size) return;
    window.location.href = "/admin/api/export.csv?ids=" + Array.from(regState.selected).join(",");
    regState.selected.clear();
    updateSelCount();
  });

  function detailItem(label, value) {
    return '<div class="detail-item"><span class="detail-label">' + esc(label) +
      '</span><span class="detail-value">' + esc(value == null || value === "" ? "—" : value) + "</span></div>";
  }

  function viewRegistration(regId) {
    api("GET", "/admin/api/registrations/" + regId).then(function (data) {
      var r = data.registration;
      var history = (data.history || []).map(function (h) {
        return '<li><span class="h-action">' + esc(h.action) + "</span>" +
          (h.admin_email ? " · " + esc(h.admin_email) : "") + " · " + esc(fmtDate(h.created_at)) + "</li>";
      }).join("") || '<li class="muted">No recorded actions yet.</li>';

      openModal(
        '<div class="modal-head"><h3>' + esc(r.reg_id) + '</h3><button class="modal-close" type="button">&times;</button></div>' +
        '<div class="detail-grid">' +
        detailItem("Status", r.status) +
        detailItem("Submitted", fmtDate(r.created_at)) +
        detailItem("Student", r.full_name + " (" + r.age + ")") +
        detailItem("Country / City", (r.country || "—") + " / " + (r.city || "—")) +
        detailItem("Phone", r.phone) +
        detailItem("WhatsApp", r.whatsapp || "—") +
        detailItem("Email", r.email || "—") +
        detailItem("Program", r.program_name_snapshot) +
        detailItem("Monthly price (at registration)", r.monthly_price_snapshot === null ? "Contact us" : fmtPrice(r.monthly_price_snapshot, r.currency_snapshot)) +
        detailItem("Reading level", r.reading_level) +
        detailItem("Preferred schedule", r.preferred_schedule) +
        detailItem("Class format", r.class_format || "—") +
        detailItem("Parent / guardian", (r.parent_name || "—") + (r.parent_phone ? " · " + r.parent_phone : "")) +
        detailItem("Previous experience", r.previous_experience || "—") +
        detailItem("Learning goals", r.learning_goals || "—") +
        detailItem("Referral source", r.referral_source || "—") +
        detailItem("Sheets sync", r.sheets_sync_status + (r.sheets_synced_at ? " · " + fmtDate(r.sheets_synced_at) : "") +
          (r.sheets_sync_error ? " · " + r.sheets_sync_error : "")) +
        "</div>" +
        detailItem("Admin notes", r.admin_notes || "—") +
        '<h4 style="margin:1.2rem 0 0.6rem">Change status</h4>' +
        '<div class="status-btns">' +
        ["contacted", "confirmed", "active", "rejected", "cancelled", "new"].map(function (s) {
          return '<button class="btn btn-ghost btn-sm status-set" data-status="' + s + '"' +
            (r.status === s ? " disabled" : "") + ">" + esc(s) + "</button>";
        }).join("") + "</div>" +
        '<h4 style="margin:1.2rem 0 0.6rem">Recent history</h4>' +
        '<ul class="history-list">' + history + "</ul>" +
        '<div class="modal-actions">' +
        '<button class="btn btn-ghost" id="mEdit">Edit details</button>' +
        '<button class="btn btn-danger" id="mDelete">Delete permanently…</button></div>', true);

      $$(".status-set").forEach(function (b) {
        b.addEventListener("click", function () {
          api("POST", "/admin/api/registrations/" + regId + "/status", { status: b.dataset.status })
            .then(function () { toast("Status updated → " + b.dataset.status, "ok"); viewRegistration(regId); loadRegistrations(); })
            .catch(function (e) { toast(e.message, "err"); });
        });
      });
      $("#mEdit").addEventListener("click", function () { editRegistration(regId); });
      $("#mDelete").addEventListener("click", function () {
        confirmModal("Delete permanently",
          "Permanently delete " + regId + "? This cannot be undone. Archiving keeps the record — prefer it whenever possible.",
          "Delete forever", true, function () {
            openModal(
              '<div class="modal-head"><h3>Confirm deletion</h3><button class="modal-close" type="button">&times;</button></div>' +
              '<p class="muted">Type the registration ID <code>' + esc(regId) + "</code> to confirm permanent deletion.</p>" +
              '<div class="field"><input id="delConfirm" placeholder="' + esc(regId) + '"></div>' +
              '<div class="modal-actions"><button class="btn btn-ghost" id="mCancel2">Cancel</button>' +
              '<button class="btn btn-danger" id="mDelete2">Delete forever</button></div>');
            $("#mCancel2").addEventListener("click", closeModal);
            $("#mDelete2").addEventListener("click", function () {
              if ($("#delConfirm").value.trim() !== regId) { toast("Registration ID does not match.", "err"); return; }
              api("DELETE", "/admin/api/registrations/" + regId, { confirm: regId }).then(function () {
                toast("Deleted " + regId, "ok"); closeModal(); loadRegistrations();
              }).catch(function (e) { toast(e.message, "err"); });
            });
          });
      });
    }).catch(function (e) { toast(e.message, "err"); });
  }

  function editRegistration(regId) {
    api("GET", "/admin/api/registrations/" + regId).then(function (data) {
      var r = data.registration;
      function f(id, label, value, type) {
        return '<div class="field"><label>' + esc(label) + '</label><input id="' + id + '" type="' + (type || "text") + '" value="' + esc(value == null ? "" : value) + '"></div>';
      }
      openModal(
        '<div class="modal-head"><h3>Edit ' + esc(regId) + '</h3><button class="modal-close" type="button">&times;</button></div>' +
        '<p class="muted small">Program and the price snapshot never change — they are part of the historical record.</p>' +
        '<div class="field-row">' + f("ef-name", "Student full name", r.full_name) +
        f("ef-age", "Age", r.age, "number") + "</div>" +
        '<div class="field-row">' + f("ef-country", "Country", r.country) + f("ef-city", "City", r.city) + "</div>" +
        '<div class="field-row">' + f("ef-phone", "Phone", r.phone) + f("ef-whatsapp", "WhatsApp", r.whatsapp) + "</div>" +
        '<div class="field-row">' + f("ef-email", "Email", r.email, "email") + "</div>" +
        '<div class="field-row">' +
        '<div class="field"><label>Preferred schedule</label><select id="ef-schedule">' +
        ["Morning", "Afternoon", "Evening", "Flexible"].map(function (s) {
          return '<option' + (r.preferred_schedule === s ? " selected" : "") + ">" + s + "</option>";
        }).join("") + "</select></div>" +
        '<div class="field"><label>Reading level</label><select id="ef-level">' +
        ["Complete beginner", "Learning Arabic letters", "Can read slowly",
         "Can read but needs Tajweed improvement", "Intermediate", "Advanced",
         "Quran memorization (Hifz)"].map(function (s) {
          return '<option' + (r.reading_level === s ? " selected" : "") + ">" + s + "</option>";
        }).join("") + "</select></div></div>" +
        '<div class="field-row">' + f("ef-pname", "Parent/guardian name", r.parent_name) +
        f("ef-pphone", "Parent/guardian phone", r.parent_phone) + "</div>" +
        '<div class="field"><label>Admin notes (internal)</label><textarea id="ef-notes" rows="3">' + esc(r.admin_notes || "") + "</textarea></div>" +
        '<p class="field-error" id="ef-error" style="color:var(--danger);font-size:.85rem"></p>' +
        '<div class="modal-actions"><button class="btn btn-ghost" id="mCancel">Cancel</button>' +
        '<button class="btn btn-primary" id="mSave">Save changes</button></div>', true);
      $("#mCancel").addEventListener("click", closeModal);
      $("#mSave").addEventListener("click", function () {
        api("PATCH", "/admin/api/registrations/" + regId, {
          full_name: $("#ef-name").value.trim(),
          age: $("#ef-age").value.trim(),
          country: $("#ef-country").value.trim(),
          city: $("#ef-city").value.trim(),
          phone: $("#ef-phone").value.trim(),
          whatsapp: $("#ef-whatsapp").value.trim(),
          email: $("#ef-email").value.trim(),
          preferred_schedule: $("#ef-schedule").value,
          reading_level: $("#ef-level").value,
          parent_name: $("#ef-pname").value.trim(),
          parent_phone: $("#ef-pphone").value.trim(),
          admin_notes: $("#ef-notes").value,
        }).then(function () {
          toast("Saved. Google Sheets row will be updated.", "ok");
          closeModal(); loadRegistrations();
        }).catch(function (e) {
          $("#ef-error").textContent = e.message +
            (e.fieldErrors ? " (" + Object.values(e.fieldErrors).join(" ") + ")" : "");
        });
      });
    }).catch(function (e) { toast(e.message, "err"); });
  }

  // ------------------------------------------------------------ programs
  function loadPrograms() {
    api("GET", "/admin/api/programs").then(function (data) {
      var rows = data.programs.map(function (p) {
        return [
          esc(p.name) + (p.is_sample ? ' <span class="badge badge-sample">Sample</span>' : "") +
            '<div class="muted small">' + esc(p.slug) + "</div>",
          esc(p.description || "—"),
          p.monthly_price === null ? '<span class="badge badge-not_configured">Contact us</span>'
            : "<strong>" + esc(fmtPrice(p.monthly_price, p.currency)) + "</strong>",
          (p.active ? '<span class="badge badge-active">open</span>' : '<span class="badge badge-cancelled">closed</span>') +
            " " + (p.public_visible ? '<span class="badge badge-new">public</span>' : '<span class="badge badge-cancelled">hidden</span>') +
            '<div class="muted small">' + p.registration_count + " registration" + (p.registration_count === 1 ? "" : "s") + "</div>",
          '<div class="row-actions">' +
            '<button class="btn btn-ghost btn-sm prog-edit" data-id="' + p.id + '">Edit</button>' +
            '<button class="btn btn-ghost btn-sm prog-del" data-id="' + p.id + '" data-name="' + esc(p.name) + '">Delete</button></div>',
        ];
      });
      $("#programsTable").innerHTML = rows.length ? tableHTML(
        ["Program", "Description", "Monthly price", "Status", "Actions"], rows) :
        '<p class="muted">No programs yet.</p>';
      $$(".prog-edit").forEach(function (b) {
        b.addEventListener("click", function () { programModal(data.programs.find(function (p) { return p.id == b.dataset.id; })); });
      });
      $$(".prog-del").forEach(function (b) {
        b.addEventListener("click", function () {
          confirmModal("Delete program",
            'Delete "' + b.dataset.name + '" permanently? Programs with registrations cannot be deleted — deactivate instead.',
            "Delete program", true, function () {
              api("DELETE", "/admin/api/programs/" + b.dataset.id, { confirm: "yes" })
                .then(function () { toast("Program deleted", "ok"); loadPrograms(); })
                .catch(function (e) { toast(e.message, "err"); });
            });
        });
      });
    }).catch(function (e) { toast(e.message, "err"); });
  }
  $("#addProgramBtn").addEventListener("click", function () { programModal(null); });

  function programModal(p) {
    var isNew = !p;
    openModal(
      '<div class="modal-head"><h3>' + (isNew ? "New program" : "Edit program") + '</h3><button class="modal-close" type="button">&times;</button></div>' +
      '<div class="field"><label>Program name *</label><input id="pf-name" value="' + esc(p ? p.name : "") + '"></div>' +
      '<div class="field"><label>Short description</label><textarea id="pf-description" rows="2">' + esc(p ? p.description : "") + "</textarea></div>" +
      '<div class="field-row">' +
      '<div class="field"><label>Suitable level</label><input id="pf-level_info" value="' + esc(p ? p.level_info : "") + '"></div>' +
      '<div class="field"><label>Age group</label><input id="pf-age_group" value="' + esc(p ? p.age_group : "") + '"></div></div>' +
      '<div class="field-row">' +
      '<div class="field"><label>Monthly price (empty = "Contact us")</label><input id="pf-price" type="number" step="0.01" min="0" value="' + (p && p.monthly_price !== null ? p.monthly_price : "") + '"></div>' +
      '<div class="field"><label>Currency</label><input id="pf-currency" maxlength="3" value="' + esc(p ? p.currency : "ETB") + '"></div></div>' +
      '<div class="field-row">' +
      '<div class="field"><label>Lessons per week</label><input id="pf-lessons" type="number" min="1" max="7" value="' + (p && p.lessons_per_week ? p.lessons_per_week : "") + '"></div>' +
      '<div class="field"><label>Lesson duration (minutes)</label><input id="pf-duration" type="number" min="15" max="240" value="' + (p && p.lesson_duration_min ? p.lesson_duration_min : "") + '"></div></div>' +
      '<div class="field"><label>Class format</label><input id="pf-format" value="' + esc(p ? p.class_format : "Online classes") + '"></div>' +
      '<div class="field"><label>Included services (one per line)</label><textarea id="pf-services" rows="3">' + esc(p ? p.included_services : "") + "</textarea></div>" +
      '<label class="checkbox-label"><input type="checkbox" id="pf-active"' + (!p || p.active ? " checked" : "") + "> Registration open for this program</label> " +
      '<label class="checkbox-label"><input type="checkbox" id="pf-visible"' + (!p || p.public_visible ? " checked" : "") + "> Visible on the public website</label>" +
      '<p class="field-error" id="pf-error" style="color:var(--danger);font-size:.85rem"></p>' +
      '<div class="modal-actions"><button class="btn btn-ghost" id="mCancel">Cancel</button>' +
      '<button class="btn btn-primary" id="mSave">' + (isNew ? "Create program" : "Save changes") + "</button></div>", true);
    $("#mCancel").addEventListener("click", closeModal);
    $("#mSave").addEventListener("click", function () {
      var payload = {
        name: $("#pf-name").value.trim(),
        description: $("#pf-description").value.trim(),
        level_info: $("#pf-level_info").value.trim(),
        age_group: $("#pf-age_group").value.trim(),
        monthly_price: $("#pf-price").value === "" ? null : $("#pf-price").value,
        currency: $("#pf-currency").value.trim().toUpperCase(),
        lessons_per_week: $("#pf-lessons").value === "" ? null : $("#pf-lessons").value,
        lesson_duration_min: $("#pf-duration").value === "" ? null : $("#pf-duration").value,
        class_format: $("#pf-format").value.trim(),
        included_services: $("#pf-services").value,
        active: $("#pf-active").checked,
        public_visible: $("#pf-visible").checked,
      };
      api(isNew ? "POST" : "PATCH", "/admin/api/programs" + (isNew ? "" : "/" + p.id), payload)
        .then(function () { toast(isNew ? "Program created" : "Program saved", "ok"); closeModal(); loadPrograms(); })
        .catch(function (e) {
          $("#pf-error").textContent = e.message +
            (e.fieldErrors ? " (" + Object.values(e.fieldErrors).join(" ") + ")" : "");
        });
    });
  }

  // ------------------------------------------------------------ pricing
  function loadPricing() {
    api("GET", "/admin/api/pricing").then(function (data) {
      $("#discountNote").value = data.discount_note || "";
      var rows = data.programs.map(function (p) {
        return [
          esc(p.name),
          p.monthly_price === null ? '<span class="badge badge-not_configured">Not set — shows "Contact us"</span>'
            : "<strong>" + esc(p.monthly_price) + " " + esc(p.currency) + "</strong>",
          p.lessons_per_week || "—", p.lesson_duration_min ? p.lessons_per_week ? p.lesson_duration_min + " min" : p.lesson_duration_min + " min" : "—",
          p.public_visible ? '<span class="badge badge-new">shown</span>' : '<span class="badge badge-cancelled">hidden</span>',
          '<button class="btn btn-ghost btn-sm price-edit" data-id="' + p.id + '">Edit price</button>',
        ];
      });
      $("#pricingTable").innerHTML = rows.length ? tableHTML(
        ["Program", "Monthly price", "Lessons / week", "Duration", "Public display", ""], rows) :
        '<p class="muted">No programs yet.</p>';
      $$(".price-edit").forEach(function (b) {
        b.addEventListener("click", function () {
          var prog = data.programs.find(function (p) { return p.id == b.dataset.id; });
          openModal(
            '<div class="modal-head"><h3>Pricing — ' + esc(prog.name) + '</h3><button class="modal-close" type="button">&times;</button></div>' +
            '<div class="field-row">' +
            '<div class="field"><label>Monthly price (empty = "Contact us")</label><input id="prf-price" type="number" step="0.01" min="0" value="' + (prog.monthly_price !== null ? prog.monthly_price : "") + '"></div>' +
            '<div class="field"><label>Currency</label><input id="prf-currency" maxlength="3" value="' + esc(prog.currency) + '"></div></div>' +
            '<div class="field-row">' +
            '<div class="field"><label>Lessons per week</label><input id="prf-lessons" type="number" min="1" max="7" value="' + (prog.lessons_per_week || "") + '"></div>' +
            '<div class="field"><label>Lesson duration (min)</label><input id="prf-duration" type="number" min="15" max="240" value="' + (prog.lesson_duration_min || "") + '"></div></div>' +
            '<div class="field"><label>Included services (one per line)</label><textarea id="prf-services" rows="3">' + esc(prog.included_services || "") + "</textarea></div>" +
            '<label class="checkbox-label"><input type="checkbox" id="prf-visible"' + (prog.public_visible ? " checked" : "") + "> Show this program's price publicly</label>" +
            '<p class="muted small">Existing registrations keep the price that was displayed when the student registered.</p>' +
            '<p class="field-error" id="prf-error" style="color:var(--danger);font-size:.85rem"></p>' +
            '<div class="modal-actions"><button class="btn btn-ghost" id="mCancel">Cancel</button>' +
            '<button class="btn btn-primary" id="mSave">Save price</button></div>');
          $("#mCancel").addEventListener("click", closeModal);
          $("#mSave").addEventListener("click", function () {
            api("PATCH", "/admin/api/programs/" + prog.id, {
              monthly_price: $("#prf-price").value === "" ? null : $("#prf-price").value,
              currency: $("#prf-currency").value.trim().toUpperCase(),
              lessons_per_week: $("#prf-lessons").value === "" ? null : $("#prf-lessons").value,
              lesson_duration_min: $("#prf-duration").value === "" ? null : $("#prf-duration").value,
              included_services: $("#prf-services").value,
              public_visible: $("#prf-visible").checked,
            }).then(function () { toast("Price saved", "ok"); closeModal(); loadPricing(); })
              .catch(function (e) {
                $("#prf-error").textContent = e.message +
                  (e.fieldErrors ? " (" + Object.values(e.fieldErrors).join(" ") + ")" : "");
              });
          });
        });
      });
    }).catch(function (e) { toast(e.message, "err"); });
  }
  $("#saveDiscountNote").addEventListener("click", function () {
    api("PUT", "/admin/api/pricing/settings", { discount_note: $("#discountNote").value })
      .then(function () { toast("Note saved", "ok"); })
      .catch(function (e) { toast(e.message, "err"); });
  });

  // ------------------------------------------------------------ content
  var aboutSections = [];

  function loadContent() {
    api("GET", "/admin/api/settings").then(function (data) {
      var s = data.settings;
      var map = {
        "set-academy_name": s.academy_name, "set-academy_tagline": s.academy_tagline,
        "set-hero_headline": s.hero_headline, "set-hero_text": s.hero_text,
        "set-announcement_text": s.announcement_text,
        "set-contact_email": s.contact_email, "set-contact_phone": s.contact_phone,
        "set-whatsapp_number": s.whatsapp_number, "set-working_hours": s.working_hours,
        "set-telegram_link": s.telegram_link, "set-facebook_link": s.facebook_link,
        "set-instagram_link": s.instagram_link, "set-youtube_link": s.youtube_link,
      };
      Object.keys(map).forEach(function (id) {
        var el = document.getElementById(id);
        if (el) el.value = map[id] == null ? "" : map[id];
      });
      var annToggle = document.getElementById("set-announcement_enabled");
      if (annToggle) annToggle.checked = !!s.announcement_enabled;

      aboutSections = Array.isArray(s.about_sections) ? s.about_sections.slice() : [];
      renderAboutEditor();

      var logo = $("#logoPreview");
      if (s.logo_url) { logo.src = s.logo_url; logo.hidden = false; }
      else logo.hidden = true;
    }).catch(function (e) { toast(e.message, "err"); });
  }

  function renderAboutEditor() {
    var editor = $("#aboutEditor");
    editor.innerHTML = aboutSections.map(function (s, i) {
      return '<div class="about-edit-item" data-i="' + i + '">' +
        '<div class="field"><label>Section title</label><input class="ae-title" value="' + esc(s.title) + '"></div>' +
        '<div class="field"><label>Section text</label><textarea class="ae-body" rows="3">' + esc(s.body) + "</textarea></div>" +
        '<div class="editor-row"><button class="btn btn-ghost btn-sm ae-remove">Remove section</button></div></div>';
    }).join("") || '<p class="muted">No sections yet.</p>';
    $$(".ae-remove", editor).forEach(function (b) {
      b.addEventListener("click", function () {
        var i = +b.closest(".about-edit-item").dataset.i;
        aboutSections.splice(i, 1);
        renderAboutEditor();
      });
    });
  }
  $("#addSectionBtn").addEventListener("click", function () {
    aboutSections.push({ title: "New section", body: "" });
    renderAboutEditor();
  });

  $("#saveContentBtn").addEventListener("click", function () {
    // gather about sections from the editor
    aboutSections = $$("#aboutEditor .about-edit-item").map(function (item) {
      return {
        title: $(".ae-title", item).value.trim(),
        body: $(".ae-body", item).value.trim(),
      };
    }).filter(function (s) { return s.title; });

    var payload = {
      academy_name: $("#set-academy_name").value.trim(),
      academy_tagline: $("#set-academy_tagline").value.trim(),
      hero_headline: $("#set-hero_headline").value.trim(),
      hero_text: $("#set-hero_text").value.trim(),
      announcement_text: $("#set-announcement_text").value.trim(),
      announcement_enabled: $("#set-announcement_enabled").checked,
      contact_email: $("#set-contact_email").value.trim(),
      contact_phone: $("#set-contact_phone").value.trim(),
      whatsapp_number: $("#set-whatsapp_number").value.trim(),
      working_hours: $("#set-working_hours").value.trim(),
      telegram_link: $("#set-telegram_link").value.trim(),
      facebook_link: $("#set-facebook_link").value.trim(),
      instagram_link: $("#set-instagram_link").value.trim(),
      youtube_link: $("#set-youtube_link").value.trim(),
      about_sections: aboutSections,
    };
    api("PUT", "/admin/api/settings", payload)
      .then(function () { toast("Website content saved", "ok"); })
      .catch(function (e) {
        toast(e.message + (e.fieldErrors ? " (" + Object.values(e.fieldErrors).join(" ") + ")" : ""), "err");
      });
  });

  $("#uploadLogoBtn").addEventListener("click", function () {
    var file = $("#logoFile").files[0];
    if (!file) { toast("Choose an image file first.", "err"); return; }
    var fd = new FormData();
    fd.append("logo", file);
    fetch("/admin/api/settings/logo", {
      method: "POST", body: fd, credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    }).then(function (resp) { return resp.json(); }).then(function (data) {
      if (data.error) { toast(data.error, "err"); return; }
      toast("Logo updated", "ok");
      var logo = $("#logoPreview");
      logo.src = data.logo_url; logo.hidden = false;
      $("#logoFile").value = "";
    }).catch(function () { toast("Upload failed", "err"); });
  });

  // ------------------------------------------------------------ FAQs
  function loadFaqs() {
    api("GET", "/admin/api/faqs").then(function (data) {
      var editor = $("#faqEditor");
      editor.innerHTML = data.faqs.map(function (f) {
        return '<div class="faq-edit-item" data-id="' + f.id + '">' +
          '<div class="field"><label>Question</label><input class="fq-q" value="' + esc(f.question) + '"></div>' +
          '<div class="field"><label>Answer</label><textarea class="fq-a" rows="3">' + esc(f.answer) + "</textarea></div>" +
          '<div class="editor-row">' +
          '<label class="checkbox-label"><input type="checkbox" class="fq-v"' + (f.visible ? " checked" : "") + "> Visible</label>" +
          '<span class="muted small">Order: ' + f.sort_order + "</span>" +
          '<button class="btn btn-ghost btn-sm fq-save">Save</button>' +
          '<button class="btn btn-ghost btn-sm fq-del">Delete</button></div></div>';
      }).join("") || '<p class="muted">No FAQs yet.</p>';
      $$(".fq-save").forEach(function (b) {
        b.addEventListener("click", function () {
          var item = b.closest(".faq-edit-item");
          api("PATCH", "/admin/api/faqs/" + item.dataset.id, {
            question: $(".fq-q", item).value, answer: $(".fq-a", item).value,
            visible: $(".fq-v", item).checked,
          }).then(function () { toast("FAQ saved", "ok"); })
            .catch(function (e) { toast(e.message, "err"); });
        });
      });
      $$(".fq-del").forEach(function (b) {
        b.addEventListener("click", function () {
          var item = b.closest(".faq-edit-item");
          confirmModal("Delete FAQ", "Delete this question permanently?", "Delete", true, function () {
            api("DELETE", "/admin/api/faqs/" + item.dataset.id)
              .then(function () { toast("FAQ deleted", "ok"); loadFaqs(); })
              .catch(function (e) { toast(e.message, "err"); });
          });
        });
      });
    }).catch(function (e) { toast(e.message, "err"); });
  }
  $("#addFaqBtn").addEventListener("click", function () {
    openModal(
      '<div class="modal-head"><h3>New FAQ</h3><button class="modal-close" type="button">&times;</button></div>' +
      '<div class="field"><label>Question *</label><input id="nfq-q"></div>' +
      '<div class="field"><label>Answer *</label><textarea id="nfq-a" rows="4"></textarea></div>' +
      '<p class="field-error" id="nfq-error" style="color:var(--danger);font-size:.85rem"></p>' +
      '<div class="modal-actions"><button class="btn btn-ghost" id="mCancel">Cancel</button>' +
      '<button class="btn btn-primary" id="mSave">Create</button></div>');
    $("#mCancel").addEventListener("click", closeModal);
    $("#mSave").addEventListener("click", function () {
      api("POST", "/admin/api/faqs", { question: $("#nfq-q").value, answer: $("#nfq-a").value })
        .then(function () { toast("FAQ created", "ok"); closeModal(); loadFaqs(); })
        .catch(function (e) { $("#nfq-error").textContent = e.message; });
    });
  });

  // ------------------------------------------------------------ messages
  function loadMessages() {
    api("GET", "/admin/api/messages").then(function (data) {
      var list = $("#messagesList");
      list.innerHTML = data.messages.map(function (m) {
        return '<div class="message-item' + (m.is_read ? "" : " unread") + '" data-id="' + m.id + '">' +
          '<div class="message-head"><strong>' + esc(m.name) + "</strong>" +
          '<span class="message-meta">' + esc(fmtDate(m.created_at)) + "</span></div>" +
          '<div class="message-meta">' + esc(m.email || "") + (m.phone ? " · " + esc(m.phone) : "") + "</div>" +
          '<div class="message-body">' + esc(m.message) + "</div>" +
          '<div class="editor-row">' +
          (m.is_read ? "" : '<button class="btn btn-ghost btn-sm msg-read">Mark as read</button>') +
          '<button class="btn btn-ghost btn-sm msg-del">Delete</button></div></div>';
      }).join("") || '<p class="muted">No messages yet.</p>';
      $$(".msg-read").forEach(function (b) {
        b.addEventListener("click", function () {
          var item = b.closest(".message-item");
          api("POST", "/admin/api/messages/" + item.dataset.id + "/read")
            .then(function () { loadMessages(); loadOverview(); })
            .catch(function (e) { toast(e.message, "err"); });
        });
      });
      $$(".msg-del").forEach(function (b) {
        b.addEventListener("click", function () {
          var item = b.closest(".message-item");
          confirmModal("Delete message", "Delete this contact message permanently?", "Delete", true, function () {
            api("DELETE", "/admin/api/messages/" + item.dataset.id)
              .then(function () { toast("Message deleted", "ok"); loadMessages(); })
              .catch(function (e) { toast(e.message, "err"); });
          });
        });
      });
    }).catch(function (e) { toast(e.message, "err"); });
  }

  // ------------------------------------------------------------ sheets
  function loadSheets() {
    api("GET", "/admin/api/sheets/status").then(function (s) {
      var card = $("#sheetsStatusCard");
      var html = "<h3>Google Sheets synchronization</h3>";
      if (s.configured) {
        html += integrationRow("Status", "Connected", "ok") +
          integrationRow("Spreadsheet worksheet", s.worksheet) +
          integrationRow("Synced registrations", s.synced_registrations) +
          integrationRow("Pending jobs", s.pending) +
          integrationRow("Failed jobs", s.failed) +
          integrationRow("Last successful sync", s.last_success_at ? fmtDate(s.last_success_at) : "—") +
          (s.last_error ? integrationRow("Last error", s.last_error, "err") : "");
      } else {
        html += integrationRow("Status", "Not configured", "err") +
          '<p class="muted small">Registrations are saved safely in the database either way — the queue waits until Google Sheets is configured, and nothing is lost.</p>' +
          '<ol class="setup-steps">' +
          "<li>Create a Google Cloud service account with the Sheets API enabled.</li>" +
          "<li>Download its JSON key.</li>" +
          '<li>Create the spreadsheet <strong>Online Quran Academy — Student Registrations</strong> and share it with the service account email (Editor).</li>' +
          "<li>Set <code>GOOGLE_SHEET_ID</code>, <code>GOOGLE_SERVICE_ACCOUNT_EMAIL</code> and <code>GOOGLE_PRIVATE_KEY</code> in the <code>.env</code> file, then restart.</li>" +
          "</ol>" +
          '<p class="muted small">Missing variables: ' + esc(s.missing_vars.join(", ") || "none") + "</p>";
      }
      card.innerHTML = html;
    }).catch(function (e) { toast(e.message, "err"); });
  }

  $("#syncNowBtn").addEventListener("click", function () {
    var btn = $("#syncNowBtn");
    btn.disabled = true;
    api("POST", "/admin/api/sheets/sync").then(function (data) {
      var st = data.stats;
      toast("Sync finished: " + st.succeeded + " sent, " + st.failed + " failed, " + st.skipped + " skipped", "ok");
      loadSheets();
    }).catch(function (e) { toast(e.message, "err"); })
      .finally(function () { btn.disabled = false; });
  });
  $("#retryFailedBtn").addEventListener("click", function () {
    api("POST", "/admin/api/sheets/retry-failed").then(function (data) {
      toast("Retried " + data.reset + " failed job(s): " + data.stats.succeeded + " succeeded", "ok");
      loadSheets();
    }).catch(function (e) { toast(e.message, "err"); });
  });

  // ------------------------------------------------------------ audit
  function loadAudit() {
    api("GET", "/admin/api/audit").then(function (data) {
      var rows = data.entries.map(function (a) {
        return [
          esc(fmtDate(a.created_at)),
          "<strong>" + esc(a.action) + "</strong>",
          esc(a.admin_email || "—"),
          esc((a.entity_type || "") + (a.entity_id ? " · " + a.entity_id : "")),
          '<span class="muted small">' + esc(a.details || "") + "</span>",
        ];
      });
      $("#auditTable").innerHTML = rows.length ? tableHTML(
        ["When", "Action", "Admin", "Entity", "Details"], rows) :
        '<p class="muted">No entries yet.</p>';
    }).catch(function (e) { toast(e.message, "err"); });
  }

  // ------------------------------------------------------------ account
  $("#changePwBtn").addEventListener("click", function () {
    var cur = $("#pwCurrent").value, nw = $("#pwNew").value;
    if (!cur || !nw) { toast("Fill in both fields.", "err"); return; }
    api("POST", "/admin/api/change-password", { current_password: cur, new_password: nw })
      .then(function () {
        toast("Password changed. Signing out…", "ok");
        setTimeout(function () {
          var f = document.createElement("form");
          f.method = "post"; f.action = "/admin/logout";
          document.body.appendChild(f); f.submit();
        }, 1200);
      })
      .catch(function (e) { toast(e.message, "err"); });
  });

  // ------------------------------------------------------------ start
  loadOverview();
})();
