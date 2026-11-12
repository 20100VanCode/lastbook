"""Test-only entry point for the real Windows window. Imports the same product modules and adds logging from outside them.
Never packaged. pythonw -I -B -X utf8 win_app.py --run NAME [--stub] [--cdp] [--netlog] [--real-browser] [--no-index]
"""
import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

sys.dont_write_bytecode = True
APP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(APP), str(APP.parent)]
BUILD = Path(r'C:\Users\you\app-test\app-build')
DATA = Path('C:\\Users\\you\\app-test\\app-only-proof\\data\\L\u00e4st \u06a9\u062a\u0627\u0628 #1 100%')
ap = argparse.ArgumentParser()
ap.add_argument('--run', required=True)
ap.add_argument('--stub', action='store_true')
ap.add_argument('--cdp', action='store_true')
ap.add_argument('--netlog', action='store_true')
ap.add_argument('--real-browser', action='store_true')
ap.add_argument('--no-index', action='store_true')
ap.add_argument('--no-runtime', action='store_true', help='make WebView2 look absent, through its own documented environment variable')
a = ap.parse_args()
RUN = BUILD / 'logs' / a.run
RUN.mkdir(parents=True, exist_ok=True)
(RUN / 'pid.txt').write_text(str(os.getpid()))
sys.stdout = sys.stderr = open(RUN / 'stdout.txt', 'a', encoding='utf-8', buffering=1)
TMP = BUILD / 'tmp'
TMP.mkdir(exist_ok=True)
os.environ.update(TEMP=str(TMP), TMP=str(TMP), SURVIVAL_MODEL_BASE='http://127.0.0.1:1', LASTBOOK_DATA=str(DATA))
sys.argv = ['main', '--data', str(DATA)]
if a.no_runtime:
    os.environ['WEBVIEW2_BROWSER_EXECUTABLE_FOLDER'] = r'C:\Users\you\app-test\app-build\no-such-runtime'
logf = open(RUN / 'events.jsonl', 'a', encoding='utf-8', buffering=1)
loglock = threading.Lock()


def log(d):
    with loglock:
        logf.write(json.dumps({'ts': round(time.time(), 3), **d}, ensure_ascii=False) + '\n')


import shell_windows as S  # noqa: E402
import bridge as B  # noqa: E402
args = S.BROWSER_ARGS
if a.cdp:
    args += ' --remote-debugging-port=8941'
if a.netlog:
    args += f' --log-net-log={RUN}\\netlog.json --net-log-capture-mode=Default'
if args != S.BROWSER_ARGS:
    os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = args
S.note = lambda **kw: log(kw)
real_ready = S.Shell.on_ready


def on_ready(self, sender, args_):
    real_ready(self, sender, args_)
    if args_.IsSuccess:
        threading.Thread(target=ui_ping, args=(self,), daemon=True).start()
        # A listener no product code has: if a page's postMessage could reach the host at all, this would log it.
        self.core.WebMessageReceived += S.guarded(lambda s, e: log({'kind': 'WEBMESSAGE-REACHED-HOST', 'src': str(e.Source)[:200]}))


def ui_ping(shell):
    """How long the window's own thread takes to get to something new."""
    with open(RUN / 'uilag.jsonl', 'a', buffering=1) as f:
        while True:
            t = time.time()
            shell.ui(lambda t=t: f.write(json.dumps({'ts': round(t, 3), 'lag_ms': round((time.time() - t) * 1000)}) + '\n'))
            time.sleep(0.2)


S.Shell.on_ready = on_ready


TIMES = {}


def timed(name, fn):
    def wrapped(*args_):
        t = time.perf_counter()
        try:
            return fn(*args_)
        finally:
            d = (time.perf_counter() - t) * 1000
            e = TIMES.setdefault(name, [0, 0.0, 0.0])
            e[0] += 1
            e[1] += d
            e[2] = max(e[2], d)
    return wrapped


S.Shell.on_request = timed('on_request', S.Shell.on_request)
real_ui = S.Shell.ui
S.Shell.ui = lambda self, fn: real_ui(self, timed('ui_fn', fn))
real_init = B.Bridge.__init__
THE = {}


def bridge_init(self, *pos, **kw):
    kw['log'] = log
    real_init(self, *pos, **kw)
    THE['b'] = self


B.Bridge.__init__ = bridge_init


def stats():
    with open(RUN / 'stats.jsonl', 'a', encoding='utf-8', buffering=1) as f:
        while True:
            time.sleep(2)
            if 'b' in THE:
                f.write(json.dumps({'ts': round(time.time(), 3), 'times': {k: [v[0], round(v[1]), round(v[2])] for k, v in TIMES.items()}, 'heap_mb': round(S.net().System.GC.GetTotalMemory(False) / 1048576), **THE['b'].stats()}) + '\n')


threading.Thread(target=stats, daemon=True).start()

import server  # noqa: E402
import assistant  # noqa: E402
if a.no_index:
    real_engine_init = server.init
    server.init = lambda no_index=False: real_engine_init(True)
if a.stub:
    stub_log = open(RUN / 'stub.jsonl', 'a', encoding='utf-8', buffering=1)

    def stub_status():
        return {'model': 'stub', 'online': True, 'error': None, 'index': dict(server.INDEX.status) if server.INDEX else {'state': 'off'}}

    def stub_chat(messages, about, emit, cancelled):
        text = json.dumps(messages)[:200]
        stub_log.write(json.dumps({'chat': text, 't': time.time()}) + '\n')
        emit({'type': 'state', 'state': 'thinking'})
        out = ''
        for i in range(12):
            time.sleep(0.4)
            if cancelled():
                stub_log.write(json.dumps({'stopped_at_piece': i, 't': time.time()}) + '\n')
                return
            piece = f'piece{i} '
            out += piece
            emit({'type': 'delta', 'text': piece})
        emit({'type': 'done', 'answer': out, 'sources': [], 'consulted': [], 'invalid': [], 'latency': 0})

    assistant.model_status = stub_status
    assistant.chat = stub_chat

import main  # noqa: E402
print('test entry: starting', time.strftime('%H:%M:%S'), flush=True)
sys.exit(main.main())
