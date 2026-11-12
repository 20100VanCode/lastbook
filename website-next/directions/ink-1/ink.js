// Lastbook ink hero: the crowd walks, sways and talks; the O-eyes read the little book.
// With JavaScript off, or with reduced motion asked for, the drawing stays still.
(function () {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  var hero = document.querySelector(".hero");
  if (!hero) return;
  var R = Math.random, now = performance.now.bind(performance);
  var running = true, seen = true;

  // ---- line boil: three noise seeds, about 6 frames a second
  var turb = [document.getElementById("boil-t"), document.getElementById("brush-t")];
  var seeds = [2, 7, 12], si = 0, lastBoil = 0;

  // ---- figures
  var figs = [].slice.call(hero.querySelectorAll(".fig")).map(function (el) {
    var range = +el.getAttribute("data-walk") || 0;
    return {
      el: el, svg: el.querySelector("svg"), bub: el.querySelector(".bub"),
      range: range, x: (R() - .5) * range, dir: R() < .5 ? -1 : 1,
      speed: 14 + R() * 8, phase: R() * 6.28, step: 0, lastStep: 0,
      say: el.hasAttribute("data-say") ? +el.getAttribute("data-say") : 99,
      reader: el.classList.contains("p-reader")
    };
  });
  figs.forEach(function (f) { if (f.bub) f.bub.classList.remove("on"); });

  // ---- talk: a little story, then anyone may chip in
  var story = figs.filter(function (f) { return f.say < 99; }).sort(function (a, b) { return a.say - b.say; });
  var chatter = figs.filter(function (f) { return f.bub && f.say === 99; });
  var si2 = 0, nextTalk = now() + 600, shown = [];
  function visible(f) { return f.el.offsetParent !== null; }
  function talk(t) {
    shown = shown.filter(function (s) { return s.until > t || (s.f.bub.classList.remove("on"), false); });
    if (t < nextTalk || shown.length >= 3) return;
    var f, tries = 0;
    do {
      f = (si2 < story.length) ? story[si2++] : (R() < .7 ? story[(R() * story.length) | 0] : chatter[(R() * chatter.length) | 0]);
      if (si2 >= story.length && R() < .25) si2 = 0;
    } while (f && (!visible(f) || shown.some(function (s) { return s.f === f; })) && ++tries < 12);
    if (!f || !visible(f)) return;
    f.bub.classList.add("on");
    shown.push({ f: f, until: t + 2200 + R() * 1000 });
    nextTalk = t + 900 + R() * 500;
  }

  // ---- the O-eyes
  var pupils = [].slice.call(document.querySelectorAll(".word .pupil"));
  var lids = [].slice.call(document.querySelectorAll(".word .lid"));
  var nextBlink = now() + 2500, blinkAt = -1, glanceAt = now() + 9000;
  function eyes(t) {
    // read along a line: glide right over 2.4 s, snap back, next line down
    var cyc = (t % 2400) / 2400, line = Math.floor(t / 2400) % 3;
    var gx = cyc < .95 ? -9 + 18 * (cyc / .95) : 9 - 18 * ((cyc - .95) / .05);
    var gy = line * 3 - 2;
    if (t > glanceAt && t < glanceAt + 700) { gx = 4; gy = -40; }
    else if (t >= glanceAt + 700) glanceAt = t + 13000 + R() * 5000;
    for (var i = 0; i < pupils.length; i++) pupils[i].style.transform = "translate(" + gx.toFixed(1) + "px," + gy + "px)";
    if (t > nextBlink) { blinkAt = t; nextBlink = t + 4000 + R() * 3000; }
    var b = blinkAt < 0 ? 0 : (t - blinkAt) / 170, lid = 0;
    if (b >= 0 && b < 1) lid = b < .5 ? b * 2 : 2 - b * 2;
    for (var j = 0; j < lids.length; j++) lids[j].style.transform = "scaleY(" + lid.toFixed(2) + ")";
  }

  // ---- giant lantern sways on its rope
  var lamp = document.querySelector(".lamp svg");

  var last = now();
  function frame(t) {
    if (!running) return;
    var dt = Math.min(.05, (t - last) / 1000); last = t;
    if (t - lastBoil > 160) {
      si = (si + 1) % 3; lastBoil = t;
      turb[0] && turb[0].setAttribute("seed", seeds[si]);
      turb[1] && turb[1].setAttribute("seed", seeds[si] + 3);
    }
    for (var i = 0; i < figs.length; i++) {
      var f = figs[i];
      if (f.range) {
        f.x += f.dir * f.speed * dt;
        if (Math.abs(f.x) > f.range / 2) { f.x = f.dir * f.range / 2; f.dir = -f.dir; }
        if (t - f.lastStep > 220) { f.step ^= 1; f.lastStep = t; f.el.classList.toggle("step", !!f.step); }
        f.el.style.transform = "translate(" + f.x.toFixed(1) + "px," + (f.step ? -2 : 0) + "px)";
        f.svg.style.transform = f.dir < 0 ? "scaleX(-1)" : "";
      } else {
        var a = Math.sin(t / 3000 * 6.283 + f.phase) * 1.5;
        f.svg.style.transform = "rotate(" + a.toFixed(2) + "deg)";
        if (f.reader) f.el.classList.toggle("turn", (t % 4000) < 380);
      }
    }
    if (lamp) lamp.style.transform = "rotate(" + (Math.sin(t / 2600) * 1.6).toFixed(2) + "deg)";
    eyes(t);
    talk(t);
    requestAnimationFrame(frame);
  }
  function setRun() {
    var go = seen && !document.hidden;
    if (go && !running) { running = true; last = now(); requestAnimationFrame(frame); }
    running = go;
  }
  document.addEventListener("visibilitychange", setRun);
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (e) { seen = e[0].isIntersecting; setRun(); }).observe(hero);
  }
  requestAnimationFrame(frame);
})();
