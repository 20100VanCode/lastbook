# Every record in this pack's catalog, and every stripped page, through the running window's own fetch: does it open, and what do the served bytes hold. PK_DATA = pack folder on this machine.
import json, os, time
PACK = os.environ['PK_DATA']
cat = json.load(open(PACK + r'\library-data\catalog.json', encoding='utf-8'))
strip = [l.split('\t')[0] for l in open(PACK + r'\pack-manifest.tsv', encoding='utf-8') if l.split('\t')[3:4] == ['stripped'] and l.startswith('library-data/')]
JS = r'''
async (items, n) => {
  const out = { n: items.length, ok: 0, bad: [] };
  let i = 0;
  const one = async () => { while (i < items.length) { const it = items[i++];
    try {
      const d = await fetch('/api/doc/' + encodeURIComponent(it[0])); if (!d.ok) { out.bad.push([it[0], 'doc', d.status]); continue }
      const j = await d.json(); const u = j.path ? '/' + j.path.split('/').map(encodeURIComponent).join('/') : null;
      if (j.kind === 'zim') { out.ok++; continue }
      if (!u) { out.bad.push([it[0], 'nopath']); continue }
      const f = await fetch(u, { headers: { Range: 'bytes=0-63' } }); await f.arrayBuffer();
      if (f.status !== 200 && f.status !== 206) out.bad.push([it[0], j.kind, f.status, u]); else out.ok++;
    } catch (e) { out.bad.push([it[0], String(e)]) } } };
  await Promise.all(Array.from({ length: n }, one)); out.bad = out.bad.slice(0, 200); return out;
}'''
t = time.time(); r = c.eval('(' + JS + ')(' + json.dumps([[x['id']] for x in cat]) + ',6)', 3000); r['secs'] = round(time.time() - t); rec('catalog-all', **r)
JS2 = r'''
async (paths, n) => {
  const out = { n: paths.length, ok: 0, status: {}, script: [], on: [], remote: [], cspMissing: 0, jsUrl: [], bytes: 0 };
  let i = 0; const RX = /<[a-z][^>]*\s(?:src|poster|data|background|action|formaction|ping)\s*=\s*["']?\s*(?:https?:)?\/\/[^>]*>/ig;
  const one = async () => { while (i < paths.length) { const p = paths[i++];
    try {
      const u = '/' + p.split('/').map(encodeURIComponent).join('/');
      const f = await fetch(u); const b = await f.text(); out.status[f.status] = (out.status[f.status] || 0) + 1; out.bytes += b.length;
      if (f.status !== 200) continue; out.ok++;
      if (!/script-src 'none'/.test(f.headers.get('content-security-policy') || '')) out.cspMissing++;
      if (/<script\b/i.test(b)) out.script.push(p);
      if (/<[a-z][^>]*\son[a-z]+\s*=/i.test(b)) out.on.push(p);
      const m = b.match(RX); if (m) out.remote.push([p, m[0].slice(0, 200)]);
      if (/href\s*=\s*["']?\s*javascript:/i.test(b)) out.jsUrl.push(p);
    } catch (e) { out.status['fail'] = (out.status['fail'] || 0) + 1 } } };
  await Promise.all(Array.from({ length: n }, one));
  for (const k of ['script', 'on', 'remote', 'jsUrl']) { out[k + 'Count'] = out[k].length; out[k] = out[k].slice(0, 25) } return out;
}'''
t = time.time(); r = c.eval('(' + JS2 + ')(' + json.dumps([p.removeprefix('library-data/') for p in strip]) + ',6)', 3000); r['secs'] = round(time.time() - t); rec('stripped-all', **r)
sh = c.eval("fetch('/api/shelves').then(r=>r.json())"); rec('shelves', shelves=sh)
print('check done', flush=True)
