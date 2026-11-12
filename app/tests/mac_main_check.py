"""app/main.py's Mac path with no window: the real main() up to the shell's run(), which is replaced here."""
import os, subprocess, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
DATA = '/path/to/lastbook/derived/app-only-proof/mac/data'
CHILD = r'''
import os, sys, socket
sys.dont_write_bytecode = True
sys.modules['onnxruntime'] = None
os.environ['SURVIVAL_MODEL_BASE'] = 'http://127.0.0.1:9'
os.environ['SURVIVAL_DISABLE_INDEX_WATCH'] = '1'
sys.path.insert(0, APP)
import shell_macos
msgs = []
shell_macos.show_error = msgs.append
def fake_run(b):
    import retrieval, server
    print('RUN', type(b).__name__, b.mode, b.origin, 'AVAILABLE', retrieval.AVAILABLE, 'LIB', server.LIB, 'webview' in sys.modules, flush=True)
shell_macos.run = fake_run
real_bind = socket.socket.bind
def no_bind(*a): print('BIND CALLED', a, flush=True); return real_bind(*a)
socket.socket.bind = no_bind
import main
sys.argv = ['main'] + ARGV
print('MAIN RETURNED', main.main(), 'errors', msgs, flush=True)
'''
for name, argv in [('data', ['--data', DATA]), ('missing', ['--data', '/nonexistent-folder']), ('port', ['--data', DATA, '--port', '1']), ('lan', ['--data', DATA, '--lan']), ('headless', ['--data', DATA, '--headless'])]:
    code = CHILD.replace('APP', repr(APP)).replace('ARGV', repr(argv))
    p = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True, timeout=60)
    print('==', name, 'exit', p.returncode)
    print(p.stdout[-500:], p.stderr[-240:])
