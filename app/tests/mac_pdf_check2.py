"""Off-screen: Whole PDF jump, seen two ways: the view's own snapshot and the window server's copy of the window. Never packaged."""
import subprocess, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, '/path/to/lastbook/app/tests')
from mac_driver import Run
import Quartz
r = Run(sys.argv[1])
try:
    assert r.wait_up(), 'not up'
    r.go('#/read/med-2e83e22162a9a006?p=202&view=pdf', 'iframe.frame', 300); time.sleep(6); r.shot('snap.png')
    w = [x for x in Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionAll, 0) if x.get('kCGWindowOwnerPID') == r.p.pid and x.get('kCGWindowLayer') == 0]
    r.rec('windows', [(x['kCGWindowNumber'], dict(x['kCGWindowBounds']), x.get('kCGWindowIsOnscreen')) for x in w])
    for x in w:
        subprocess.run(['/usr/sbin/screencapture', '-x', '-o', '-l', str(x['kCGWindowNumber']), str(r.out / 'shots' / f"win-{x['kCGWindowNumber']}.png")])
finally:
    r.stop()
