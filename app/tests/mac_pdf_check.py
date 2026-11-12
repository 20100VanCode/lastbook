"""On this Mac, off-screen: Whole PDF shows pictures drawn by PDFium, loads only the pages near the view, jumps by #page=N, and a PDF's script has nothing to run in. Never packaged.
  python mac_pdf_check.py NAME"""
import re, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, '/path/to/lastbook/app/tests')
from mac_driver import Run, DATA
r = Run(sys.argv[1])
try:
    assert r.wait_up(), 'not up'
    r.rec('geolocation', r.js("return await new Promise(ok => navigator.geolocation.getCurrentPosition(() => ok('GOT A FIX'), e => ok(e.message)))"))
    t0 = time.time()
    r.go('#/read/ea6f3ba491ab0a49?p=900&view=pdf', 'iframe.frame', 500)
    time.sleep(10)
    r.shot('whole-900.png')
    rows = r.log('bridge', t0)
    pages = sorted(int(m.group(1)) for x in rows for m in [re.search(r'pdf-page=(\d+)', x.get('t') or '')] if m)
    r.rec('pages asked', pages[:60])
    r.rec('viewer', [{k: x.get(k) for k in ('t', 'status', 'sent', 'ms', 'lane')} for x in rows if 'anatomy' in (x.get('t') or '') and 'pdf-page' not in (x.get('t') or '')])
    r.rec('slowest page ms', max([x.get('ms', 0) for x in rows if 'pdf-page' in (x.get('t') or '')] or [0]))
    r.rec('mem', r.mem())
    r.rec('outside', {k: v for k, v in r.outside().items() if k != 'pids'})
    r.rec('asks', r.log('asks', t0))
finally:
    r.stop()
