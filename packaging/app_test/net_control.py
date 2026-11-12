# Control for the packet record: a process that does try to go off the computer, to an address reserved for documentation (192.0.2.1, never routed to a real host).
import os, socket, time
print('control pid', os.getpid(), flush=True)
u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); u.sendto(b'lastbook-control', ('192.0.2.1', 9))
s = socket.socket(); s.settimeout(1.5)
try: s.connect(('192.0.2.1', 9))
except OSError as e: print('tcp', e, flush=True)
try: socket.gethostbyname('control-lookup.lastbook.invalid')
except OSError as e: print('dns', e, flush=True)
