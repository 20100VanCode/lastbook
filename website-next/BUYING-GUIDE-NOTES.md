# Buying guide: notes for the owner and for root

Preview work, not deployed, nothing committed. Written 12 November 2026.

## What it is

A page on the website only, `/buying-guide/`: what to have before an emergency, and what to look for when you buy it. Six sections: first aid, drinking water, food preparation and preservation, critical repairs, power, and general emergency preparedness. Every "what to look for" point links its source (FEMA, Ready.gov, EPA, NPS, USDA's home-canning centre, USFA, the National Weather Service, and one generator maker's manual). 10 of the 16 sources are also in the Lastbook library.

It is never part of the app (`web/`, `app/`, `engine/`), the library packs or `website/`.

## Files this page owns

| File | What |
|---|---|
| `data/buying-guide.json` | All the content, sources, and the one setting `ASSOCIATE_TAG` (empty) |
| `tools/buying_guide.py` | Builds `buying-guide/index.html` from the data. Imports `tools/build.py` for the site's head, header and footer, without changing it |
| `buying-guide/index.html` | Built output. Edit the JSON, not this |
| `buying-guide.css` | Styles for this page only. Loaded after `style.css` |
| `img/buying-guide/t-repair.svg` | Hand-drawn wrench and tape icon for the repairs section, in the `img/ink` style |

Build: `python3 -I tools/buying_guide.py`. Preview: `http://localhost:8933/buying-guide/` (launch config `website-next-buying-guide` in `.claude/launch.json`, a plain `http.server` on this folder).

## Amazon Associates status: not connected

- `ASSOCIATE_TAG` is empty. The page says: "Lastbook’s Amazon Associates account isn’t connected yet. Any Amazon links here are plain links and earn nothing."
- With a tag set, that note becomes the required statement "As an Amazon Associate I earn from qualifying purchases." plus one plain line. Links become `https://www.amazon.com/dp/ASIN/?tag=TAG` with `rel="sponsored noopener"`. The build refuses a tag that doesn't look like a tracking ID.
- **There are no product links yet.** Each item has an empty `products` list. Amazon's site blocks AI agents ("Access restricted … Continued access by an unauthorized AI agent violates Amazon's Conditions of Use"), so I did not browse Amazon or check any ASIN. I picked no products and wrote down no ASINs: an ASIN nobody could check would just be a guess. A product only shows once a person has opened its page and filled in `checked`.
- To add products, a person opens each Amazon product page, copies the ASIN and the listing's own title, and adds `{"asin", "name", "maker_says", "checked"}` to the item. Once the account is approved, Amazon's SiteStripe bar gives tagged links straight from product pages.

### Rules the page follows (read from Amazon's own pages on 12 Nov 2026)

Sources: Operating Agreement (updated 15 October 2025) and Program Policies / Participation Requirements (updated 14 April 2026), at affiliate-program.amazon.com/help/operating/…

- Disclosure: "As an Amazon Associate I earn from qualifying purchases.", shown "clearly and prominently" on the site. The page shows it near the top, under the title, whenever a tag is set.
- No prices or availability unless they come from Amazon's PA API or Creators API. No star ratings or review counts. No stored Amazon images. The page has none of these, and the data file says not to add them. (The site's CSP, `img-src 'self'`, would block Amazon images anyway.)
- Every link carries the tag as a URL parameter. No redirects, shorteners or cloaking. Links go straight to amazon.com.
- Not offline: Amazon bans Special Links in printed material, ebooks, mailings and client-side software other than approved mobile apps. That's another reason the app and the packs must never carry these links. Don't put the guide in a PDF either.
- No implying Amazon endorses Lastbook. No rewards for clicking. No buying through your own links.
- Sites need original content, publicly available at the address given in the application. The guide's sourced advice meets that.
- `rel="sponsored"` isn't in Amazon's text. It's used here as the usual web practice for paid links.

## What the owner still needs to give

1. **Whether the Associates account exists and is approved.** If not, apply at affiliate-program.amazon.com and list lastbook.org (and the buying guide URL) as the site.
2. **The tracking ID** (looks like `name-20`). Put it in `ASSOCIATE_TAG` in `data/buying-guide.json` and rebuild. Not invented, not set.
3. **Tax and payment details in the Associates account.** Amazon "may request tax information" and can hold payment until it's given. It also needs a payment method (direct deposit, gift card or check). For a US account that's the account holder's legal name, country and US tax ID, done in Amazon's own tax interview. I can't see or do this part.
4. **Which country store.** The page uses `marketplace: https://www.amazon.com` (US). Other stores need separate Associates accounts.
5. **Which products to list**, picked and checked by a person, as above.
6. **The 180-day / 3-sales rule.** It wasn't on the pages I read, so I didn't rely on it. The owner should check the current account-approval terms inside Associates Central.

## Changes proposed for root's files (not made, Codex owns these)

### `tools/build.py`

1. Header nav. Add the guide to `NAV`:

```python
NAV = [("/download/", "Download"), ("/library/", "Library"), ("/buying-guide/", "Buying guide"), ("/privacy/", "Privacy"), ("/credits/", "Credits")]
```

2. Footer. In `FOOT`, after the `What’s in the library` link:

```html
      <a href="/buying-guide/">Buying guide</a>
```

3. Build the guide with the rest, so its header, footer and `style.css` hash stay current. At the end of `if __name__ == "__main__":`

```python
    import buying_guide
    write(buying_guide.OUT, buying_guide.page(json.loads(buying_guide.DATA.read_text()))[0])
```

Until then, run `python3 -I tools/buying_guide.py` after any `build.py` or `style.css` change, so the guide picks up the new `style.css?v=` hash.

4. Privacy page copy. `privacy()` says "No analytics, ads or tracking." That stays true for the site, but the guide has (or will have) paid links. Proposed replacement for that `<li>`:

```html
  <li>No analytics, ads or tracking. The buying guide has Amazon links that may earn Lastbook a small commission; Amazon sets its own cookies only if you open amazon.com.</li>
```

and below the list, one line:

```html
<p>The Lastbook app has no shop, no ads and no links out. It never goes online.</p>
```

### `sitemap.xml`

Add `https://lastbook.org/buying-guide/`.

### `vercel.json` (optional)

Nothing is required: the CSP already allows this page, and links to amazon.com aren't limited by it. To cache the hashed CSS for a year, add `buying-guide.css` to the immutable rule: `"source": "/(style.css|os.js|crowd.js|credits/credits.js|buying-guide.css)"`.

## Link check, 12 Nov 2026

- All 24 local links and files load (200), and every `#` anchor exists.
- 13 of the 16 external source links returned 200 to a scripted check.
- `fema.gov` returned 403 to the script for 3 PDFs. In the built-in browser, `basic_preparedness.pdf` downloaded as a file, so it's live. **Not checked:** `fema.gov/pdf/library/f&web.pdf` and `fema_earthquakes_fema-p-530-earthquake-safety-at-home-march-2020.pdf`. Both are in the Lastbook library. Open them by hand before launch.
- Amazon: no product links yet, so there's nothing to check.

## Checked in the browser

At 1280 px and 375 px (phone): no sideways scroll, no console errors, and the site's own header, footer, font and ink drawings.
