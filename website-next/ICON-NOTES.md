# App icon on website-next (12 Nov 2026)

The new app icon (the smiling open book) replaced these files in place:
favicon.svg, favicon.ico (16, 32, 48), apple-touch-icon.png (180, opaque: iOS rounds it), img/icon-192.png, img/icon-512.png.

They are made by `packaging/icon/make_icons.py` in the repo; rerun it rather than editing them by hand.

No `<link>` change is needed: index.html, 404.html and tools/build.py already link /favicon.ico, /favicon.svg,
/apple-touch-icon.png and /site.webmanifest, and site.webmanifest already lists img/icon-192.png and img/icon-512.png.
og.png, the hero wordmark and the mascot art were left as they were.

Optional, for Codex if wanted: site.webmanifest's theme_color and background_color (#F4F2EC) still suit the cream tile (#F8F3E9).
