"""Every stripped page in a pack against the same page in the library, read only, by parser. No browser, no app.
For each: visible words lost, images lost, local references that point at nothing in the pack, and whether they pointed at something in the library.
compare_stripped.py PACK_FOLDER OUT.json"""
import csv, html.parser, json, re, sys, urllib.parse
from collections import Counter
from pathlib import Path
sys.dont_write_bytecode = True
PACK, OUT = Path(sys.argv[1]), Path(sys.argv[2])
LIB = Path('/path/to/lastbook/library-data').resolve()
SKIP = {'script', 'style', 'noscript', 'template'}
csv.field_size_limit(10**8)


class P(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.words, self.imgs, self.links, self.skip, self.css = [], [], [], 0, []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag in SKIP:
            self.skip += 1
        if tag == 'img':
            self.imgs.append(d.get('src') or d.get('data-src') or '')
        if tag in ('a', 'area') and d.get('href'):
            self.links.append(d['href'])
        if tag == 'link' and d.get('href'):
            self.css.append(d['href'])
        if tag in ('source', 'video', 'audio', 'embed') and d.get('src'):
            self.imgs.append(d['src'])

    def handle_endtag(self, tag):
        if tag in SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.words += data.split()


def parse(path):
    p = P()
    try:
        p.feed(path.read_text('utf-8', 'replace'))
    except Exception as e:
        p.words.append('PARSE-ERROR:' + str(e)[:40])
    return p


def local(ref):
    if not ref or ref.startswith(('#', 'data:', 'mailto:', 'tel:', 'javascript:', '//')) or re.match(r'^[a-z][a-z0-9+.-]*:', ref, re.I):
        return None
    return urllib.parse.unquote(ref.split('#')[0].split('?')[0])


def resolve(base, rel, ref):
    r = local(ref)
    if not r:
        return None
    if r.startswith('/'):
        return r.lstrip('/')
    parts = (Path(rel).parent / r).as_posix().split('/')
    out = []
    for x in parts:
        if x == '..':
            if out:
                out.pop()
        elif x not in ('.', ''):
            out.append(x)
    return '/'.join(out)


manifest = list(csv.DictReader(open(PACK / 'pack-manifest.tsv', newline=''), delimiter='\t', quoting=csv.QUOTE_NONE))
pages = [m for m in manifest if m['how'] == 'stripped' and m['path'].startswith('library-data/')]
tot = Counter()
rows = []
dead_img, dead_link = Counter(), Counter()
dead_kind = Counter()
for i, m in enumerate(pages):
    rel = m['path'][len('library-data/'):]
    a = parse(PACK / m['path'])
    src = LIB / rel
    if not src.is_file():
        tot['not_in_library_now'] += 1
        continue
    b = parse(src)
    wa, wb = Counter(a.words), Counter(b.words)
    lost = sum((wb - wa).values())
    gained = sum((wa - wb).values())
    tot['pages'] += 1
    tot['words_library'] += sum(wb.values())
    tot['words_lost'] += lost
    ia = [x for x in a.imgs if local(x)]
    ib = [x for x in b.imgs if local(x)]
    remote_b = [x for x in b.imgs if not local(x) and not x.startswith('data:') and x]
    tot['local_imgs_library'] += len(ib)
    tot['local_imgs_pack'] += len(ia)
    tot['remote_imgs_library'] += len(remote_b)
    tot['links_library'] += len(b.links)
    tot['links_pack'] += len(a.links)
    miss_i, miss_l = [], []
    for x in ia:
        t = resolve(None, rel, x)
        if t and not (PACK / 'library-data' / t).exists():
            there = (LIB / t).exists()
            miss_i.append([t, there])
            tot['dead_img_in_library_too' if not there else 'dead_img_pack_only'] += 1
    for x in a.links:
        t = resolve(None, rel, x)
        if t and not (PACK / 'library-data' / t).exists():
            there = (LIB / t).exists()
            miss_l.append([t, there])
            tot['dead_link_in_library_too' if not there else 'dead_link_pack_only'] += 1
            ext = Path(t).suffix.lower() or '(none)'
            dead_kind[('library' if there else 'nowhere') + ' ' + ext] += 1
    if lost > max(3, 0.01 * sum(wb.values())) or len(ia) < len(ib) or miss_i or miss_l or len(a.links) < len(b.links):
        rows.append({'path': rel, 'lost': lost, 'gained': gained, 'words': sum(wb.values()), 'lost_sample': [w for w, _ in (wb - wa).most_common(10)], 'imgs': [len(ia), len(ib)], 'links': [len(a.links), len(b.links)], 'dead_img': miss_i[:8], 'dead_link': miss_l[:8], 'n_dead_img': len(miss_i), 'n_dead_link': len(miss_l), 'changes': m['changes']})
    if i % 1000 == 0:
        print(i, len(pages), flush=True)
worst = sorted(rows, key=lambda r: r['lost'], reverse=True)[:30]
sumr = {'pages_stripped': len(pages), 'totals': dict(tot), 'pages_flagged': len(rows), 'pages_with_text_loss_over_1pct': sum(1 for r in rows if r['lost'] > max(3, 0.01 * r['words'])), 'pages_with_dead_img': sum(1 for r in rows if r['n_dead_img']), 'pages_with_dead_link': sum(1 for r in rows if r['n_dead_link']), 'dead_link_by_kind': dead_kind.most_common(25), 'worst_text': [{k: r[k] for k in ('path', 'lost', 'words', 'lost_sample', 'changes')} for r in worst]}
OUT.write_text(json.dumps({'summary': sumr, 'rows': rows}, indent=0))
print(json.dumps(sumr, indent=0))
