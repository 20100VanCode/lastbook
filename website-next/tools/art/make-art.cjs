// Draws Lastbook's small ink pictures (figures, doodle icons, the eye-book mark)
// as static SVG files in img/ink/, with the same hand-jittered pen as the home crowd.
// Every run gives the same drawings (fixed seeds).
//   usage: node tools/art/make-art.cjs
"use strict";
const fs = require("fs"), path = require("path");
const K = require("../../crowd.js");
const { Pen, SvgOut, DRAW, rng, rect, ell, hatch, legs, body, head, arm, book, C } = K;
const OUT = path.join(__dirname, "../../img/ink");
fs.mkdirSync(OUT, { recursive: true });
const PI = Math.PI;

function svg(name, vb, draw, seed, extra) {
  const o = SvgOut(), p = new Pen(o);
  p.r = rng(seed || 7);
  draw(p, o);
  const s = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="' + vb.join(" ") + '" fill="none" stroke-linecap="round" stroke-linejoin="round"' + (extra || "") + ">" +
    (o.defs.length ? "<defs>" + o.defs.join("") + "</defs>" : "") + o.parts.join("") + "</svg>";
  fs.writeFileSync(path.join(OUT, name + ".svg"), s);
  return s.length;
}
function arc(cx, cy, rx, ry, a0, a1, n) { const q = []; for (let i = 0; i <= n; i++) { const a = a0 + (a1 - a0) * i / n; q.push([cx + rx * Math.cos(a), cy + ry * Math.sin(a)]); } return q; }
const INK = C.INK, W = C.WHITE, CREAM = C.CREAM, LAMP = C.LAMP, AID = C.AID, WATER = C.WATER, H = C.HATCH;
const sizes = {};

/* ---------------- figures ---------------- */
// people are white with soft grey lines, like the home crowd; only the wordmark and buttons are black ink
const LINE = "#6B6B66", SHIRT = "#9C9B94";
function soft(draw) { return function (p, o) { p.fade = LINE; p.soft = 1; draw(p, o); p.fade = null; p.soft = 0; }; }
function person(kind, opt) {
  return soft(function (p) {
    const F = Object.assign({ fill: W, dir: 1 }, opt);
    p.save(); if (F.dir < 0) p.sc(-1, 1);
    DRAW[kind](p, F, { t: 0, walk: false, bob: 0, turn: 0 });
    p.restore();
  });
}
const FIG_VB = [-40, -96, 86, 104];
[["reader", {}], ["lantern", { hat: "beanie", shirt: SHIRT }], ["jug", { hat: "scarf" }], ["aid", { shirt: SHIRT }], ["laptop", { shirt: SHIRT }],
 ["radio", { hat: "cap", mouthO: 1 }], ["garden", { hat: "straw" }], ["kid", { shirt: SHIRT }], ["phone", { mouthO: 1, shirt: SHIRT }]].forEach(([k, o], i) => {
  sizes["fig-" + k] = svg("fig-" + k, FIG_VB, person(k, o), 101 + i * 13);
});

function waver(p, F, up) {
  F = Object.assign({ fill: W }, F);
  p.shadow(10, 1, 17, 5.5, .14);
  legs(p, { walk: false, t: 0 });
  body(p, F, -29, 13, 16);
  arm(p, [[-10, -36], [-14, -27], [-12, -20]]);
  head(p, F, 1, -55, F.look || [1.5, 0]);
  if (up) { arm(p, [[10, -38], [19, -48], [22, -62]]); p.dot(22.5, -64, 3.2); p.line([[27, -70], [31, -73]], 1.8); p.line([[29, -63], [34, -63]], 1.8); p.line([[17, -72], [17, -77]], 1.8); }
  else arm(p, [[10, -36], [14, -27], [12, -20]]);
}
// footer: three people waving on the line
sizes["foot-crowd"] = svg("foot-crowd", [-34, -96, 210, 104], soft((p) => {
  p.save(); p.tr(0, 0); waver(p, { hat: "cap", fill: CREAM }, 1); p.restore();
  p.save(); p.tr(66, 0); p.sc(.9); waver(p, { hat: "scarf", look: [0, 1] }, 0); p.restore();
  p.save(); p.tr(136, 0); p.sc(-1, 1); waver(p, { hat: "beanie", look: [2, -1], shirt: SHIRT }, 1); p.restore();
}), 31);

// closing band: one person hands a book to another
sizes["pair-book"] = svg("pair-book", [-36, -92, 150, 100], soft((p) => {
  p.save();
  const A = { fill: W, hat: "beanie" };
  p.shadow(10, 1, 17, 5.5, .14); legs(p, { t: 0 }); body(p, A, -29, 13, 16);
  arm(p, [[-10, -36], [-14, -27], [-12, -20]]); head(p, A, 1, -55, [3, 1.4]);
  arm(p, [[10, -37], [24, -34], [36, -36]]);
  p.restore();
  // the book between them, closed, a little tilted
  p.save(); p.tr(42, -40); p.rot(-.12);
  p.shape(rect(-9, -8, 18, 14, 2), { close: 1, fill: LAMP, w: 2.6 });
  p.line([[-6, -8], [-6, 6]], 2); p.line([[-2, -3], [6, -3]], 1.4, H); p.line([[-2, 0], [5, 0]], 1.4, H);
  p.restore();
  p.save(); p.tr(86, 0); p.sc(-1, 1);
  const B = { fill: CREAM };
  p.shadow(10, 1, 17, 5.5, .14); legs(p, { t: 0 }); body(p, B, -29, 13, 16);
  arm(p, [[-10, -36], [-14, -27], [-12, -20]]); head(p, B, 1, -55, [3, .4]);
  arm(p, [[10, -37], [22, -40], [34, -42]]);
  p.restore();
}), 47);

// 404: a person holding an open book upside down, a question mark above
sizes["fig-lost"] = svg("fig-lost", [-40, -108, 88, 116], soft((p) => {
  const F = { fill: W, hat: "cap", mouthO: 1 };
  p.shadow(10, 1, 17, 5.5, .14); legs(p, { t: 0 }); body(p, F, -29, 13, 16);
  head(p, F, 1, -55, [1.5, 3.4]);
  arm(p, [[-10, -37], [-6, -27], [4, -26]]); arm(p, [[10, -37], [22, -32], [22, -26]]);
  p.save(); p.tr(13, -28); p.rot(PI); book(p, 0, 0, 1.1, 0); p.restore();
  p.line(arc(22, -94, 7, 7, -PI * 1.05, PI * .35, 8).concat([[24, -82], [24, -79]]), 3);
  p.dot(24, -72, 2);
}), 59);

// a doodle hand pointing right, for the screenshot card
sizes["hand-point"] = svg("hand-point", [0, 0, 96, 60], (p) => {
  p.shape([[4, 18], [22, 16], [22, 46], [4, 46]], { close: 1, fill: W, w: 3 });
  p.shape([[22, 20], [34, 14], [46, 16], [84, 17], [90, 21], [86, 26], [56, 27], [58, 31], [57, 36], [54, 40], [55, 44], [51, 48], [30, 48], [22, 44]], { close: 1, fill: W, w: 3 });
  p.line([[40, 27], [56, 28]], 2); p.line([[40, 33], [57, 34]], 2); p.line([[40, 40], [54, 40]], 2);
  p.line([[26, 22], [26, 42]], 1.4, H); p.line([[30, 24], [30, 44]], 1.4, H);
}, 71);

/* ---------------- icons (stroke 2.5, 64 grid) ---------------- */
const I = [0, 0, 64, 64];
function ico(name, draw, seed) { sizes[name] = svg(name, I, (p) => { p.amp = .55; draw(p); }, seed); }
ico("d-laptop", (p) => {
  p.shape(rect(12, 12, 40, 28, 3), { close: 1, fill: W, w: 3 });
  p.ell(32, 25, 6, 6, { w: 2.4 }, 12); p.dot(32, 27, 2.4);
  p.shape([[6, 44], [58, 44], [54, 52], [10, 52]], { close: 1, fill: W, w: 3 });
  p.line([[26, 48], [38, 48]], 2);
}, 3);
ico("d-box", (p) => {
  p.shape([[10, 22], [32, 12], [54, 22], [54, 46], [32, 56], [10, 46]], { close: 1, fill: CREAM, w: 3 });
  p.line([[10, 22], [32, 32], [54, 22]], 3); p.line([[32, 32], [32, 56]], 3);
  p.line([[21, 17], [43, 27], [43, 37]], 2.2);
  p.line([[38, 40], [48, 35]], 1.4, H); p.line([[38, 46], [48, 41]], 1.4, H);
}, 5);
ico("d-zip", (p) => {
  p.shape([[12, 10], [40, 10], [52, 22], [52, 54], [12, 54]], { close: 1, fill: W, w: 3 });
  p.line([[40, 10], [40, 22], [52, 22]], 2.4);
  for (let y = 12; y < 40; y += 6) { p.line([[26, y], [30, y]], 2.2); p.line([[30, y + 3], [34, y + 3]], 2.2); }
  p.shape(rect(25, 40, 10, 9, 2), { close: 1, fill: INK, amp: .3 });
  p.line([[56, 30], [60, 26]], 2); p.line([[57, 38], [62, 38]], 2);
}, 9);
ico("d-tick", (p) => { p.line([[12, 34], [26, 48], [54, 14]], 5); }, 11);
ico("d-plus", (p) => { p.line([[32, 14], [32, 50]], 4.5); p.line([[14, 32], [50, 32]], 4.5); }, 13);
ico("d-bang", (p) => { p.ell(32, 32, 24, 24, { fill: LAMP, w: 3.2 }, 24); p.line([[32, 17], [32, 37]], 5); p.dot(32, 46, 3.4); }, 15);
ico("d-bang-red", (p) => { p.ell(32, 32, 24, 24, { fill: W, w: 3.2, col: AID }, 24); p.line([[32, 17], [32, 37]], 5, AID); p.dot(32, 46, 3.4, AID); }, 16);
ico("d-caret", (p) => { p.line([[22, 14], [42, 32], [22, 50]], 5); }, 17);
ico("d-circle", (p) => { p.ell(32, 32, 27, 26, { fill: W, w: 3 }, 26, .2); }, 19);
ico("d-dot", (p) => { p.ell(32, 32, 9, 8, { fill: INK, amp: .8 }, 10); }, 21);
ico("d-arrow", (p) => { p.line([[8, 34], [24, 30], [42, 33], [56, 31]], 3.5); p.line([[44, 20], [56, 31], [45, 43]], 3.5); }, 23);

// topics (library page)
ico("t-aid", (p) => {
  p.line([[24, 16], [25, 10], [39, 10], [40, 16]], 3);
  p.shape(rect(8, 16, 48, 36, 5), { close: 1, fill: W, w: 3 });
  p.shape(rect(28, 22, 8, 24, 1), { close: 1, fill: AID, amp: .3 }); p.shape(rect(20, 30, 24, 8, 1), { close: 1, fill: AID, amp: .3 });
  p.line([[46, 44], [52, 38]], 1.4, H); p.line([[42, 48], [52, 40]], 1.4, H);
}, 25);
ico("t-water", (p) => {
  p.shape(rect(26, 22, 28, 34, 7), { close: 1, fill: W, w: 3 });
  p.shape([[28, 36], [34, 34], [41, 37], [52, 34], [52, 50], [48, 54], [32, 54], [28, 50]], { close: 1, fill: WATER, amp: .4 });
  p.shape(rect(26, 22, 28, 34, 7), { close: 1, w: 3 });
  p.shape(rect(33, 15, 14, 7, 2), { close: 1, fill: W, w: 2.6 });
  p.shape([[14, 10], [20, 22], [20, 27], [14, 31], [8, 27], [8, 22]], { close: 1, fill: WATER, w: 2.6 });
}, 27);
ico("t-food", (p) => {
  p.shape(rect(16, 8, 32, 9, 2), { close: 1, fill: INK, amp: .4 });
  p.shape([[18, 17], [46, 17], [50, 26], [50, 54], [46, 57], [18, 57], [14, 54], [14, 26]], { close: 1, fill: W, w: 3 });
  p.shape(rect(20, 30, 24, 14, 2), { close: 1, fill: LAMP, w: 2.2 });
  p.ell(25, 50, 3, 3, { fill: AID, amp: .3 }, 8); p.ell(33, 51, 3, 3, { fill: AID, amp: .3 }, 8); p.ell(41, 50, 3, 3, { fill: AID, amp: .3 }, 8);
}, 29);
ico("t-power", (p) => {
  p.line([[14, 14], [16, 8], [26, 8], [28, 14]], 2.6);
  p.shape(rect(10, 14, 22, 5, 1.5), { close: 1, fill: INK, amp: .3 });
  p.shape(rect(12, 19, 18, 24, 3), { close: 1, fill: LAMP, w: 2.6 });
  p.shape([[21, 24], [25, 32], [21, 37], [17, 32]], { close: 1, fill: "#D9A21B", amp: .3 });
  p.shape(rect(10, 43, 22, 5, 1.5), { close: 1, fill: INK, amp: .3 });
  p.line([[40, 56], [52, 24]], 5);
  p.line(arc(54, 18, 7, 7, PI * .55, PI * 2.05, 9), 3);
}, 31);
ico("t-ready", (p) => {
  p.shape(rect(12, 10, 40, 48, 4), { close: 1, fill: W, w: 3 });
  p.shape(rect(24, 6, 16, 8, 2), { close: 1, fill: INK, amp: .3 });
  [22, 34, 46].forEach((y, i) => { p.line([[18, y], [21, y + 3], [26, y - 3]], 2.6); p.line([[31, y], [46 - i * 3, y]], 2.4); });
}, 33);
ico("t-radio", (p) => {
  p.line([[14, 26], [26, 6]], 2.4); p.dot(26.5, 5.5, 2.4);
  p.shape(rect(6, 26, 36, 22, 4), { close: 1, fill: CREAM, w: 3 });
  p.ell(17, 37, 6, 6, { fill: W, w: 2.4 }, 12); p.line([[28, 33], [37, 33]], 2.2); p.line([[28, 39], [37, 39]], 2.2);
  p.ell(48, 46, 12, 12, { fill: W, w: 3 }, 16);
  p.shape([[48, 37], [51, 46], [48, 55], [45, 46]], { close: 1, fill: AID, amp: .3 });
  p.dot(48, 46, 1.6, W);
}, 35);

// privacy page
ico("p-nowifi", (p) => {
  p.line(arc(32, 44, 26, 24, -PI * .82, -PI * .18, 10), 3.4); p.line(arc(32, 44, 16, 15, -PI * .8, -PI * .2, 7), 3.4); p.dot(32, 44, 3.6);
  p.line([[10, 54], [54, 10]], 4, AID);
}, 37);
ico("p-nocookie", (p) => {
  p.shape(ell(30, 34, 20, 19, 20).map((q, i) => (i === 3 || i === 4) ? [q[0] - 4, q[1] + 3] : q), { close: 1, fill: LAMP, w: 3 });
  p.dot(24, 28, 2.6); p.dot(34, 38, 2.6); p.dot(26, 42, 2.4); p.dot(38, 26, 2);
  p.line([[10, 56], [56, 8]], 4, AID);
}, 39);
ico("p-envelope", (p) => {
  p.shape(rect(8, 16, 48, 34, 3), { close: 1, fill: W, w: 3 });
  p.line([[9, 18], [32, 36], [55, 18]], 3);
  p.line([[38, 44], [50, 44]], 1.8, H);
}, 41);
ico("p-magnifier", (p) => {
  p.ell(26, 26, 15, 15, { fill: W, w: 3.4 }, 18); p.line(arc(26, 26, 9, 9, PI * 1.1, PI * 1.5, 4), 2, H);
  p.line([[37, 37], [54, 54]], 6);
}, 43);

/* ---------------- the eye-book mark (header, favicon) ---------------- */
function mark(p, paper) {
  if (paper) p.shape(rect(1, 1, 62, 62, 14), { close: 1, fill: "#F4F2EC", amp: .2 });
  p.amp = .45;
  p.ell(32, 24, 20, 20, { fill: INK, w: 2 }, 22);
  p.ell(32, 25, 13, 14, { fill: W, amp: .3 }, 18);
  p.shape([[19.5, 13], [44.5, 13], [44.5, 16.5], [32, 18.6], [19.5, 16.5]], { close: 1, fill: INK, amp: .2 });
  p.ell(32.5, 31, 6, 6, { fill: INK, amp: .2 }, 12);
  p.dot(30.3, 29, 1.6, W);
  p.shape([[32, 48], [24, 44.5], [9, 45], [8, 58], [22, 57], [32, 61]], { close: 1, fill: W, w: 3.2 });
  p.shape([[32, 48], [40, 44.5], [55, 45], [56, 58], [42, 57], [32, 61]], { close: 1, fill: W, w: 3.2 });
  p.line([[32, 48], [32, 60]], 2.6);
}
sizes["mark"] = svg("mark", I, (p) => mark(p, false), 3);
sizes["favicon"] = svg("favicon", I, (p) => mark(p, true), 3);

/* ---------------- lines: wavy rule, scribble underline ---------------- */
sizes["wave"] = svg("wave", [0, 0, 240, 14], (p) => {
  const q = []; for (let x = -4; x <= 244; x += 6) q.push([x, 7 + Math.sin(x / 240 * 4 * PI) * 3.6]);
  p.amp = .3; p.line(q, 2.5);
}, 45, ' preserveAspectRatio="none"');
// link underline: one hand line that tiles across (starts and ends at the same height)
sizes["uline"] = svg("uline", [0, 0, 48, 6], (p) => {
  const q = []; for (let x = -1; x <= 49; x += 5) q.push([x, 3.2 + Math.sin(x / 48 * 2 * PI) * .9]);
  p.amp = .25; p.line(q, 1.9);
}, 51, ' preserveAspectRatio="none"');
sizes["uline-thick"] = svg("uline-thick", [0, 0, 48, 6], (p) => {
  const q = []; for (let x = -1; x <= 49; x += 5) q.push([x, 3.2 + Math.sin(x / 48 * 2 * PI) * .9]);
  p.amp = .25; p.line(q, 3.4);
}, 51, ' preserveAspectRatio="none"');
sizes["scribble"] = svg("scribble", [0, 0, 120, 14], (p) => {
  p.amp = .4; p.line([[3, 8], [30, 5], [62, 8], [92, 5], [117, 7], [96, 10], [60, 11]], 3);
}, 49, ' preserveAspectRatio="none"');

fs.copyFileSync(path.join(OUT, "favicon.svg"), path.join(__dirname, "../../favicon.svg"));
fs.unlinkSync(path.join(OUT, "favicon.svg"));
delete sizes.favicon;
console.log(Object.entries(sizes).map(([k, v]) => k + " " + v).join("\n"));
