"""Every stripped page in a pack against the same file in the real library, read-only: words lost, images lost, scripts left.
Opens only library files named in the pack's manifest, read-only. Writes under derived/packs/app-test/.
python3 compare_pages.py small|medium
"""
import html
import os
import re
import sys
import json
import urllib.parse
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

PROJECT = Path('/path/to/lastbook')
PACK = PROJECT / 'derived/packs' / sys.argv[1]
LIB = PROJECT / 'library-data'
OUT = PROJECT / 'derived/packs/app-test'
SKIP = {'script', 'style', 'template'}
WORD = re.compile(r"\w[\w'’-]*", re.U)
CSS_URL = re.compile(r'url\(\s*(?:"([^"]*)"|\'([^\']*)\'|([^)\s]+))\s*\)', re.I)
REMOTE = re.compile(r'^\s*(?:[a-z][a-z0-9+.-]*:|//)', re.I)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.words, self.skip, self.imgs, self.scripts, self.events, self.css, self.anchors = Counter(), 0, [], 0, 0, [], []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): v or '' for k, v in attrs}
        if tag == 'script':
            self.scripts += 1
        self.events += sum(1 for k in a if k.startswith('on'))
        if tag in SKIP:
            self.skip += 1
        if tag == 'img':
            self.imgs.append(('img', a.get('src', ''), a.get('srcset', ''), a.get('data-src', '') or a.get('data-lazy-src', ''), a.get('alt', '')))
        elif tag == 'source' and (a.get('src') or a.get('srcset')):
            self.imgs.append(('source', a.get('src', ''), a.get('srcset', ''), '', ''))
        elif tag == 'video' and a.get('poster'):
            self.imgs.append(('poster', a['poster'], '', '', ''))
        elif tag == 'link' and 'stylesheet' in a.get('rel', '').lower():
            self.css.append(a.get('href', ''))
        if a.get('style'):
            self.css += [m.group(1) or m.group(2) or m.group(3) or '' for m in CSS_URL.finditer(a['style'])]

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in SKIP:
            self.skip -= 1

    def handle_endtag(self, tag):
        if tag in SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.words.update(WORD.findall(data))


def parse(path):
    p = Page()
    raw = open(path, 'rb').read()
    p.feed(raw.decode('utf-8', 'replace'))
    p.close()
    return p, raw


def local(ref, page_rel, root):
    ref = ref.strip()
    if not ref or ref.startswith(('data:', '#')):
        return None
    if REMOTE.match(ref):
        return 'remote'
    ref = urllib.parse.unquote(ref.split('#')[0].split('?')[0])
    base = '' if ref.startswith('/') else os.path.dirname(page_rel)
    rel = os.path.normpath(os.path.join(base, ref.lstrip('/')))
    return rel


def main():
    rows, tot = [], Counter()
    with open(PACK / 'pack-manifest.tsv', encoding='utf-8') as f:
        next(f)
        pages = [ln.rstrip('\n').split('\t') for ln in f]
    pages = [p for p in pages if p[3] == 'stripped' and p[0].startswith('library-data/')]
    lost_words = Counter()
    for parts in pages:
        rel = parts[0].removeprefix('library-data/')
        orig_path, new_path = LIB / rel, PACK / parts[0]
        tot['pages'] += 1
        if not orig_path.is_file():
            tot['no_original'] += 1
            rows.append([rel, 'NO-ORIGINAL'] + [''] * 9)
            continue
        o, oraw = parse(orig_path)
        n, nraw = parse(new_path)
        wo, wn = sum(o.words.values()), sum(n.words.values())
        diff = o.words - n.words
        lost = sum(diff.values())
        lost_words.update(diff)
        tot['words_orig'] += wo
        tot['words_new'] += wn
        tot['words_lost'] += lost
        tot['scripts_orig'] += o.scripts
        tot['scripts_new'] += n.scripts
        tot['events_new'] += n.events
        if re.search(rb'<\s*script\b', nraw, re.I):
            tot['script_bytes_new'] += 1
        # Images. "lost" = a local picture the original could show that the pack cannot. "remote" = needed the web, so blank offline in both.
        lostimg = danglenew = remoteimg = okimg = oldbroken = emptyimg = 0
        def st(ref):
            r = local(ref, rel, LIB)
            if r is None or r == 'remote':
                return r
            return 'pack' if (PACK / 'library-data' / r).is_file() else 'lib' if (LIB / r).is_file() else 'neither'
        for kind, src, srcset, lazy, alt in o.imgs:
            s = st(src)
            if s == 'pack':
                okimg += 1
            elif s == 'lib':
                lostimg += 1
            elif s == 'neither':
                oldbroken += 1
            elif s == 'remote':
                remoteimg += 1
        for kind, src, srcset, lazy, alt in n.imgs:
            s = st(src)
            if s in ('lib', 'neither'):
                danglenew += 1
            if kind == 'img' and not src and not srcset:
                emptyimg += 1
        cssmiss = sum(1 for c in n.css if st(c) in ('lib', 'neither'))
        cssrem = sum(1 for c in n.css if st(c) == 'remote')
        for k, v in dict(img_ok=okimg, img_lost=lostimg, img_old_broken=oldbroken, img_remote=remoteimg, img_dangling_new=danglenew, img_empty_new=emptyimg, css_missing=cssmiss, css_remote=cssrem).items():
            tot[k] += v
        if wn < 30:
            tot['pages_under_30_words'] += 1
        rows.append([rel, wo, wn, lost, o.scripts, n.scripts, okimg, lostimg, remoteimg, danglenew, emptyimg, oldbroken, cssmiss, wn < 30])
    head = ['path', 'words_orig', 'words_new', 'words_lost', 'scripts_orig', 'scripts_new', 'img_ok', 'img_lost', 'img_remote_orig', 'img_dangling_new', 'img_empty_new', 'img_old_broken', 'css_missing', 'under30']
    with open(OUT / f'pages-compare-{sys.argv[1]}.tsv', 'w', encoding='utf-8') as f:
        f.write('\t'.join(head) + '\n')
        for r in rows:
            f.write('\t'.join(map(str, r)) + '\n')
    tot_d = dict(tot)
    tot_d['top_lost_words'] = lost_words.most_common(25)
    (OUT / f'pages-compare-{sys.argv[1]}.json').write_text(json.dumps(tot_d, indent=1), encoding='utf-8')
    print(json.dumps(tot_d, indent=0, ensure_ascii=False))


main()
