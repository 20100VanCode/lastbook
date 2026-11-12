"""Can the port and connection checks see anything at all? Runs the packaged app with a stub on 127.0.0.1:8943 standing in for a model (no model runs), so the app's own
Python makes a real loopback connection, then reads what nettop and lsof recorded for the app's process. Also shows Ask with a responding stub.
app_net_control.py DATA_FOLDER"""
import json, re, subprocess, sys, time
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path('/path/to/lastbook')
sys.path.insert(0, str(ROOT / 'derived/app-build/verify-mac/fin'))
import finlib
DATA = Path(sys.argv[1])
finlib.APP = str(ROOT / 'derived/app-build/mac/20261101-193435/dist/Lastbook.app')
finlib.EXE = finlib.APP + '/Contents/MacOS/Lastbook'
finlib.DYLIB = ROOT / 'derived/app-build/verify-mac/last/lbtest.dylib'
finlib.DATA = DATA
OUT = ROOT / 'derived/packs/app-walk/net-control'
OUT.mkdir(parents=True, exist_ok=True)
HOME = Path('/tmp/lastbook-scratch/home/net-control')
HOME.mkdir(parents=True, exist_ok=True)
_run = subprocess.run


def run_with_home(cmd, *k, **kw):
    if cmd and cmd[0] == '/usr/bin/open':
        cmd = cmd[:1] + ['--env', f'CFFIXED_USER_HOME={HOME}'] + cmd[1:]
    return _run(cmd, *k, **kw)


subprocess.run = run_with_home
a = finlib.App(str(OUT), model='http://127.0.0.1:8943', decoy=True, words=40, gap=0.25)
try:
    a.rec('up', bool(a.wait_up(120)))
    a.go('#/ask', '#chatIn', 1500)
    a.rec('status', a.js("return document.querySelector('#chatStatus').innerText"))
    a.js("const t=document.querySelector('#chatIn');t.value='how do I boil water';t.dispatchEvent(new Event('input',{bubbles:true}));return 1")
    r = a.js("const r=document.querySelector('#sendBtn').getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}")
    a.click_at(r['x'], r['y'])
    time.sleep(8)
    a.rec('during_answer', a.js("return document.querySelector('#chatLog').innerText.slice(-160)"))
    a.rec('lsof_during_answer', finlib.sh('/usr/sbin/lsof', '-nP', '-a', '-p', str(a.pid), '-i').splitlines()[1:])
    a.rec('fetch_web_from_page', a.js("try{const q=await fetch('https://example.invalid/');return q.status}catch(e){return String(e).slice(0,80)}"))
    a.rec('fetch_stub_from_page', a.js("try{const q=await fetch('http://127.0.0.1:8943/from-page');return q.status}catch(e){return String(e).slice(0,80)}"))
    time.sleep(6)
    a.rec('decoy_hits_now', list(a.decoy.hits)[:20])
finally:
    a.finish('close')
