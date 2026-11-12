#!/usr/bin/env python3
"""Build the Lastbook site's HTML pages.

Run:  python3 -I tools/build.py        (from anywhere; paths are relative to this file)

It writes index.html, download/, library/, privacy/, credits/ and 404.html next to
this folder, fills the credits list from data/credits.json (so it works with no
JavaScript), and adds a short content hash to style.css and the scripts so they
can be cached for a year. Edit the text here, not in the built .html files.

The look is "ink on paper": hand-drawn pictures live in img/ink/ (made by
tools/art/make-art.cjs) and the home crowd is drawn live by crowd.js. The
wordmark is inlined from tools/art/wordmark.svg.
"""
import hashlib, html, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://lastbook.org"
R2 = "https://pub-28c3cc06eb774c5cac057e6c9343efbd.r2.dev"
MAC = R2 + "/Lastbook-1.0.0-mac.dmg"
WIN = R2 + "/Lastbook-1.0.0-Setup.exe"
LIB = R2 + "/Lastbook-Small.zip"
DATE = "4 November 2026"


def h(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()[:10]


CSS = "/style.css?v=" + h("style.css")
JS = "/os.js?v=" + h("os.js")
CROWD = "/crowd.js?v=" + h("crowd.js")
FONT = "/fonts/Nunito-Variable.woff2"
WORDMARK = (ROOT / "tools/art/wordmark.svg").read_text().strip()

APPLE = ('<svg aria-hidden="true" viewBox="0 0 24 24" width="24" height="24"><path fill="currentColor" d="M16.4 12.6c0-2.6 2.1-3.8 2.2-3.9-1.2-1.8-3.1-2-3.7-2-1.6-.2-3.1.9-3.9.9-.8 0-2-.9-3.4-.9-1.7 0-3.3 1-4.2 2.6-1.8 3.1-.5 7.7 1.3 10.2.9 1.2 1.9 2.6 3.2 2.6 1.3-.1 1.8-.8 3.3-.8 1.6 0 2 .8 3.4.8 1.4 0 2.3-1.3 3.1-2.5 1-1.4 1.4-2.8 1.4-2.9 0 0-2.7-1-2.7-4.1ZM13.9 5c.7-.9 1.2-2.1 1.1-3.3-1 0-2.3.7-3 1.6-.7.8-1.2 2-1.1 3.2 1.2.1 2.3-.6 3-1.5Z"/></svg>')
WINDOWS = ('<svg aria-hidden="true" viewBox="0 0 24 24" width="22" height="22"><path fill="currentColor" d="M2 4.3 10 3.2v7.7H2Zm9-1.2L22 1.5v9.4H11ZM2 12h8v7.8l-8-1.1Zm9 0h11v9.5l-11-1.5Z"/></svg>')
BOX = ('<svg aria-hidden="true" viewBox="0 0 24 24" width="22" height="22"><path fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round" d="M4 7.5 12 3l8 4.5v9L12 21l-8-4.5Zm0 0 8 4.5 8-4.5M12 12v9"/></svg>')


def ink(name, w, h, cls="", alt=""):
    """One of the hand-drawn pictures in img/ink/ (decorative unless alt is given)."""
    c = f' class="{cls}"' if cls else ""
    return f'<img{c} src="/img/ink/{name}.svg" width="{w}" height="{h}" alt="{alt}" loading="lazy" decoding="async">'


def head(title, desc, path, extra="", index=True):
    full = title if title.startswith("Lastbook") else f"{title} · Lastbook"
    canon = f'<link rel="canonical" href="{SITE}{path}">\n' if path else ""
    ogurl = f'<meta property="og:url" content="{SITE}{path}">\n' if path else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{full}</title>
<meta name="description" content="{desc}">
<meta name="color-scheme" content="light">
<meta name="theme-color" content="#F4F2EC">
{"" if index else '<meta name="robots" content="noindex">' + chr(10)}{canon}<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Lastbook">
<meta property="og:title" content="{full}">
<meta property="og:description" content="{desc}">
{ogurl}<meta property="og:image" content="{SITE}/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Lastbook: a free library for when the internet or power is gone. A hand-drawn wordmark whose two O’s are eyes reading an open book, with small ink people around it.">
<meta name="twitter:card" content="summary_large_image">
<link rel="preload" href="{FONT}" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{CSS}">
<script src="{JS}"></script>{extra}
</head>
<body>
<svg class="defs" aria-hidden="true" focusable="false" width="0" height="0"><filter id="rough" x="-3%" y="-8%" width="106%" height="116%"><feTurbulence type="fractalNoise" baseFrequency="0.028" numOctaves="2" seed="7"/><feDisplacementMap in="SourceGraphic" scale="2.2" xChannelSelector="R" yChannelSelector="G"/></filter><filter id="rough-line" x="-2%" y="-2%" width="104%" height="104%"><feTurbulence type="fractalNoise" baseFrequency="0.02" numOctaves="2" seed="3"/><feDisplacementMap in="SourceGraphic" scale="2.4" xChannelSelector="R" yChannelSelector="G"/></filter></svg>
<a class="skip" href="#main">Skip to content</a>
"""


NAV = [("/download/", "Download"), ("/library/", "Library"), ("/privacy/", "Privacy"), ("/credits/", "Credits")]


def bar(current, over=False):
    links = []
    for href, label in NAV[1:]:
        cur = ' aria-current="page"' if href == current else ""
        links.append(f'<a href="{href}"{cur}>{label}</a>')
    cur = ' aria-current="page"' if current == "/download/" else ""
    return f"""<header class="bar{' bar-over' if over else ''}">
  <div class="bar-in">
    <a class="brand" href="/"><img src="/img/ink/mark.svg" alt="" width="36" height="36"><span>Lastbook</span></a>
    <nav class="nav" aria-label="Main">
      {chr(10).join("      " + l for l in links).strip()}
    </nav>
    <a class="btn btn-sm" href="/download/"{cur}>Download</a>
  </div>
</header>
"""


FOOT = f"""<footer class="foot">
  <div class="wrap">
    <p class="foot-warn"><img src="/img/ink/d-bang-red.svg" alt="" width="30" height="30"><span><strong>Not clinically reviewed.</strong> Lastbook doesn’t replace trained care. In an emergency, call 911 if you can.</span></p>
    <p class="foot-links">
      <a href="/download/">Download</a>
      <a href="/library/">What’s in the library</a>
      <a href="/privacy/">Privacy</a>
      <a href="/credits/">Credits and licences</a>
      <a href="/download/#check">Check your download</a>
      <a href="mailto:hello@lastbook.org">hello@lastbook.org</a>
    </p>
    <p class="fine">Lastbook 1.0.0 · {DATE} · This site has no cookies and no tracking. Licence details for the app are coming soon.</p>
  </div>
</footer>
</body>
</html>
"""


def btn(href, icon, label, sub, cls="btn"):
    return f'<a class="{cls}" href="{href}">{icon}<span><b>{label}</b><small>{sub}</small></span></a>'


def pic(stem, w, h, alt, widths=(720, 1280), sizes="92vw", fallback=None, eager=False):
    """A <picture> of a real app screenshot (light look only)."""
    light = ", ".join(f"/img/{stem.format(m='light', w=x)}.avif {x}w" for x in widths)
    fb = fallback or f"/img/{stem.format(m='light', w=widths[0])}.jpg"
    load = 'fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
    return f"""<picture>
      <source type="image/avif" srcset="{light}" sizes="{sizes}">
      <img src="{fb}" width="{w}" height="{h}" {load} alt="{alt}">
    </picture>"""


MAC_BTN = btn(MAC, APPLE, "Download for Mac", "Lastbook 1.0.0 · 22.5 MB")
WIN_BTN = btn(WIN, WINDOWS, "Download for Windows", "Lastbook 1.0.0 · 75.2 MB")
LIB_BTN = btn(LIB, BOX, "Download the library", "Small · 8.2 GB", "btn-2")
LIB_BTN_SHORT = btn(LIB, BOX, "Download the library", "Small · 8.2 GB", "btn-2")
MAC_FINE = "Free · Apple M1 or newer · macOS 14 or newer"
WIN_FINE = "Free · Windows 10 or 11, 64-bit"
PHONE = '<p class="os-note fine">Lastbook runs on Mac and Windows computers. It doesn’t run on iPhone, iPad or Android. <strong>Open lastbook.org on your computer.</strong></p>'

MAC_CHECK = "To check: Apple menu &gt; <b>About This Mac</b>. <b>Chip</b> should say Apple M1 or later (M2, M3 and so on), and <b>macOS</b> should be 14 or higher."
WIN_CHECK = "To check: <b>Settings</b> &gt; <b>System</b> &gt; <b>About</b>. <b>System type</b> should say 64-bit."

# 12,894 pages: the page counts of the 148 PDFs in derived/packs/small (Spotlight
# kMDItemNumberOfPages, summed, 4 Nov 2026). The other counts are pack.json "counts".
# The map date is the one the app itself shows on its Map page (win-*-window-map shot).
COUNTS = """<ul class="counts">
    <li><b>148</b><span>PDF documents, 12,894 pages</span></li>
    <li><b>45</b><span>saved web guides</span></li>
    <li><b>41</b><span>how‑to videos</span></li>
    <li><b>2</b><span>encyclopedias, medical and how‑to</span></li>
    <li><b>1</b><span>map of the US, roads, towns and water</span></li>
  </ul>"""

WAVE = '<div class="wave" aria-hidden="true"></div>'

AGAIN = f"""<section class="band band-lamp" aria-labelledby="again-h">
  {WAVE}
  <div class="wrap again-in">
    {ink("foot-crowd", 210, 104, "again-fig")}
    <h2 id="again-h">Set it up now, while you have internet and power.</h2>
    <p>Then it’s ready when you need it. Free for Mac and Windows.</p>
    <p class="again">
      <a class="btn-2 dl-mac" href="{MAC}">Download for Mac</a>
      <a class="btn-2 dl-win" href="{WIN}">Download for Windows</a>
      <a class="btn-2" href="{LIB}">Download the library</a>
    </p>
    <p class="fine">Mac 22.5 MB · Windows 75.2 MB · Library 8.2 GB (you need about <span class="nw">17 GB</span> free) · <a href="/download/#mac">How to open it</a></p>
  </div>
</section>
"""


def page_head(h1, lead, fig, more=""):
    return f"""<section class="page-head" aria-labelledby="h1">
  <div class="ph-title">
    <h1 id="h1">{h1}</h1>
    <span class="head-fig"><img src="/img/ink/{fig}.svg" width="150" height="181" alt=""></span>
  </div>
  <p class="lead">{lead}</p>{more}
</section>"""


# ---------------------------------------------------------------- Home
GRAIN = ('<svg class="grain" aria-hidden="true" focusable="false"><filter id="grain-f"><feTurbulence type="fractalNoise" baseFrequency=".75" numOctaves="2" stitchTiles="stitch"/>'
         '<feColorMatrix values="0 0 0 0 .09  0 0 0 0 .08  0 0 0 0 .06  0 0 0 .5 0"/></filter><rect width="100%" height="100%" filter="url(#grain-f)"/></svg>')


def home():
    return head("Lastbook: a free survival library that works with no internet",
                "Survival and repair guides, medical books, encyclopedias, how-to videos and a map, on your own Mac or Windows computer. Free. Never uses the internet.",
                "/", extra=f'\n<script src="{CROWD}" defer></script>') + bar("/", over=True) + f"""
<main id="main">

<section class="hero" id="hero" aria-labelledby="h1">
  {GRAIN}
  <canvas class="crowd" id="crowd" aria-hidden="true"></canvas>
  <noscript>
    <picture class="crowd-still">
      <source media="(max-width: 759px)" srcset="/img/ink/crowd-phone.svg">
      <img src="/img/ink/crowd-desk.svg" alt="" width="1440" height="900">
    </picture>
  </noscript>
  <div class="bubbles" id="bubbles" aria-hidden="true"></div>

  <div class="centre" id="centre">
    <h1 class="wm" id="h1"><span class="vh">Lastbook</span>
      {WORDMARK}
    </h1>
    <p class="lead">Everything you need to survive and rebuild.<br>Free, local, offline and private.<span class="phone-note"> It’s for Mac and Windows computers, not iPhone, iPad or Android. <strong>Open lastbook.org on your computer.</strong></span></p>
    <div class="dl">
      <div class="dl-item dl-mac"><a class="btn" href="{MAC}">{APPLE}<span>Download for Mac</span></a><p class="cap">22.5 MB · Apple M1 or newer · macOS 14+</p></div>
      <div class="dl-item dl-win"><a class="btn-2" href="{WIN}">{WINDOWS}<span>Download for Windows</span></a><p class="cap">75.2 MB · Windows 10 or 11, 64-bit</p></div>
    </div>
    <p class="then">Then <a href="{LIB}">download the library</a> <span class="nw">(8.2 GB,</span> needs about <span class="nw">17 GB</span> free)</p>
  </div>

  <button class="pause" id="pause" type="button" aria-pressed="false" hidden><svg aria-hidden="true" viewBox="0 0 16 16" width="14" height="14"><path class="i-pause" d="M4 3v10M12 3v10"/><path class="i-play" d="M4.5 2.5 13 8l-8.5 5.5Z"/></svg><span>Pause</span></button>
  <div class="hero-foot">
    <p>Lastbook 1.0.0 · Free · Never uses the internet · This site has no cookies and no tracking</p>
  </div>
</section>

<section class="sec essentials" aria-labelledby="essentials-h">
  <div class="wrap">
    <h2 id="essentials-h">Everything free, local, private.</h2>
    <div class="feature-shots">
      <figure>
        <figcaption><h3>AI</h3><p>Free. Local. Private.</p><p class="feature-metric"><b>Gemma 4</b>26B A4B</p><small>Runs on your computer</small></figcaption>
        <img class="real-ai-shot" src="/img/feature-ai-app.png?v=2" width="1364" height="775" alt="Lastbook’s local AI screen with questions about safe drinking water and first aid.">
      </figure>
      <figure>
        <figcaption><h3>Maps</h3><p>Free. Local. Private.</p><p class="feature-metric"><b>258,000+</b> searchable places</p><small>With the All library</small></figcaption>
        <img class="real-map-shot" src="/img/feature-map-crop.png" width="598" height="584" alt="Kansas City in Lastbook with water, medical, fire and shelter layers enabled.">
        <div class="map-key" aria-label="Map legend"><span><b class="key-water">W</b> Water</span><span><b class="key-medical">+</b> Medical</span><span><b class="key-fire">F</b> Fire stations</span><span><b class="key-shelter">⌂</b> Shelters</span></div>
      </figure>
      <figure>
        <figcaption><h3>Videos</h3><p>Free. Local. Private.</p><p class="feature-metric"><b>2,324</b> videos</p><small>With the All library</small></figcaption>
        <img class="real-video-shot" src="/img/feature-videos-crop.png?v=3" width="1166" height="656" alt="How to Use a Compass in the Lastbook video player.">
      </figure>
    </div>
    <div class="topic-cards">
      <article class="card"><h3>First aid &amp; health</h3><p>Wounds, illness and emergency care.</p></article>
      <article class="card"><h3>Safe drinking water</h3><p>Find, filter, treat and store water.</p></article>
      <article class="card"><h3>Food &amp; preservation</h3><p>Grow, prepare and preserve your food.</p></article>
      <article class="card"><h3>Critical repairs</h3><p>Tools, equipment and shelter repairs.</p></article>
      <article class="card"><h3>Power &amp; energy</h3><p>Generators, solar and electrical basics.</p></article>
      <article class="card"><h3>Emergency preparedness</h3><p>Plan for outages, disasters and evacuation.</p></article>
    </div>
  </div>
</section>

<section class="sec community" aria-labelledby="community-h">
  <div class="wrap">
    <h2 id="community-h">Lastbook is open source.</h2>
    <p class="lead">Help us improve it.</p>
    <div class="community-grid">
      <div><h3>Improve the app</h3><p>Code, design and accessibility.</p></div>
      <div><h3>Grow the library</h3><p>Recommend resources and help review guides.</p></div>
      <div><h3>Try it. Tell us.</h3><p>Report bugs and share what you need.</p></div>
    </div>
    <div class="community-actions"><a class="btn github-button" href="https://github.com/Immortal-Protocols" target="_blank" rel="noopener" aria-label="GitHub"><img src="/img/github-lockup-white.svg" width="110" height="32" alt="GitHub"></a><a class="btn-2" href="mailto:hello@lastbook.org?subject=Contributing%20to%20Lastbook">Join the community</a></div>
    <img class="community-people" src="/img/ink/foot-crowd.svg" width="1080" height="200" alt="" loading="lazy">
  </div>
</section>

<section class="sec" aria-labelledby="trust-h">
  <div class="wrap trust">
    <div>
      <h2 id="trust-h">No internet. No account. No tracking.</h2>
      <ul class="checks">
        <li><strong>It never uses the internet.</strong> Everything is on your computer, so it works with no signal at all.</li>
        <li><strong>It runs on a laptop battery.</strong> No power grid, no server, nothing to sign in to.</li>
        <li><strong>It’s free.</strong> No account, no ads, nothing to buy.</li>
        <li><strong>This site doesn’t track you either.</strong> No cookies, no analytics, nothing from other companies.</li>
      </ul>
      <p><a href="/privacy/">Privacy, in full</a></p>
    </div>
    {ink("fig-lantern", 172, 208, "trust-fig")}
  </div>
</section>

<section class="sec" id="faq" aria-labelledby="faq-h">
  <div class="wrap narrow">
    <h2 id="faq-h">Questions</h2>
    <div class="faq">
      <details><summary>Will it run on my computer?</summary><div>
        <p>On a Mac, you need Apple Silicon (M1 or newer) and macOS 14 Sonoma or newer. Macs with Intel chips can’t run version 1.0. {MAC_CHECK}</p>
        <p>On Windows, you need Windows 10 or 11, 64-bit. {WIN_CHECK}</p>
        <p>Lastbook doesn’t run on phones or tablets.</p>
      </div></details>
      <details><summary>How much space do I need?</summary><div>
        <p>About 17 GB of free space. After the library is unzipped, you can delete Lastbook-Small.zip.</p>
      </div></details>
      <details><summary>Does it need the internet?</summary><div>
        <p>Only to download it. After that, Lastbook never uses the internet.</p>
      </div></details>
      <details><summary>Why does my computer warn me?</summary><div>
        <p>Version 1.0 isn’t signed yet, so your computer asks you to confirm the first time. <a href="/download/#why">Why the warning?</a></p>
      </div></details>
      <details><summary>What is Ask?</summary><div>
        <p>The Ask page can’t answer questions yet in version 1.0. Use the search box instead. Search, guides, videos and the map all work.</p>
      </div></details>
      <details><summary>Is the medical information checked?</summary><div>
        <p>It comes from published guides, such as Hesperian, the World Health Organization and the Red Cross. Lastbook itself is not clinically reviewed, and it doesn’t replace trained care. In an emergency, call 911 if you can.</p>
      </div></details>
      <details><summary>Is there a bigger library?</summary><div>
        <p>Yes. Medium (67 GB) comes later. Small is the one to get now.</p>
      </div></details>
      <details><summary>Something else?</summary><div>
        <p>Email <a href="mailto:hello@lastbook.org">hello@lastbook.org</a>.</p>
      </div></details>
    </div>
  </div>
</section>

""" + AGAIN + "</main>\n" + FOOT


# ---------------------------------------------------------------- Download
def download():
    return head("Download",
                "Download Lastbook 1.0.0 for Mac or Windows and the Small library, then follow the steps to open it the first time.",
                "/download/") + bar("/download/") + f"""
<main id="main" class="page">
<div class="wrap">

{page_head("Download Lastbook", "You need two things: the app for your computer, and the library.", "fig-laptop")}
{PHONE}

<ul class="files" id="need">
  <li class="card file dl-mac">
    <p class="kicker">App</p><h2>Mac</h2>
    <p class="file-name">Lastbook-1.0.0-mac.dmg · 22.5 MB</p>
    <p class="req">For Apple Silicon Macs (M1 or newer) with macOS 14 Sonoma or newer.</p>
    <p class="req">{MAC_CHECK}</p>
    {MAC_BTN}
  </li>
  <li class="card file dl-win">
    <p class="kicker">App</p><h2>Windows</h2>
    <p class="file-name">Lastbook-1.0.0-Setup.exe · 75.2 MB</p>
    <p class="req">For Windows 10 or 11, 64-bit.</p>
    <p class="req">{WIN_CHECK}</p>
    {WIN_BTN}
  </li>
  <li class="card file">
    <p class="kicker">Library</p><h2>Small</h2>
    <p class="file-name">Lastbook-Small.zip · 8.2 GB</p>
    <p class="req">You need about 17 GB of free space. After the library is unzipped, you can delete Lastbook-Small.zip. It can take hours on a slow connection.</p>
    {LIB_BTN}
  </li>
  <li class="card file file-later">
    <span class="tag">Coming later</span>
    <p class="kicker">Library</p><h2>Medium</h2>
    <p class="file-name">67 GB</p>
    <p class="req">A bigger library. It comes later.</p>
  </li>
</ul>
<p class="fine host">The files download from Lastbook’s storage at Cloudflare (pub-28c3…r2.dev).</p>

<p class="note ready"><strong>The first time you open Lastbook, your computer warns you. That’s expected.</strong> Here’s what to click.</p>

<div class="os">
  <div class="os-side dl-mac">
  <section class="card os-card dl-mac" id="mac" aria-labelledby="mac-h">
    <h2 id="mac-h">{APPLE} Mac</h2>
    <p class="fine">For Apple Silicon Macs (M1 or newer) with macOS 14 Sonoma or newer.</p>
    <ol class="list">
      <li>Open <b>Lastbook-1.0.0-mac.dmg</b>.</li>
      <li>Drag <b>Lastbook</b> to <b>Applications</b>. Then eject the <b>Lastbook</b> disk in the Finder sidebar.</li>
      <li>Leave <b>Lastbook-Small.zip</b> in <b>Downloads</b> and double-click it. Wait until it finishes. It makes a folder called <b>LastbookData</b>. Leave it there.<br><span class="fine">If you already see a <b>LastbookData</b> folder in Downloads, leave it there and skip this step.</span></li>
      <li>Open <b>Lastbook</b> from Applications.</li>
    </ol>
    <p class="note warn">The first time, macOS warns that it can’t check Lastbook. That is expected. Don’t click <b>Move to Trash</b>.</p>
    <details class="ver" open>
      <summary>macOS 15 Sequoia or newer</summary>
      <div>
      <ol class="list">
        <li>Click <b>Done</b>.</li>
        <li>Open <b>System Settings</b> &gt; <b>Privacy &amp; Security</b>.</li>
        <li>Scroll down to <b>Security</b>. Next to the line that says Lastbook was blocked, click <b>Open Anyway</b>.</li>
        <li>When asked, click <b>Open Anyway</b> (or <b>Open</b>), and use Touch ID or your Mac password.</li>
      </ol>
      <p class="fine">If the button is gone, open Lastbook again and come back within an hour.</p>
      </div>
    </details>
    <details class="ver" open>
      <summary>macOS 14 Sonoma</summary>
      <div>
      <ol class="list">
        <li>Click <b>Cancel</b>.</li>
        <li>Open <b>Applications</b> in the Finder.</li>
        <li>Control-click <b>Lastbook</b>. Choose <b>Open</b>.</li>
        <li>Click <b>Open</b>.</li>
      </ol>
      </div>
    </details>
    <p><strong>You only do this once.</strong></p>
    <p class="fine">If your Mac asks to let Lastbook use your Downloads or Documents folder, click <b>Allow</b>. That is how it finds the library.</p>
  </section>
  <section class="card plain" id="find" aria-labelledby="find-h">
    <h2 id="find-h">If Lastbook can’t find the library</h2>
    <p>It asks you. Choose the <b>LastbookData</b> folder. It is in Downloads, or on Windows in Downloads &gt; Lastbook-Small.</p>
  </section>
  </div>

  <div class="os-side dl-win">
  <section class="card os-card dl-win" id="windows" aria-labelledby="win-h">
    <h2 id="win-h">{WINDOWS} Windows</h2>
    <p class="fine">For Windows 10 or 11, 64-bit.</p>
    <p class="tip">If your browser says the Setup file <b>isn’t commonly downloaded</b>: in Edge, click <b>…</b> next to it, then <b>Keep</b>, <b>Show more</b> and <b>Keep anyway</b>. In Chrome, click <b>Keep</b>.</p>
    <p class="tip">Windows may hide the end of file names, so you may see <b>Lastbook-Small</b> (a zipped folder) and <b>Lastbook-1.0.0-Setup</b>.</p>
    <ol class="list">
      <li>Right-click <b>Lastbook-Small.zip</b> in Downloads and choose <b>Extract All</b>.</li>
      <li>Click <b>Extract</b>. Keep the folder it suggests. Wait until it finishes, which can take several minutes.</li>
      <li>Double-click <b>Lastbook-1.0.0-Setup.exe</b> in Downloads.</li>
      <li>If <b>Windows protected your PC</b> appears, click <b>More info</b>, then <b>Run anyway</b>.</li>
      <li>Click <b>Install</b>, then <b>Open Lastbook</b>.</li>
    </ol>
    <p>Next time, open <b>Lastbook</b> from the Start menu.</p>
    <div class="note warn sac">
      <img src="/img/ink/d-bang-red.svg" alt="" width="40" height="40">
      <div>
      <p class="only">Only if you see this message</p>
      <p><strong>Windows 11 only:</strong> Smart App Control may block Lastbook, because it isn’t signed yet. There is no way to allow just one app.</p>
      <p>If Windows says Smart App Control blocked Lastbook, open <b>Windows Security</b> &gt; <b>App &amp; browser control</b> &gt; <b>Smart App Control settings</b> and choose <b>Off</b>. On an up-to-date Windows 11 you can turn it back on later. A signed version that doesn’t need this is coming.</p>
      </div>
    </div>
  </section>
  <section class="card plain" id="why" aria-labelledby="why-h">
    <h2 id="why-h">Why the warning?</h2>
    <p>Apple and Microsoft expect app makers to register a digital signature. Lastbook doesn’t have one yet, so your computer shows a warning. A signed version comes later.</p>
    <p>Lastbook never uses the internet.</p>
  </section>
  </div>
</div>

<section class="card plain sums-card" id="check" aria-labelledby="check-h">
  <h2 id="check-h">Check your download</h2>
  <p>Optional. You can skip this. It proves the file you got is exactly the one we made.</p>
  <p>SHA-256 of each file:</p>
  <dl class="sums">
    <dt>Lastbook-Small.zip</dt><dd><code>55a3d9b2bad7288786a60baf120ba861b1a9497199a3540d303886d7c2fad773</code></dd>
    <dt>Lastbook-1.0.0-mac.dmg</dt><dd><code>592daf8387b7cec099dbe1811158845dfd87bbb2a0ba37ae15da92387d75d447</code></dd>
    <dt>Lastbook-1.0.0-Setup.exe</dt><dd><code>b36d10291137492124ff7d9e2b5c993bd01ef00fcc5fc32e72e6c413e96dedc6</code></dd>
  </dl>
  <details class="ver cmd">
    <summary>How to check</summary>
    <div>
      <p>On a Mac, open Terminal and type:<br><code>shasum -a 256 ~/Downloads/Lastbook-1.0.0-mac.dmg</code><br><code>shasum -a 256 ~/Downloads/Lastbook-Small.zip</code></p>
      <p>On Windows, open PowerShell and type:<br><code>Get-FileHash $HOME\\Downloads\\Lastbook-1.0.0-Setup.exe</code><br><code>Get-FileHash $HOME\\Downloads\\Lastbook-Small.zip</code></p>
      <p class="fine">The long code it shows should match the one above. Capital letters don’t matter. The library is big, so its check can take a few minutes.</p>
    </div>
  </details>
  <p class="fine"><a href="/SHA256SUMS.txt">SHA256SUMS.txt</a></p>
  <p>Questions? Email <a href="mailto:hello@lastbook.org">hello@lastbook.org</a>.</p>
</section>

</div>
</main>
""" + FOOT


# ---------------------------------------------------------------- Library
TOPICS = [
    ("Injury and illness", "t-aid", "First aid, caring for the sick, medicines, teeth, birth and mental health.",
     ["Selected chapters from <cite>Where There Is No Doctor</cite> and <cite>Where There Is No Dentist</cite> (Hesperian)",
      "<cite>Basic Emergency Care</cite> (World Health Organization)",
      "<cite>MSF Clinical Guidelines</cite> and <cite>Essential Drugs</cite> (Médecins Sans Frontières)",
      "Videos: hands-only CPR, using an AED, choking, tourniquets"]),
    ("Water and toilets", "t-water", "Make water safe, clean wells and tanks, and deal with waste.",
     ["WHO technical notes on drinking water, wells and toilets in emergencies",
      "<cite>Public Health Engineering in Precarious Situations</cite> (MSF)",
      "<cite>Two Ways to Purify Water</cite> (National Park Service)"]),
    ("Food", "t-food", "Store, can, dry and freeze food safely, and grow more of it.",
     ["Canning, drying, freezing and pickling guides (National Center for Home Food Preservation)",
      "<cite>Seeds in Emergencies</cite> (FAO)",
      "Videos: water-bath and pressure canning, seed saving"]),
    ("Power, tools and repair", "t-power", "Generators, batteries and solar, small engines, tools and building.",
     ["Generator and engine owner’s manuals (Honda, Generac)",
      "Solar wiring and battery guides (Victron Energy, US Department of Energy)",
      "<cite>Tools and Their Uses</cite> and <cite>Wood Handbook</cite>",
      "Videos: welding, small-engine repair, woodworking"]),
    ("Getting ready for a disaster", "t-ready", "Plans and checklists for floods, fire, storms, heat, earthquakes and power cuts.",
     ["<cite>Are You Ready?</cite> and the <cite>Emergency Supply Kit Checklist</cite> (FEMA)",
      "<cite>Be Prepared</cite> and <cite>Disaster Preparedness for Older Adults</cite> (American Red Cross)",
      "Weather safety sheets (NOAA National Weather Service)"]),
    ("Radio and finding your way", "t-radio", "Emergency radio, maps and compass.",
     ["<cite>ARES Field Resources Manual</cite> and <cite>Quickstart Guide</cite> (ARRL)",
      "<cite>Finding Your Way with Map and Compass</cite> (USGS)",
      "Video: How to Use a Compass (REI)"]),
]


def library():
    cards = []
    for title, icon, line, items in TOPICS:
        lis = "".join(f"<li>{i}</li>" for i in items)
        cards.append(f'<section class="card topic">{ink(icon, 56, 56, "topic-icon")}<h3>{title}</h3><p>{line}</p><ul class="dots">{lis}</ul></section>')
    return head("What’s in the library",
                "Compare the Small, Medium and All offline libraries, including documents, videos, encyclopedias and maps.",
                "/library/") + bar("/library/") + f"""
<main id="main" class="page">
<div class="wrap">

{page_head("What’s in the library", "Three library sizes. Everything stays on your computer and works offline.", "fig-reader")}

<section class="pack-comparison" aria-label="Compare library sizes">
  <article class="card">
    <h2>Small</h2><p class="pack-status">Available · 8.2 GB download</p>
    <ul class="pack-facts">
      <li><strong>148</strong> PDF documents</li>
      <li><strong>12,894</strong> PDF pages</li>
      <li><strong>45</strong> saved web guides</li>
      <li><strong>41</strong> videos</li>
      <li><strong>2</strong> encyclopedias</li>
    </ul>
    <p>US base map with main roads, towns and water.</p>
  </article>
  <article class="card">
    <h2>Medium</h2><p class="pack-status">67.5 GB download · uploading</p>
    <ul class="pack-facts">
      <li><strong>4,450</strong> PDF documents</li>
      <li><strong>13</strong> slide decks</li>
      <li><strong>3,819</strong> saved web guides</li>
      <li><strong>573</strong> videos</li>
      <li><strong>3</strong> encyclopedias</li>
    </ul>
    <p>US base map plus California detail in the current build.</p>
  </article>
  <article class="card">
    <h2>All</h2><p class="pack-status">About 388 GB · estimated</p>
    <ul class="pack-facts">
      <li><strong>4,451</strong> PDF documents</li>
      <li><strong>13</strong> slide decks</li>
      <li><strong>3,819</strong> saved web guides</li>
      <li><strong>2,087</strong> videos</li>
      <li><strong>4</strong> encyclopedias</li>
    </ul>
    <p>Expanded US maps, more videos and text-only Wikipedia.</p>
  </article>
</section>
<p class="fine pack-count-note">Sizes are rounded. All’s size and counts are provisional until its rebuild and packaging finish.</p>

<h2 class="section-h">In every library size</h2>
<p class="lead">Examples from Small, also included in Medium and All. PDFs include books, manuals and selected chapters.</p>
<div class="topics">
  {chr(10).join("  " + c for c in cards).strip()}
</div>

<section class="block" aria-labelledby="larger-topics-h">
  <h2 id="larger-topics-h">More in Medium and All</h2>
  <p class="lead">Thousands more documents, including course notes, readings, exercises and technical references.</p>
  <div class="topics">
    <section class="card topic"><h3>Science and mathematics</h3><p>Physics, chemistry, genetics, geology, calculus and statistics.</p><ul class="dots"><li>MIT course materials in quantum physics, thermodynamics and genetics</li><li>Linear algebra, differential equations, probability and statistics</li></ul></section>
    <section class="card topic"><h3>Computing and electronics</h3><p>How computers and electronic systems work.</p><ul class="dots"><li>MIT Introduction to Algorithms and Computation Structures</li><li>Circuits, microelectronics and computer-system engineering</li></ul></section>
    <section class="card topic"><h3>Engineering and infrastructure</h3><p>Materials, heat, fluids and water systems.</p><ul class="dots"><li>Advanced fluid mechanics and heat-transfer course materials</li><li>Water and wastewater treatment manuals</li></ul></section>
    <section class="card topic"><h3>Making and manufacturing</h3><p>Tools, materials and production methods.</p><ul class="dots"><li>Metalworking and materials references</li><li>Ceramics, clothing and textile materials</li></ul></section>
    <section class="card topic"><h3>Transport and equipment</h3><p>Technical references for operating and maintaining equipment.</p><ul class="dots"><li>Aviation handbooks, including instructor materials</li><li>Generator, engine and machinery manuals</li></ul></section>
    <section class="card topic"><h3>More video teaching in All</h3><p>All adds a much larger video collection alongside the documents.</p><ul class="dots"><li>Science, engineering and practical-skills videos</li><li>Text-only Wikipedia is included in All</li></ul></section>
  </div>
</section>

<section class="block" aria-labelledby="enc-h">
  <h2 id="enc-h">Encyclopedias</h2>
  <p class="lead"><strong>MDWiki</strong> has plain-language articles on conditions, medicines and first aid. <strong>Appropedia</strong> covers water, sanitation, energy and building projects.</p>
  <p>Medium also includes <strong>Wikibooks</strong>. All adds <strong>Wikipedia, without pictures</strong>.</p>
  <p class="fine">These are written by volunteers. They’re good for background. For steps where safety matters, use the guides and manuals.</p>
  <figure class="tile pic">
    {pic("enc-{m}-{w}", 820, 464, "Lastbook’s Encyclopedias page: a search box and two cards, Medical encyclopedia (MDWiki: plain-language articles on conditions, medicines and first aid) and Appropedia (water, sanitation, energy and building projects).", widths=(820, 1640), sizes="(min-width: 880px) 800px, 88vw")}
  </figure>
</section>

<section class="block" aria-label="Map coverage">
  <div class="card plain">
    <h2>The map</h2>
    <p>A map of the whole US with main roads, towns and water. Find a town, ZIP code or place with no signal.</p>
    <p>Small has only this base map. Hospitals, water taps and side streets are not in it. It shows what was mapped by 25 October 2026, not damage, closures or hazards.</p>
  </div>

</section>

<section class="block narrow" aria-labelledby="src-h">
  <h2 id="src-h">Who made it</h2>
  <p>The guides, videos and books come from the people and groups who wrote them. Each owner keeps all rights in their work.</p>
  <p><a href="/credits/">See everyone whose work is in it</a></p>
</section>

</div>
""" + AGAIN + "</main>\n" + FOOT


# ---------------------------------------------------------------- Privacy
def ph2(icon, text):
    return f'<h2 class="h-doodle"><img src="/img/ink/{icon}.svg" alt="" width="44" height="44">{text}</h2>'


def privacy():
    return head("Privacy and trust",
                "Lastbook never uses the internet. This site has no cookies and no tracking. Version 1.0 isn’t signed yet, and here is why.",
                "/privacy/") + bar("/privacy/") + f"""
<main id="main" class="page">
<div class="wrap narrow prose">

{page_head("Privacy and trust", "Short version: Lastbook never uses the internet, and this site doesn’t track you.", "fig-lantern")}

{ph2("p-nowifi", "The app never uses the internet")}
<p>Everything is on your computer. Lastbook doesn’t check for updates, and it doesn’t send anything anywhere. There is no account to make.</p>
<p>What you save in Lastbook stays on your computer.</p>
<p class="note"><strong>You can check:</strong> turn off Wi‑Fi and open Lastbook. Everything works the same.</p>

{ph2("p-nocookie", "This site doesn’t track you")}
<ul class="checks">
  <li>No cookies.</li>
  <li>No analytics, ads or tracking.</li>
  <li>No fonts, scripts or pictures from other companies. Everything on these pages comes from lastbook.org.</li>
</ul>
<p>The site is hosted by Vercel, and the download files are stored on Cloudflare. Like any web host, they may keep standard request logs, such as IP addresses. We don’t add anything on top.</p>

{ph2("p-envelope", "Not signed yet, and why")}
<p>Apple and Microsoft expect app makers to register a digital signature. Lastbook doesn’t have one yet, so your computer shows a warning the first time you open it. A signed version comes later.</p>
<p><a href="/download/#mac">What to click on a Mac</a> · <a href="/download/#windows">What to click on Windows</a></p>

{ph2("p-magnifier", "Check your download")}
<p>Optional. You can skip this. Each file has a SHA-256 code. If yours matches, the file you got is exactly the one we made.</p>
<p><a href="/download/#check">See the codes and how to check</a></p>

<h2>Questions</h2>
<p>Email <a href="mailto:hello@lastbook.org">hello@lastbook.org</a>.</p>

</div>
</main>
""" + FOOT


# ---------------------------------------------------------------- Credits
def credits():
    data = json.loads((ROOT / "data/credits.json").read_text())
    owners = data["owners"]
    vids = sum(1 for o in owners if o.get("videos"))
    docs = sum(1 for o in owners if o.get("documents"))
    cols = [o["name"] for o in owners if o.get("collections")]
    rows = []
    for o in owners:
        words = [w for w in ("videos", "documents", "collections") if o.get(w)]
        what = ", ".join(words)
        what = what[:1].upper() + what[1:]
        parts = [f'<span class="owner">{html.escape(o["name"])}</span>']
        info = [what] if what else []
        if o.get("source"):
            info.append(f'from {html.escape(o["source"])}')
        if info:
            parts.append(f'<span class="what">{" · ".join(info)}</span>')
        rows.append("<li>" + "".join(parts) + "</li>")
    colnames = ", ".join(html.escape(c) for c in cols[:-1]) + (" and " + html.escape(cols[-1]) if len(cols) > 1 else "")
    note = f'<p class="fine">{html.escape(data["note"])}</p>' if data.get("note") else ""
    more = """
    <p>Each owner keeps all rights in their work. Lastbook’s own licence doesn’t cover it.</p>
    <p>To change or remove something, email <a href="mailto:hello@lastbook.org">hello@lastbook.org</a> and name the work.</p>
    <p><a href="#who">Find a name</a></p>"""
    return head("Credits",
                "Who made the work in the Lastbook library.",
                "/credits/", extra='\n<script src="/credits/credits.js?v=' + h("credits/credits.js") + '" defer></script>') + bar("/credits/") + f"""
<main id="main" class="page">
<div class="wrap">

{page_head("Credits", "We love to give credit.", "fig-garden", more)}

<div class="two">
<section class="card plain" id="map-sources" aria-labelledby="map-h">
  <h2 id="map-h">Map sources</h2>
  <ul class="dots">
    <li>OpenStreetMap contributors (via Geofabrik)</li>
    <li>Overture Maps Foundation</li>
    <li>Microsoft Global ML Building Footprints</li>
    <li>U.S. Census Bureau</li>
    <li>U.S. Geological Survey</li>
  </ul>
</section>

<section class="card plain" id="fonts" aria-labelledby="fonts-h">
  <h2 id="fonts-h">Fonts</h2>
  <ul class="dots">
    <li><strong>Nunito</strong> by Vernon Adams, Cyreal and Jacques Le Bailly (The Nunito Project Authors). SIL Open Font License 1.1.</li>
  </ul>
  <p class="fine">The font file is served from lastbook.org itself. <a href="/fonts/OFL.txt">Read the font licence</a></p>
  <p class="fine">The Lastbook wordmark and all the ink drawings on this site are drawn for Lastbook.</p>
</section>
</div>

<section id="who" aria-labelledby="who-h">
  <h2 id="who-h">Who made it</h2>
  <p class="lead">{len(owners)} publishers and makers: {vids} with videos, {docs} with documents, and {len(cols)} collections ({colnames}).</p>
  {note}
  <div class="search">
    <label for="q">Search</label>
    <input id="q" type="search" autocomplete="off" aria-describedby="searchstatus">
    <p class="fine" id="searchstatus" role="status" aria-atomic="true"></p>
  </div>
  <ul class="owners" id="owners" data-fold="40">
{chr(10).join(rows)}
  </ul>
  <p class="fine">The same list as data: <a href="/data/credits.json">credits.json</a></p>
</section>

</div>
</main>
""" + FOOT


# ---------------------------------------------------------------- 404
def notfound():
    return head("Page not found", "This page isn’t here.", None, index=False) + bar("") + f"""
<main id="main" class="page">
<div class="wrap narrow">
<section class="lost" aria-labelledby="h1">
  <div class="lost-fig" aria-hidden="true">
    <p class="bub on"><span>hm, where did it go?</span><svg width="18" height="14" viewBox="0 0 18 14"><path d="M2 0.5 L8.5 12 L15.5 0.5"/></svg></p>
    <img src="/img/ink/fig-lost.svg" width="176" height="232" alt="">
  </div>
  <div>
    <h1 id="h1">This page isn’t here.</h1>
    <p class="lead">It may have moved. These are the main pages:</p>
    <ul class="links ticks">
      <li><a href="/">Home</a></li>
      <li><a href="/download/">Download Lastbook</a></li>
      <li><a href="/library/">What’s in the library</a></li>
      <li><a href="/privacy/">Privacy and trust</a></li>
      <li><a href="/credits/">Credits</a></li>
    </ul>
  </div>
</section>
</div>
</main>
""" + FOOT


def write(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    print(f"{rel}: {len(text.encode())} bytes")


if __name__ == "__main__":
    write("index.html", home())
    # file names may break inside their grey chip; the other UI names stay whole
    write("download/index.html", re.sub(r'<b>(Lastbook[-.][^<]*)</b>', r'<b class="f">\1</b>', download()))
    write("library/index.html", library())
    write("privacy/index.html", privacy())
    write("credits/index.html", credits())
    write("404.html", notfound())
