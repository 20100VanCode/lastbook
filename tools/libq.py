#!/usr/bin/env python3
"""Read-only query helper for curating the survival library.
  libq.py search "words"        full-text, grouped by document (best pages)
  libq.py titles "regex"        catalog titles/collections matching a regex
  libq.py doc <id>              metadata for a catalog id
  libq.py page <id> <n> [chars] text of page n (PDF file page; 1 for html/video)
  libq.py toc <id>              first line of every page (quick outline)
  libq.py zim "words"           encyclopedia (ZIM) article search via port 8879
"""
import json, re, sqlite3, sys, urllib.parse, urllib.request
from pathlib import Path
LIB = Path(__file__).resolve().parents[1] / 'library-data'
DB = LIB / 'search.sqlite'
_cat = None
def cat():
    global _cat
    if _cat is None: _cat = {r['id']: r for r in json.loads((LIB/'catalog.json').read_text())}
    return _cat
def pages(id):
    r = cat()[id]; t = (LIB/r['text_path']).read_text(errors='replace')
    return t.split('\n\f\n') if r['kind'] != 'pdf' or '\n\f\n' in t else t.split('\f')
def main(a):
    if a[0] == 'search':
        terms = re.findall(r'[\w-]+', a[1])
        expr = ' AND '.join('"%s"' % t for t in terms)
        con = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
        rows = con.execute("SELECT doc_id,title,collection,page,snippet(pages,6,'[',']','…',20),bm25(pages,0,5,2,1,0,0,1) s FROM pages WHERE pages MATCH ? ORDER BY s LIMIT 300", (expr,)).fetchall()
        g = {}
        for d, t, c, p, sn, s in rows:
            if d.startswith('metadata-'): continue
            g.setdefault(d, [t, c, []])[2].append((p, sn))
        for d, (t, c, ps) in list(g.items())[:int(a[2]) if len(a) > 2 else 25]:
            print(f'{d} | {t[:80]} | {c[:45]} | pages {[p for p,_ in ps[:8]]}')
            print('    ', ps[0][1].replace('\n', ' ')[:200])
    elif a[0] == 'titles':
        rx = re.compile(a[1], re.I)
        for r in cat().values():
            if r['kind'] == 'metadata': continue
            if rx.search(r['title'] + ' ' + r['collection']):
                print(f"{r['id']} | {r['kind']} | {r['title'][:90]} | {r['collection'][:40]} | {r.get('pages') or ''}p {r.get('duration') or ''}s")
    elif a[0] == 'doc':
        print(json.dumps(cat()[a[1]], indent=1))
    elif a[0] == 'page':
        ps = pages(a[1]); n = int(a[2]); print(f'[{len(ps)} pages]'); print(ps[n-1][:int(a[3]) if len(a) > 3 else 4000])
    elif a[0] == 'toc':
        for i, p in enumerate(pages(a[1]), 1):
            line = ' '.join(p.split())[:110]
            print(i, line)
    elif a[0] == 'zim':
        print(urllib.request.urlopen('http://127.0.0.1:8879/api/collection-search?q=' + urllib.parse.quote(a[1])).read().decode()[:4000])
if __name__ == '__main__': main(sys.argv[1:])
