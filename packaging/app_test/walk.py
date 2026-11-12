# Runs inside vw.py py (stdin): walks every route of the app in the real window over DevTools, following every in-app link. Records raw values.
# Argument through the environment: PK_RUN, PK_LIMIT (per-kind cap on read/watch/wiki pages; 0 = none), PK_SEED (extra routes, json).
import json, os, re, time, collections
PROBE = r'''
(async (h) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const t0 = performance.now();
  const mm = document.querySelector('#main'); const mark = document.createElement('i'); mark.id = 'pkmark'; mm.append(mark);
  if (location.hash !== h) location.hash = h; else window.dispatchEvent(new HashChangeEvent('hashchange'));
  await sleep(60);
  const m = document.querySelector('#main');
  while (m.querySelector('#pkmark') && performance.now() - t0 < 25000) await sleep(40);
  const stuck = !!m.querySelector('#pkmark'); if (stuck) m.querySelector('#pkmark').remove();
  const busy = () => m.querySelector('.loading') || (m.querySelector('img.pageimg') && !m.querySelector('img.pageimg').complete) || (m.querySelector('video') && m.querySelector('video').readyState < 1 && !m.querySelector('video').error && !m.querySelector('.err'));
  while (busy() && performance.now() - t0 < 25000) await sleep(80);
  await sleep(150);
  const f = m.querySelector('iframe');
  let served = null;
  if (f) { await new Promise(r => { f.addEventListener('load', r, { once: true }); setTimeout(r, 2500) });
    const u = f.getAttribute('src').split('#')[0];
    if (!/\.pdf$/i.test(u)) { try { const x = await fetch(u); const b = await x.text(); served = { status: x.status, ct: x.headers.get('content-type'), bytes: b.length, script: (b.match(/<script\b/ig) || []).length, csp: /script-src 'none'/.test(x.headers.get('content-security-policy') || ''), onattr: (b.match(/<[a-z][^>]*\son[a-z]+\s*=/ig) || []).length } } catch (e) { served = { fail: String(e) } } }
    else { try { const x = await fetch(u, { headers: { Range: 'bytes=0-7' } }); served = { status: x.status, ct: x.headers.get('content-type') } } catch (e) { served = { fail: String(e) } } } }
  const imgs = [...m.querySelectorAll('img')];
  for (const i of imgs) { try { i.loading = 'eager' } catch {} }
  let tt = performance.now(); while (imgs.some(i => i.isConnected && i.getAttribute('src') && !i.complete) && performance.now() - tt < 6000) await sleep(80);
  const v = m.querySelector('video');
  const links = [...document.querySelectorAll('#main a[href], .foot a[href]')].map(a => [a.getAttribute('href'), (a.innerText || '').trim().slice(0, 70), a.target || '']);
  return { h, stuck, served, final: location.hash, ms: Math.round(performance.now() - t0), title: document.title, h1: (m.querySelector('h1') || {}).innerText || '', len: m.innerText.length,
    errs: [...m.querySelectorAll('.err,.errorbox,.error')].map(e => e.innerText.slice(0, 200)), empties: [...m.querySelectorAll('.empty')].map(e => e.innerText.slice(0, 160)),
    notices: [...m.querySelectorAll('.notice')].map(e => e.innerText.slice(0, 120)).slice(0,3),
    broken: imgs.filter(i => i.isConnected && i.getAttribute('src') && i.complete && !i.naturalWidth).map(i => i.getAttribute('src')).slice(0, 8), imgs: imgs.length,
    video: v ? { ready: v.readyState, dur: v.duration, err: v.error && v.error.message, src: v.getAttribute('src').slice(0, 120), w: v.videoWidth } : null,
    frame: f ? f.getAttribute('src').slice(0,160) : null, heads: [...m.querySelectorAll('h2,h3')].map(e=>e.innerText).slice(0,30), links, text: m.innerText.slice(0, 300) };
})
'''
def probe(h):
    try: return c.eval(PROBE + '(' + json.dumps(h) + ')', 60)
    except Exception as e: return {'h': h, 'crash': repr(e)[:300], 'links': []}
def key(h):   # same place, whichever page linked to it
    h = re.sub(r'([?&])(from|p|view|t)=[^&]*', r'\1', h); h = re.sub(r'&+', '&', h).replace('?&', '?'); return h.rstrip('?&')
LIMIT = int(os.environ.get('PK_LIMIT', '0'))
seeds = ['#/', '#/ask', '#/videos', '#/map', '#/library', '#/saved', '#/about', '#/prepare', '#/encyclopedias'] + json.loads(os.environ.get('PK_SEED', '[]'))
seen, todo, out, kinds = set(), list(seeds), open(L + '\\' + os.environ.get('PK_OUT', 'walk.jsonl'), 'a', encoding='utf-8', buffering=1), collections.Counter()
ext = collections.Counter(); t0 = time.time(); n = 0
while todo:
    h = todo.pop(0); k = key(h)
    if k in seen: continue
    seen.add(k)
    kind = (k.split('/') + [''])[1].split('?')[0]
    if LIMIT and kind in ('read', 'watch', 'wiki', 'collection') and kinds[kind] >= LIMIT: continue
    kinds[kind] += 1
    if kind == 'map': pass
    r = probe(k); r['from'] = None
    if r.get('frame') and not re.search(r'\.pdf(#|$)', r['frame'], re.I):
        try: r['frameinfo'] = frame_info()
        except Exception as e: r['frameinfo'] = {'fail': repr(e)[:200]}
    out.write(json.dumps(r, ensure_ascii=False) + '\n'); n += 1
    for href, txt, tgt in r.get('links', []):
        if href.startswith('#/'):
            kk = key(href)
            if kk not in seen and not kk.startswith('#/ask') and not kk.startswith('#/search'): todo.append(href)
        else: ext[href] += 1
    if n % 25 == 0: print(n, len(todo), round(time.time() - t0), dict(kinds), flush=True)
st = E("Promise.all(" + json.dumps(sorted(ext)) + ".map(u=>fetch(u.split('#')[0],{headers:{Range:'bytes=0-64'}}).then(r=>[u,r.status,r.headers.get('content-type')]).catch(e=>[u,String(e)])))", 300)
json.dump(st, open(L + '\\' + os.environ.get('PK_OUT', 'walk') + '.links.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('other links', len(st), 'not ok', [x for x in st if x[1] not in (200, 206)][:60])
print('done', n, round(time.time() - t0), dict(kinds))
print(json.dumps(agent('summary'), ensure_ascii=False)[:900])
