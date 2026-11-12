"""Real-window checks on this Mac, off-screen, with no model. Run one section per launch: ui, chat, nomodel, safety, links, restart."""
import json, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, '/path/to/lastbook/app/tests')
from mac_driver import Run

section, name = sys.argv[1], sys.argv[2]
B64 = "lastbook://app/videos/glass-manufacturing-processes/Laceface_Hickory_and_Phil_Siegel_Guest_Artist_Flameworking_Demo%20%5BREiWSUc8sTY%5D.mp4"
VIDEO = "/videos/glass-manufacturing-processes/Laceface_Hickory_and_Phil_Siegel_Guest_Artist_Flameworking_Demo%20%5BREiWSUc8sTY%5D.mp4"
SNAP = "return {hash:location.hash,title:document.title,h1:(document.querySelector('#main h1')||{}).innerText,len:document.getElementById('main').innerText.length,err:!!document.querySelector('.notice.err,.err')}"
COORD = "const r=(%s).getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2,w:r.width,h:r.height}"


def click(r, sel_expr):
    c = r.js(COORD % sel_expr)
    if not c or c.get('__error') or not c['w']:
        return {'no_target': c}
    r.cmd('click', x=c['x'], y=c['y'])
    return c


def ui(r):
    for n, h, sel in [('home', '#/', '#main h1'), ('search', '#/search?q=boil%20water', '#main a[href^="#/read"]'), ('topic', '#/t/water', '#main h1'), ('reader', '#/read/f7ff53bcaae9cc?p=2', 'img.pageimg'),
                      ('library', '#/library', '#main h1'), ('videos', '#/videos', '#main h1'), ('encyc', '#/encyclopedias', '#main h1'), ('map', '#/map', 'canvas'), ('ask', '#/ask', '#chatIn')]:
        r.go(h, sel, 1200)
        r.rec('route_' + n, r.js(SNAP))
        r.shot(n + '.png')
    r.rec('find_counts', r.js("const o={};for(const w of ['water','canning','generator']){o[w]=(await (await fetch('/api/find?q='+w)).json()).results.length}return o"))
    r.go('#/search?q=boil%20water', None, 800)
    r.go('#/library', None, 800)
    r.rec('js_back', r.js("history.back(); await sleep(1000); const a=location.hash; history.forward(); await sleep(1000); return [a,location.hash]"))
    r.cmd('back'); time.sleep(1.2)
    a = r.js("return location.hash")
    r.cmd('forward'); time.sleep(1.2)
    r.rec('native_back_forward', [a, r.js("return location.hash")])
    r.rec('pdf_image', r.js("location.hash='#/read/f7ff53bcaae9cc?p=3'; const i=await until(()=>{const x=document.querySelector('img.pageimg');return x&&x.naturalWidth?x:null}); return {w:i.naturalWidth,h:i.naturalHeight}"))
    r.go('#/read/f7ff53bcaae9cc?p=9&view=pdf', 'iframe.frame', 2500)
    r.rec('pdf_frame', r.js("const f=document.querySelector('iframe.frame');return {type:f.contentDocument&&f.contentDocument.contentType,plugin:!!(f.contentDocument&&f.contentDocument.querySelector('embed')),src:f.src.slice(-50)}"))
    r.shot('pdf-small.png')
    r.cmd('back'); time.sleep(1.5)
    r.rec('back_out_of_pdf', r.js("return {hash:location.hash,top:location.href}"))
    r.go('#/', None, 300)
    m0 = r.mem(); t0 = time.time()
    r.go('#/read/ea6f3ba491ab0a49?p=500&view=pdf', 'iframe.frame', 500)
    series = []
    for i in range(12):
        time.sleep(1); series.append(r.mem().get('WebContent'))
    r.rec('pdf_476MB', {'before': m0, 'webcontent': series, 'after': r.mem(), 'info': r.js("const f=document.querySelector('iframe.frame');return {type:f.contentDocument&&f.contentDocument.contentType,plugin:!!(f.contentDocument&&f.contentDocument.querySelector('embed')),src:f.src.slice(-50)}"),
                        'requests': [{k: x.get(k) for k in ('m', 'status', 'sent', 'ms', 'end', 'note')} for x in r.log('bridge', t0) if 'anatomy' in str(x.get('t'))][:8]})
    r.shot('pdf-476.png')
    r.go('#/', None, 300)
    r.go('#/wiki/appropedia_en_all_maxi_2026-02.zim/Solar_cooker', '#wframe', 3000)
    r.rec('zim', r.js("const f=document.querySelector('#wframe');const d=f.contentDocument;return {wtitle:document.querySelector('#wtitle').innerText,frame:d&&d.title,images:d?[...d.images].length:null,drawn:d?[...d.images].filter(i=>i.naturalWidth>0).length:null}"))
    r.shot('zim.png')
    r.go('#/wiki/appropedia_en_all_maxi_2026-02.zim/', '#wframe', 2500)
    r.rec('zim_main_redirect', r.js("return {wtitle:document.querySelector('#wtitle').innerText,hash:location.hash}"))
    r.go('#/', None, 300)
    r.go('#/read/99dd5e2cc78a16a0?view=web', 'iframe.frame', 2000)
    r.rec('saved_page', r.js("const f=document.querySelector('iframe.frame');return {src:f.src.slice(-60),sandbox:f.getAttribute('sandbox')}"))
    r.shot('saved.png')
    r.go('#/', None, 300)
    r.go('#/map?lat=39.0997&lon=-94.5786&z=14.00', 'canvas', 3000)
    r.rec('map', r.js("""const info=await (await fetch('/api/map/info')).json();const tile=await (await fetch('/api/map/tile/14/3887/6255')).text();const ter=await fetch('/api/map/terrain/14/3887/6255.png');const tb=await ter.blob();const b=await fetch('/api/map/bldg3d/3887/6255');const bb=await b.arrayBuffer();const pl=await (await fetch('/api/places?q=kansas')).json();
const us=[];for(let x=2795;x<2805;x++)for(let y=6543;y<6553;y++)us.push('/api/map/tile/14/'+x+'/'+y+'?burst');const t=performance.now();const rs=await Promise.all(us.map(u=>fetch(u).then(x=>x.status)));
return {info_keys:Object.keys(info.national||{}),tile:tile.length,terrain:[ter.status,tb.size],bldg:bb.byteLength,place:pl[0]&&pl[0].name,burst:[rs.length,rs.filter(s=>s==200).length,Math.round(performance.now()-t)]}"""))
    r.shot('map.png')
    r.js("document.getElementById('map-3d').click();await sleep(5000);return 1")
    r.rec('map_3d', r.js("return {text:[...document.querySelectorAll('#mapwrap *')].map(e=>e.childElementCount?'':e.textContent).join(' ').match(/[\\d,]+ buildings/)?.[0],canvases:document.querySelectorAll('#mapwrap canvas').length}"))
    r.shot('map3d.png')
    VID = """const v=document.querySelector('#vid');v.muted=true;await until(()=>v.readyState>=1||v.error,15000);await v.play();await sleep(3000);
const look=()=>{const c=document.createElement('canvas');c.width=16;c.height=9;const g=c.getContext('2d');g.drawImage(v,0,0,16,9);const d=g.getImageData(0,0,16,9).data;let mx=0;for(let i=0;i<d.length;i+=4)mx=Math.max(mx,d[i]+d[i+1]+d[i+2]);return {t:+v.currentTime.toFixed(1),rs:v.readyState,w:v.videoWidth,h:v.videoHeight,err:v.error&&v.error.code,maxPixel:mx}};
const out={dur:Math.round(v.duration),start:look()};const seek=async s=>{const t=performance.now();v.currentTime=s;await Promise.race([new Promise(r=>v.addEventListener('seeked',r,{once:true})),sleep(15000)]);const ms=Math.round(performance.now()-t);await sleep(2500);return {ms,...look()}};
out.mid=await seek(v.duration/2);out.nearEnd=await seek(v.duration-15);v.currentTime=v.duration-2;v.play();await Promise.race([new Promise(r=>v.addEventListener('ended',r,{once:true})),sleep(8000)]);out.ended=v.ended;v.pause();return out"""
    for n, vid in [('h264_1_75GB', 'video-REiWSUc8sTY'), ('moov_at_end', 'video-course-bd619204a41c6827'), ('av1', 'video-1eIUZ_6QulY'), ('vp9', 'video-Q55emDRUZUE')]:
        r.go('#/', None, 200)
        t0 = time.time()
        r.go('#/watch/' + vid, '#vid', 200)
        res = r.js(VID, timeout=70)
        res = res if isinstance(res, dict) else {'got': res}
        pieces = [x for x in r.log('bridge', t0) if x.get('lane') == 'large' and x.get('kind') == 'req']
        res['pieces'] = {'n': len(pieces), 'largest': max([x.get('sent') or 0 for x in pieces] or [0]), 'bad': [x.get('status') for x in pieces if x.get('status') not in (200, 206)][:5]}
        r.rec('video_' + n, res)
    r.shot('video.png')
    r.rec('local_storage_set', r.js("const old=localStorage.getItem('sg.macshell');localStorage.setItem('sg.macshell','set-'+Date.now());return {old,now:localStorage.getItem('sg.macshell')}"))
    r.rec('state', {k: v for k, v in r.cmd('state').items() if k != 'bridge'})
    r.rec('bridge_stats', r.cmd('state').get('bridge'))
    r.rec('bad_status', [{k: x.get(k) for k in ('t', 'status', 'lane')} for x in r.log('bridge') if x.get('kind') == 'req' and x.get('status') not in (200, 204, 206)][:30])
    r.rec('refused', [x for x in r.log('bridge') if x.get('kind') == 'refused'][:20])


def chat(r):
    r.go('#/', None, 300)
    r.rec('stream', r.js("const T=performance.now();const q=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[{role:'user',content:'self test'}]})});const rd=q.body.getReader();const at=[];for(;;){const {done}=await rd.read();if(done)break;at.push(Math.round(performance.now()-T))}return {status:q.status,pieces:at.length,first:at[0],last:at[at.length-1]}", timeout=20))
    r.rec('abort', r.js("const c=new AbortController();const q=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:'{\"messages\":[{\"role\":\"user\",\"content\":\"abort\"}]}',signal:c.signal});const rd=q.body.getReader();setTimeout(()=>c.abort(),700);let n=0;try{for(;;){const {done}=await rd.read();if(done)break;n++}return {reads:n,err:null}}catch(e){return {reads:n,err:e.name}}", timeout=20))
    time.sleep(1)
    r.rec('stub_log', r.log('stub')[-4:])
    r.go('#/ask', '#chatIn', 500)
    r.js("const t=document.querySelector('#chatIn');t.value='how do I boil water';t.dispatchEvent(new Event('input',{bubbles:true}));return 1")
    click(r, "document.querySelector('#sendBtn')")
    time.sleep(1.5)
    r.rec('ui_mid', r.js("return {text:document.querySelector('#chatLog').innerText.slice(-120)}"))
    r.js("await until(()=>document.querySelector('#chatLog').innerText.includes('test stub, no model'),12000);await sleep(300);return 1", timeout=20)
    r.rec('ui_end', r.js("return {text:document.querySelector('#chatLog').innerText.slice(-200),buttons:[...document.querySelectorAll('#chatLog [data-act]')].map(b=>b.dataset.act)}"))
    r.shot('chat.png')
    t0 = time.time()
    r.rec('export_click', click(r, "document.querySelector('[data-act=export]')"))
    time.sleep(2)
    r.rec('export_asks', r.log('asks', t0))
    f = r.out / 'saved-download.txt'
    r.rec('export_file', f.read_text()[:300] if f.exists() else None)
    r.rec('scripted_export_no_gesture', r.js("const n=document.createElement('a');n.href=URL.createObjectURL(new Blob(['x']));n.download='scripted.txt';document.body.append(n);n.click();await sleep(800);return 1"))
    r.rec('asks_after_scripted', r.log('asks', t0))
    t0 = time.time()
    r.go('#/ask', '#clearChats', 300)
    r.rec('clear_click', click(r, "document.querySelector('#clearChats')"))
    time.sleep(1)
    r.rec('confirm_seen', r.log('asks', t0))
    r.rec('chats_after', r.js("return document.querySelector('#chatSide').innerText.slice(0,120)"))
    r.rec('confirm_direct', r.js("return [confirm('direct'), typeof alert('direct')]"))
    t0 = time.time()
    r.go('#/ask', '#chatIn', 300)
    r.js("const t=document.querySelector('#chatIn');t.value='stop me';t.dispatchEvent(new Event('input',{bubbles:true}));return 1")
    click(r, "document.querySelector('#sendBtn')")
    time.sleep(1.5)
    click(r, "document.querySelector('#sendBtn')")   # the same button is Stop while an answer is running
    time.sleep(1)
    r.rec('stop_button', {'stub': r.log('stub', t0), 'text': r.js("return document.querySelector('#chatLog').innerText.slice(-80)")})


def nomodel(r):
    r.go('#/ask', '#chatIn', 1500)
    r.rec('status', r.js("return document.querySelector('#chatStatus').innerText"))
    r.js("const t=document.querySelector('#chatIn');t.value='how do I boil water';t.dispatchEvent(new Event('input',{bubbles:true}));return 1")
    click(r, "document.querySelector('#sendBtn')")
    time.sleep(5)
    r.rec('answer', r.js("return document.querySelector('#chatLog').innerText.slice(0,400)"))
    r.shot('nomodel.png')
    r.rec('direct', r.js("const q=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[{role:'user',content:'x'}]})});return {status:q.status,body:(await q.text()).slice(0,300)}", timeout=30))
    r.rec('outside', r.outside())


def safety(r):
    r.go('#/', None, 300)
    r.rec('channel_top', r.js("return {webkit:typeof window.webkit,handlers:window.webkit&&Object.keys(window.webkit.messageHandlers||{}),pywebview:typeof window.pywebview,chrome:typeof window.chrome,external:typeof window.external}"))
    # native loads the window must refuse
    for u in ('https://example.invalid/', 'file:///etc/hosts', 'lastbook://app/pages/v3/topwin.html', 'lastbook://app/api/library', 'about:blank', 'lastbook://evil/'):
        r.cmd('load', url=u)
        time.sleep(0.5)
    r.rec('native_loads', {k: v for k, v in r.cmd('state').items() if k in ('url', 'loading')})
    P = ['/video-auth.json', '/documents/link-out.txt', '/documents/..%2fvideo-auth.json', '/tools/canary.txt', '/documents/x.info.json', '/ui/..%2fserver.py', '/documents/plain-canary-ok.txt', '/documents/v3-hardlink.txt', '/documents/verify-hardlink.txt', '/documents/v3-symlink.txt', '/%2e%2e/outside-canary.txt', '/__bridge/stream/start', 'lastbook://evil/api/topics', 'lastbook://APP/api/library']
    r.rec('bad_paths', r.js("const o={};for(const u of " + json.dumps(P) + "){try{const q=await fetch(u);o[u]=[q.status,/CANARY/.test(await q.text())]}catch(e){o[u]=e.name}}return o"))
    r.rec('post_no_key', r.js("const f=window.fetch;const i=document.createElement('iframe');document.body.append(i);const q=await i.contentWindow.fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(x=>x.status,e=>e.name);i.remove();return q"))
    r.rec('menu', r.cmd('menu', ids=['WKMenuItemIdentifierOpenLink', 'WKMenuItemIdentifierOpenLinkInNewWindow', 'WKMenuItemIdentifierDownloadLinkedFile', 'WKMenuItemIdentifierOpenImageInNewWindow', 'WKMenuItemIdentifierDownloadImage', 'WKMenuItemIdentifierOpenFrameInNewWindow', 'WKMenuItemIdentifierOpenMediaInNewWindow', 'WKMenuItemIdentifierDownloadMedia', 'WKMenuItemIdentifierSearchWeb', 'WKMenuItemIdentifierCopyLink', 'WKMenuItemIdentifierCopy']))
    r.rec('outside', r.outside())
    r.rec('focus', [{k: x.get(k) for k in ('active', 'key')} for x in r.log('mem')[-1:]] + [{'ever_active': any(x.get('active') or x.get('key') for x in r.log('mem'))}])


def links(r):
    b = lambda t0: [x.get('url') for x in r.log('browser', t0)]
    hsh = lambda: r.js("return location.hash")
    r.go('#/', None, 300)
    def add(html_):
        r.js("let d=document.getElementById('__t');if(!d){d=document.createElement('div');d.id='__t';d.style='position:fixed;left:0;top:0;width:400px;z-index:99999;background:#fff';document.body.append(d)}d.innerHTML=" + json.dumps(html_) + ";return 1")
    T = "document.querySelector('#__t a')"
    # http(s) from the app's top frame
    for n, h in [('blank_real_click', '<a target="_blank" href="https://example.invalid/blank">x</a>'), ('plain_real_click', '<a href="https://example.invalid/plain">x</a>')]:
        t0 = time.time(); add(h.replace('>x<', ' style="display:block;height:40px">x<')); c = click(r, T); time.sleep(0.8)
        r.rec(n, {'browser': b(t0), 'clicked': c, 'top': r.js("return location.href")})
    t0 = time.time(); add('<a target="_blank" href="https://example.invalid/scripted">x</a>')
    # This channel's own script counts as a gesture to WebKit, so these wait until any such gesture has run out, on a page timer.
    r.js("setTimeout(()=>document.querySelector('#__t a').click(),6000);return 1"); time.sleep(6.8)
    r.rec('blank_scripted_no_gesture', {'browser': b(t0), 'seen': r.log('leave', t0)})
    t0 = time.time(); r.js("setTimeout(()=>{window.__w=String(window.open('https://example.invalid/winopen-no-gesture'))},6000);return 1"); time.sleep(6.8)
    r.rec('window_open_no_gesture', {'browser': b(t0), 'seen': r.log('leave', t0), 'returned': r.js("return window.__w")})
    t0 = time.time(); add('<a href="https://example.invalid/plain-scripted">x</a>'); r.js("setTimeout(()=>document.querySelector('#__t a').click(),6000);return 1"); time.sleep(6.8)
    r.rec('plain_scripted_no_gesture', {'browser': b(t0), 'seen': r.log('leave', t0), 'top': r.js("return location.href")})
    t0 = time.time(); add('<a href="#" onclick="window.open(\'https://example.invalid/winopen-gesture\');return false" style="display:block;height:40px">x</a>'); click(r, T); time.sleep(0.8)
    r.rec('window_open_real_click', {'browser': b(t0), 'hash': hsh()})
    t0 = time.time(); add('<a target="_blank" href="ftp://example.invalid/x" style="display:block;height:40px">x</a>'); click(r, T); time.sleep(0.6)
    r.rec('ftp_real_click', {'browser': b(t0)})
    r.rec('windows', r.cmd('state').get('windows'))
    # the app's own 'open in its own tab' and 'original file' links
    r.go('#/', None, 200)
    r.go('#/wiki/appropedia_en_all_maxi_2026-02.zim/Solar_cooker', '#wopen', 1500)
    t0 = time.time(); c = click(r, "document.querySelector('#wopen')"); time.sleep(1.2)
    r.rec('zim_own_tab', {'clicked': c, 'hash': hsh(), 'href': r.js("return location.href"), 'browser': b(t0), 'windows': r.cmd('state').get('windows')})
    r.go('#/', None, 200)
    r.go('#/read/f7ff53bcaae9cc?p=2', 'img.pageimg', 800)
    r.js("document.querySelectorAll('details').forEach(d=>d.open=true);await sleep(200);const a=[...document.querySelectorAll('a[target=_blank]')].find(x=>/original file/i.test(x.innerText));a.scrollIntoView({block:'center'});window.__a=a;await sleep(300);return 1")
    t0 = time.time(); c = click(r, "window.__a"); time.sleep(1.5)
    r.rec('pdf_original_file', {'clicked': c, 'hash': hsh(), 'href': r.js("return location.href"), 'browser': b(t0)})
    r.shot('pdf-inside.png')
    r.go('#/', None, 200)
    for n, href in [('own_saved_page', '/pages/food-preservation/canning-99dd5e2cc78a16a0.html'), ('own_video', '/videos/first-aid/How_to_Recognize_Life-Threatening_Bleeding%20%5BOfSsPwil0kw%5D.mp4'), ('own_reports', '/reports/gap-closure-status.html'), ('own_api', '/api/library'), ('own_hash', '/#/library')]:
        for tgt in (' target="_blank"', ''):
            r.go('#/', None, 200)
            t0 = time.time(); add(f'<a{tgt} href="{href}" style="display:block;height:40px">x</a>'); c = click(r, T); time.sleep(0.8)
            r.rec(n + ('_blank' if tgt else '_plain'), {'hash': hsh(), 'href': r.js("return location.href"), 'browser': b(t0)})
    # real clicks inside a saved page
    r.go('#/', None, 200)
    r.go('#/read/v3-click?view=web', 'iframe.frame', 1500)
    t0 = time.time()
    fr = r.js("const f=document.querySelector('iframe.frame');f.scrollIntoView({block:'start'});await sleep(200);const q=f.getBoundingClientRect();return {x:q.left,y:q.top,w:q.width,h:q.height}")
    r.cmd('click', x=fr['x'] + 100, y=fr['y'] + 100); time.sleep(1)
    r.cmd('click', x=fr['x'] + 100, y=fr['y'] + 650); time.sleep(1)
    r.rec('saved_page_real_click', {'frame': fr, 'hash': hsh(), 'href': r.js("return location.href"), 'browser': b(t0), 'windows': r.cmd('state').get('windows'), 'engine': [x.get('t') for x in r.log('bridge', t0) if x.get('kind') == 'req'][:10]})
    r.shot('saved-click.png')
    r.rec('focus', {'ever_active': any(x.get('active') or x.get('key') for x in r.log('mem'))})


def restart(r):
    r.rec('local_storage_from_earlier_run', r.js("return localStorage.getItem('sg.macshell')"))
    r.rec('product_window', r.cmd('product_window'))
    r.rec('menu_bar', r.cmd('menu_bar'))
    r.rec('confirm_ok_button', r.cmd('real_panel', what='confirm', code=1000))
    r.rec('confirm_cancel_button', r.cmd('real_panel', what='confirm', code=1001))
    r.rec('alert', r.cmd('real_panel', what='alert', code=1000))
    r.rec('focus', {'ever_active': any(x.get('active') or x.get('key') for x in r.log('mem'))})
    r.cmd('close')
    t = time.time()
    try:
        r.p.wait(6)
    except Exception:
        pass
    r.rec('closing_the_window_ends_the_app', {'exit': r.p.poll(), 'after_s': round(time.time() - t, 2)})


args = {'restart': ['--stub-chat'], 'chat': ['--stub-chat'], 'ui': ['--stub-chat'], 'safety': ['--stub-chat'], 'links': ['--stub-chat'], 'nomodel': []}[section]
r = Run(name, *args)
try:
    r.rec('up', r.wait_up(40))
    globals()[section](r)
    if r.p.poll() is None:
        r.rec('outside_at_end', r.outside())
    rows = r.log('mem')
    r.rec('focus_all_samples', {'samples': len(rows), 'active': sum(1 for x in rows if x.get('active')), 'key': sum(1 for x in rows if x.get('key')), 'front_was_this_app': sum(1 for x in rows if x.get('front') == r.p.pid)})
finally:
    r.stop()
