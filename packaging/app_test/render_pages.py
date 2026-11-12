# The same list of pages in whatever library this window has open: words, images, what shows. PK_LIST json of paths, PK_OUT file name. Run once on the pack, once on the unstripped copy, and compare.
import json, os, time
paths = json.load(open(os.environ['PK_LIST'], encoding='utf-8')); out = {}; SHOT = set(json.loads(os.environ.get('PK_SHOT', '[]')))
for i, p in enumerate(paths):
    u = '/' + p.split('/').map(lambda x: x) if False else '/' + '/'.join(__import__('urllib.parse').parse.quote(x) for x in p.split('/'))
    E("document.body.className='v-read';document.querySelector('#main').innerHTML='<iframe class=\"frame\" style=\"width:100%;height:480px\" src=" + json.dumps(u)[1:-1] + "></iframe>';scrollTo(0,0)")
    time.sleep(1.2)
    r = frame_info(); t = feval("document.body?document.body.innerText:''"); w = feval("(()=>[...document.images].filter(i=>i.getAttribute('src')&&i.naturalWidth).length)()")
    if isinstance(r, dict):
        r.pop('textStart', None); r['loaded_imgs'] = w; r['text'] = t if isinstance(t, str) else ''
    out[p] = r
    if p in SHOT: shot(os.environ['PK_OUT'] + '-' + str(i))
    if (i + 1) % 10 == 0: print(i + 1, flush=True)
json.dump(out, open(L + '\\' + os.environ['PK_OUT'] + '.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('render done', len(out), flush=True)
