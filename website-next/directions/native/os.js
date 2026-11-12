// Lastbook: pick the main download button for this computer.
// Without this script both buttons show side by side, which is fine.
(function () {
  var ua = navigator.userAgent || "";
  var plat = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "";
  var phone = /Android|iPhone|iPod/i.test(ua) || (/iPad/.test(ua)) ||
              (/Mac/.test(plat) && navigator.maxTouchPoints > 1); // iPad asking for desktop pages
  var os = phone ? "phone" : /Win/i.test(plat + ua) ? "win" : /Mac/i.test(plat + ua) ? "mac" : "";
  var dl = document.getElementById("dl");
  if (!dl || !os) return;
  dl.setAttribute("data-os", os);
  if (os === "phone") {
    document.getElementById("phone-note").hidden = false;
    return;
  }
  var main = dl.querySelector(os === "win" ? ".dl-win" : ".dl-mac");
  var other = dl.querySelector(os === "win" ? ".dl-mac" : ".dl-win");
  dl.insertBefore(main, dl.firstChild);
  other.classList.add("dl-other");
  var p = document.createElement("p");
  p.className = "fine wrong";
  var a = document.createElement("a");
  a.href = other.querySelector("a").href;
  a.textContent = os === "win" ? "Download for Mac instead" : "Download for Windows instead";
  p.appendChild(document.createTextNode("Wrong computer? "));
  p.appendChild(a);
  other.replaceChildren(p);
})();
