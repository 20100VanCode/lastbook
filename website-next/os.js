// Lastbook: mark the page with this computer's system, before it is drawn.
// The CSS then puts that download first. With this script off, both show equally.
(function () {
  var d = document.documentElement, n = navigator, ua = n.userAgent || "";
  var p = (n.userAgentData && n.userAgentData.platform) || n.platform || "";
  d.className += " js";
  var phone = /Android|iPhone|iPod|iPad/i.test(ua) || (/Mac/.test(p) && n.maxTouchPoints > 1);
  var os = phone ? "phone" : /Win/i.test(p + ua) ? "win" : /Mac/i.test(p + ua) ? "mac" : "";
  if (os) d.setAttribute("data-os", os);
  // CSS already draws Windows first; this moves it first in the page too,
  // so keyboard and screen-reader order match what is on screen.
  if (os === "win") document.addEventListener("DOMContentLoaded", function () {
    var els = document.querySelectorAll(".dl-win");
    for (var i = 0; i < els.length; i++) els[i].parentNode.insertBefore(els[i], els[i].parentNode.firstElementChild);
    // In the home hero the solid button goes to Windows, the outlined one to Mac.
    var m = document.querySelector(".dl .dl-mac a"), w = document.querySelector(".dl .dl-win a");
    if (m && w) { m.className = "btn-2"; w.className = "btn"; }
    // The Windows screenshot waits in a <template>, so no one else downloads it.
    // Only wide windows get it; narrow ones keep the phone-width shot.
    var t = document.getElementById("hero-win");
    if (t && t.content && window.matchMedia("(min-width: 601px)").matches) {
      t.parentNode.appendChild(t.content.cloneNode(true));
      t.parentNode.className += " has-win";
    }
  });
})();
