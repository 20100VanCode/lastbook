#!/usr/bin/env python3
"""Check curated topic files: every doc id exists, pages are in range, ZIM paths resolve."""
import json, sys, urllib.request, urllib.parse
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
LIB = HERE / 'library-data'
cat = {r['id']: r for r in json.loads((LIB/'catalog.json').read_text())}
def items(t):
    for k in ('prepare', 'learn'):
        yield from ((k, i) for i in t.get(k, []))
    for c in t.get('choices', []):
        yield from (('choice:' + c.get('id', '?'), i) for i in c.get('read', []))
    for s in t.get('route', []):
        yield from (('route:' + str(s.get('title')), i) for i in s.get('read', []))
    for l in t.get('limits', []):
        if l.get('doc') or l.get('zim'): yield ('limits', l)
errors = 0
files = [Path(f) for f in sys.argv[1:]] or sorted((HERE/'content/topics').glob('*.json'))
for f in files:
    t = json.loads(f.read_text()); n = 0
    for where, i in items(t):
        n += 1
        if i.get('zim'):
            try: urllib.request.urlopen('http://127.0.0.1:8879/' + i['zim'].lstrip('/'), timeout=10).read(1)
            except Exception as e: print(f'{f.name} {where}: ZIM path fails {i["zim"]}: {e}'); errors += 1
            continue
        r = cat.get(i.get('doc'))
        if not r: print(f'{f.name} {where}: unknown doc {i.get("doc")}'); errors += 1; continue
        if r['kind'] == 'metadata': print(f'{f.name} {where}: use the video id, not metadata {i["doc"]}'); errors += 1
        p = i.get('page')
        if p and r.get('pages') and not (1 <= p <= r['pages']): print(f'{f.name} {where}: page {p} out of range for {i["doc"]} ({r["pages"]})'); errors += 1
        if not i.get('label') and where != 'limits': print(f'{f.name} {where}: missing label for {i.get("doc")}'); errors += 1
    print(f'{f.name}: {n} references checked')
print('ERRORS', errors); sys.exit(1 if errors else 0)
