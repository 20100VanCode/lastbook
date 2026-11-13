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
  Product photos are local copies of the makers' own images (sources and terms in
  buying-guide/IMAGE-SOURCES.md); nothing is loaded from Amazon or hotlinked.
"""
import hashlib, html, json, pathlib, re, sys, urllib.parse

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


def search_url(market, query, tag):
    q = urllib.parse.urlencode({"k": query, **({"tag": tag} if tag else {})})
    return f"{market.rstrip('/')}/s?{q}"


def page(d):
    tag = d.get("ASSOCIATE_TAG", "").strip()
    if tag and not TAG.match(tag):
        sys.exit(f"ASSOCIATE_TAG {tag!r} doesn't look like an Associates tracking ID (for example name-20).")
    market = d["marketplace"]
    if not re.match(r"^https://www\.amazon\.[a-z.]+$", market.rstrip("/")):
        sys.exit(f"marketplace {market!r} must be an Amazon address such as https://www.amazon.com")
    src = d["sources"]
    rel = "sponsored noopener" if tag else "noopener"

    shown = searches = 0
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
            for product in it.get("products", []):
                if not product.get("checked") or not product.get("maker_url"):
                    sys.exit(f"Missing manufacturer source or checked date for {product['name']!r}")
                if product.get("asin"):
                    if not ASIN.fullmatch(product["asin"]) or not product.get("seen_url"):
                        sys.exit(f"Missing ASIN evidence for {product['name']!r}")
                    destination = product_url(market, product["asin"], tag)
                    label = "View on Amazon"
                else:
                    destination = search_url(market, product["query"], tag)
                    label = "Find on Amazon"
                    searches += 1
                photo = ""
                if product.get("image"):
                    for k in ("image", "image_fallback"):
                        ref = product.get(k, "")
                        if not ref.startswith("/img/buying-guide/") or not (ROOT / ref.lstrip("/")).is_file():
                            sys.exit(f"{k} for {product['name']!r} must be a local file under /img/buying-guide/")
                    if not product.get("image_alt"):
                        sys.exit(f"Missing image_alt for {product['name']!r}")
                    photo = (f'\n        <picture class="bg-photo"><source srcset="{e(product["image"])}" type="image/webp">'
                             f'<img src="{e(product["image_fallback"])}" width="600" height="600" loading="lazy" decoding="async" alt="{e(product["image_alt"])}"></picture>')
                prods.append(f'''<div class="bg-product">{photo}
        <h4>{e(product["name"])}</h4>
        <p>{e(product["feature"])}</p>
        <a class="bg-maker" href="{e(product["maker_url"])}">Manufacturer details</a>
        <p class="bg-search"><a class="btn-2 bg-shop" href="{e(destination)}" rel="{rel}">{label}</a></p>
      </div>''')
                shown += 1
            buy = "".join(prods)
            if not prods and it.get("search"):
                buy = (f'<p class="bg-search"><a class="btn-2 bg-shop" href="{e(search_url(market, it["search"], tag))}" rel="{rel}">'
                       f'<span><b>Search Amazon</b><small>for {e(it["search"])}</small></span></a></p>')
                searches += 1
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
    <li>Product descriptions use manufacturer information. Compare the model, size, seller and current price before buying.</li>
    <li>“Find on Amazon” and “Search Amazon” open search results. “View on Amazon” opens a specific listing.</li>
    <li>Lastbook has not tested these products. Nobody paid to be listed.</li>
  </ul>
  <p class="fine">Shopping links take you to Amazon, which has its own privacy and cookie policies.</p>
</section>

<section class="block narrow bg-sources" id="sources" aria-labelledby="src-h">
  <h2 id="src-h">Sources</h2>
  <ul class="links">{srcs}</ul>
  <p class="fine">Checked {e(d["updated"])}. {len(lib)} of these {len(src)} are in the Lastbook library.</p>
</section>

</div>
</main>
""" + build.FOOT
    return body, tag, shown, searches


if __name__ == "__main__":
    d = json.loads(DATA.read_text())
    text, tag, shown, searches = page(d)
    p = ROOT / OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    print(f"{OUT}: {len(text.encode())} bytes · products shown: {shown} · search links: {searches} · Associates tag: {'set' if tag else 'not set (plain links)'}")
