#!/usr/bin/env python3
"""Build the website-only buying guide: buying-guide/index.html.

Run:  python3 -I tools/buying_guide.py

Content and the Amazon Associates tracking ID both live in data/buying-guide.json.
This page belongs to the website only. Nothing here goes into the Lastbook app or
its library packs, which stay offline with no links out.

It reuses the site's own head, header and footer from tools/build.py (imported, not
changed), so the page matches the rest of lastbook.org.

Amazon rules this follows (Associates Operating Agreement, 15 Oct 2025, and
Program Policies, 14 Apr 2026, read 12 Nov 2026):
- the disclosure "As an Amazon Associate I earn from qualifying purchases." shows
  clearly whenever a tag is set;
- links go straight to amazon.com/dp/ASIN with the tag as a URL parameter: no
  shortener, redirect or cloaking;
- no prices, ratings, review counts, availability or Amazon images (those need
  Amazon's own API), and no claims beyond what the listing or maker states.
"""
import hashlib, html, json, pathlib, re, sys

TOOLS = pathlib.Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import build  # noqa: E402  (head, bar, FOOT, page_head)

DATA = ROOT / "data/buying-guide.json"
OUT = "buying-guide/index.html"
PATH = "/buying-guide/"
ASIN = re.compile(r"^[A-Z0-9]{10}$")
TAG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{1,38}[A-Za-z0-9]$")
DISCLOSURE = "As an Amazon Associate I earn from qualifying purchases."


def e(s):
    return html.escape(s, quote=True)


def product_url(market, asin, tag):
    url = f"{market.rstrip('/')}/dp/{asin}/"
    return f"{url}?tag={tag}" if tag else url


def page(d):
    tag = d.get("ASSOCIATE_TAG", "").strip()
    if tag and not TAG.match(tag):
        sys.exit(f"ASSOCIATE_TAG {tag!r} doesn't look like an Associates tracking ID (for example name-20).")
    market = d["marketplace"]
    if not re.match(r"^https://www\.amazon\.[a-z.]+$", market.rstrip("/")):
        sys.exit(f"marketplace {market!r} must be an Amazon address such as https://www.amazon.com")
    src = d["sources"]
    rel = "sponsored noopener" if tag else "noopener"

    shown = 0
    navs, secs = [], []
    for s in d["sections"]:
        navs.append(f'<li><a href="#{e(s["id"])}"><img src="{e(s["icon"])}" width="40" height="40" alt=""><span><span class="u">{e(s["title"])}</span></span></a></li>')
        cards = []
        for it in s["items"]:
            looks = []
            for text, key in it["look"]:
                so = src[key]
                looks.append(f'<li>{e(text)} <a class="bg-src" href="{e(so["url"])}">{e(so["by"])}</a></li>')
            prods = []
            for p in it.get("products", []):
                if not p.get("checked"):
                    continue  # not opened by a person yet: leave it out rather than guess
                if not ASIN.match(p["asin"]):
                    sys.exit(f"Bad ASIN {p['asin']!r} under {it['name']!r}")
                says = f'<small>{e(p["maker_says"])}</small>' if p.get("maker_says") else ""
                prods.append(f'<li><a href="{e(product_url(market, p["asin"], tag))}" rel="{rel}">{e(p["name"])}</a>{says}</li>')
                shown += 1
            buy = (f'<p class="bg-on">On Amazon</p><ul class="bg-prods">{"".join(prods)}</ul>') if prods else ""
            cards.append(f"""<article class="card bg-item">
      <h3>{e(it["name"])}</h3>
      <p class="bg-why">{e(it["why"])}</p>
      <p class="bg-look">What to look for</p>
      <ul class="dots">{"".join(looks)}</ul>{buy}
    </article>""")
        secs.append(f"""<section class="bg-sec" id="{e(s["id"])}" aria-labelledby="{e(s["id"])}-h">
  <div class="bg-sec-head">
    <img class="bg-icon" src="{e(s["icon"])}" width="64" height="64" alt="">
    <div><h2 id="{e(s["id"])}-h">{e(s["title"])}</h2><p class="lead">{e(s["line"])}</p></div>
  </div>
  <div class="bg-items">
    {(chr(10) + "    ").join(cards)}
  </div>
</section>""")

    if tag:
        status = f"""<p class="note bg-disclose"><strong>{DISCLOSURE}</strong> If you buy through a link here, Lastbook gets a small share. You pay the same.</p>"""
    else:
        status = """<p class="note bg-disclose"><strong>Lastbook’s Amazon Associates account isn’t connected yet.</strong> Any Amazon links here are plain links and earn nothing.</p>"""

    lib = [k for k, v in src.items() if v.get("library")]
    srcs = "".join(
        f'<li><a href="{e(v["url"])}">{e(v["name"])}</a> <span class="fine">· {e(v["by"])}{" · in the Lastbook library" if v.get("library") else ""}</span></li>'
        for v in src.values())

    css = "/buying-guide.css?v=" + hashlib.sha256((ROOT / "buying-guide.css").read_bytes()).hexdigest()[:10]
    more = status
    body = build.head(
        "Buying guide",
        "What to have before an emergency, and what to look for when you buy it: first aid, water, food, repairs, power and the basics.",
        PATH, extra=f'\n<link rel="stylesheet" href="{css}">') + build.bar(PATH) + f"""
<main id="main" class="page bg">
<div class="wrap">

{build.page_head("Buying guide", "What to have before an emergency, and what to look for when you buy it.", "fig-radio", more)}

<nav class="bg-jump" aria-label="Sections">
  <ul>
    {(chr(10) + "    ").join(navs)}
  </ul>
</nav>

{(chr(10) + chr(10)).join(secs)}

<section class="block narrow bg-how" aria-labelledby="how-h">
  <h2 id="how-h">How this guide works</h2>
  <ul class="checks">
    <li>Each point comes from an official guide. Most of them are also in the Lastbook library.</li>
    <li>No prices, ratings or stock here. Check those on Amazon before you buy.</li>
    <li>Nobody paid to be listed.</li>
    <li>The Lastbook app has no shop and no links. It never goes online.</li>
  </ul>
  <p class="fine">This page sets no cookies. Amazon sets its own when you open amazon.com.</p>
</section>

<section class="block narrow bg-sources" id="sources" aria-labelledby="src-h">
  <h2 id="src-h">Sources</h2>
  <ul class="links">{srcs}</ul>
  <p class="fine">Checked {e(d["updated"])}. {len(lib)} of these {len(src)} are in the Lastbook library.</p>
</section>

</div>
</main>
""" + build.FOOT
    return body, tag, shown


if __name__ == "__main__":
    d = json.loads(DATA.read_text())
    text, tag, shown = page(d)
    p = ROOT / OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    print(f"{OUT}: {len(text.encode())} bytes · products shown: {shown} · Associates tag: {'set' if tag else 'not set (plain links)'}")
