"""Summarises a walk.jsonl. python3 walk_report.py small"""
import json, sys, re, collections
A = '/path/to/lastbook/derived/packs/app-test/' + sys.argv[1] + '/'
rows = [json.loads(l) for l in open(A + 'walk.jsonl', encoding='utf-8')]
K = lambda r: (r['h'].split('/') + [''])[1].split('?')[0]
print('pages', len(rows), collections.Counter(K(r) for r in rows))
print('.err boxes', [(r['h'][:80], r.get('h1', '')[:30], r['errs'][0][:160]) for r in rows if r.get('errs')][:30])
print('crash', [(r['h'], r['crash'][:100]) for r in rows if r.get('crash')][:10], 'stuck', [r['h'][:70] for r in rows if r.get('stuck')][:10])
print('broken imgs in app pages', [(r['h'][:70], r['broken'][:3]) for r in rows if r.get('broken')][:20])
print('empty notes', collections.Counter(e[:70] for r in rows for e in r.get('empties', [])))
print('notfound h1', [r['h'][:70] for r in rows if 'isn’t here' in r.get('h1', '')])
print('videos ready/err', collections.Counter((r['video']['ready'], r['video']['err'], r['video']['w'] > 0) for r in rows if r.get('video')))
print('video not ok', [(r['h'][:60], r['video']) for r in rows if r.get('video') and (r['video']['err'] or r['video']['ready'] < 1 or not r['video']['w'])][:12])
fr = [r for r in rows if r.get('frame')]
print('framed', len(fr), 'served status', collections.Counter((r.get('served') or {}).get('status') for r in fr))
print('served not ok', [(r['h'][:70], r['frame'][:90], r['served']) for r in fr if (r.get('served') or {}).get('status') not in (200, 206)][:50])
html = [r for r in fr if (r.get('served') or {}).get('bytes') is not None]
print('html served: script tags', sum(r['served']['script'] for r in html if K(r) == 'read'), 'on-attrs', sum(r['served']['onattr'] for r in html if K(r) == 'read'), 'csp missing', sum(not r['served']['csp'] for r in html))
print('zim served script tags', sum(r['served']['script'] for r in html if K(r) == 'wiki'))
fi = [r for r in fr if isinstance(r.get('frameinfo'), dict)]
print('frame scripts seen', sum(r['frameinfo'].get('scripts', 0) for r in fi if K(r) == 'read'), 'noframe', [r['h'][:50] for r in fi if r['frameinfo'].get('noframe')][:12], 'fail', [(r['h'][:50], r['frameinfo']) for r in fi if r['frameinfo'].get('fail') or r['frameinfo'].get('exc')][:6])
print('frame broken imgs', [(r['h'][:60], r['frameinfo']['url'][:60], r['frameinfo']['imgs'], r['frameinfo']['broken'][:4]) for r in fi if r['frameinfo'].get('broken')][:30])
print('frame imgs without src', [(r['h'][:40], r['frameinfo']['noSrc'], r['frameinfo']['imgs']) for r in fi if r['frameinfo'].get('noSrc')][:15])
print('thin frames (<30 words)', [(r['h'][:50], r.get('h1', '')[:30], r['frameinfo']['words']) for r in fi if K(r) == 'read' and r['frameinfo'].get('words', 99) < 30][:40])
print('reports etc', [x for x in json.load(open(A + 'walk-links.json')) if x[1] not in (200, 206)][:60])
print('shelf rows'); [print('  ', r['h'], r['h1'], r['len'], r.get('heads', [])[:10]) for r in rows if K(r) == 'shelf' and '?' not in r['h']]
