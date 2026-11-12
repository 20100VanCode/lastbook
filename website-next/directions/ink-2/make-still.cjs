// Writes the JavaScript-off crowd drawings from the same code as the live canvas.
// usage: node make-still.cjs desk.json phone.json   (layout JSON measured in a browser)
const fs = require("fs"), path = require("path");
const still = require("./crowd.js");
const bubbles = [["lantern", "power's out"], ["jug", "how do I purify water?"], ["aid", "found it", 1]];
for (const [file, out] of [[process.argv[2], "crowd-desk.svg"], [process.argv[3], "crowd-phone.svg"]]) {
  const txt = fs.readFileSync(file, "utf8"); const L = JSON.parse(txt.slice(txt.indexOf("{"), txt.lastIndexOf("}") + 1));
  const svg = still(Math.round(L.W), Math.round(L.H), L.B, L.phone, L.G, bubbles);
  fs.writeFileSync(path.join(__dirname, out), svg);
  console.log(out, svg.length);
}
