// Copy Registration ID button on the confirmation page.
(function () {
  "use strict";
  var btn = document.getElementById("copyRegId");
  var regId = document.getElementById("regId");
  if (!btn || !regId) return;
  btn.addEventListener("click", function () {
    var text = regId.textContent.trim();
    function done(ok) {
      btn.textContent = ok ? "Copied ✓" : "Copy failed — select it manually";
      setTimeout(function () { btn.textContent = "Copy Registration ID"; }, 2200);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(false); });
    } else {
      var range = document.createRange();
      range.selectNodeContents(regId);
      var sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      try { done(document.execCommand("copy")); } catch (e) { done(false); }
      sel.removeAllRanges();
    }
  });
})();
