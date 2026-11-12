"""Drives the real window over DevTools, one step of win_suite.js at a time. Records raw values; deciding pass or fail is left to the reader.
python -I -B -X utf8 win_driver.py RUN step,step,...
"""
import json
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cdp  # noqa: E402

BUILD = Path(r'C:\Users\you\app-test\app-build')
RUN = BUILD / 'logs' / sys.argv[1]
STEPS = sys.argv[2].split(',')
(RUN / 'shots').mkdir(parents=True, exist_ok=True)
rep = open(RUN / 'report.jsonl', 'a', encoding='utf-8', buffering=1)


def out(**kw):
    rep.write(json.dumps({'ts': round(time.time(), 3), **kw}, ensure_ascii=False) + '\n')


end = time.time() + 45
page = None
while time.time() < end and not page:
    try:
        page = next((t for t in cdp.targets(8941) if t['type'] == 'page' and t['url'].startswith('https://lastbook.invalid')), None)
    except OSError:
        pass
    time.sleep(0.3)
if not page:
    out(step='connect', error='no page target')
    sys.exit(1)
c = cdp.CDP(8941, page['webSocketDebuggerUrl'])
c.call('Runtime.enable')
c.call('Page.enable')
t = time.time()
while time.time() - t < 30 and not c.eval("!!document.querySelector('#main h1')"):
    time.sleep(0.2)
out(step='first-h1', secs=round(time.time() - t, 2), url=c.eval('location.href'))
c.eval((HERE / 'win_suite.js').read_text(encoding='utf-8') + ';0')
for name in STEPS:
    t0 = time.time()
    out(step='START', name=name)
    i = c.send('Runtime.evaluate', {'expression': f'runStep({json.dumps(name)})', 'returnByValue': True, 'awaitPromise': True})
    while i not in c.results and time.time() - t0 < 560:
        c.pump(0.25)
        qid = c.send('Runtime.evaluate', {'expression': 'typeof nextAsk==="function"?nextAsk():null', 'returnByValue': True})
        m = c.wait(qid, 90)
        ask = m.get('result', {}).get('result', {}).get('value')
        if not ask:
            continue
        ans = None
        if ask['what'] == 'shot':
            c.shot(RUN / 'shots' / (ask['name'] + '.png'))
        elif ask['what'] == 'click':
            c.click(ask['x'], ask['y'], ask.get('button', 'left'))
        elif ask['what'] == 'targets':
            ans = [[x['type'], x['url'][:120]] for x in cdp.targets(8941)]
        elif ask['what'] == 'mark':
            out(step='mark', name=ask['name'])
        c.call('Runtime.evaluate', {'expression': f'answerAsk({ask["id"]},{json.dumps(ans)})'})
    if i in c.results:
        m = c.results.pop(i)
        r = m.get('result', {})
        out(step=name, secs=round(time.time() - t0, 1), data=r.get('result', {}).get('value'), exc=r.get('exceptionDetails') and str(r['exceptionDetails'])[:400], err=m.get('error'))
    else:
        out(step=name, error='TIMED OUT in driver')
out(step='END', href=c.eval('location.href'), targets=[[x['type'], x['url'][:120]] for x in cdp.targets(8941)])
