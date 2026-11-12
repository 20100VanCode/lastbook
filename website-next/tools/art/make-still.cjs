// Writes the JavaScript-off crowd drawings (img/ink/crowd-desk.svg, crowd-phone.svg)
// from the same code as the live canvas.
//   usage: node tools/art/make-still.cjs desk.json phone.json   (JSON printed by tools/art/measure.js)
const fs = require("fs"), path = require("path");
const { still } = require("../../crowd.js");
for (const [file, out] of [[process.argv[2], "crowd-desk.svg"], [process.argv[3], "crowd-phone.svg"]]) {
  const txt = fs.readFileSync(file, "utf8"); const L = JSON.parse(txt.slice(txt.indexOf("{"), txt.lastIndexOf("}") + 1));
  const svg = still(Math.round(L.W), Math.round(L.H), L.B, L.phone, L.G);
  fs.writeFileSync(path.join(__dirname, "../../img/ink", out), svg);
  console.log(out, svg.length);
}
