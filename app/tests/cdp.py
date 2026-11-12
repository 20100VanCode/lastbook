"""The least DevTools client that can drive one page: standard library only. Test code, never packaged."""
import base64
import json
import os
import socket
import struct
import urllib.request


def targets(port):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return json.load(opener.open(f'http://127.0.0.1:{port}/json/list', timeout=5))


class CDP:
    def __init__(self, port, ws_url):
        path = ws_url.split(str(port), 1)[1]
        self.s = socket.create_connection(('127.0.0.1', port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f'GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        buf = b''
        while b'\r\n\r\n' not in buf:
            buf += self.s.recv(4096)
        head, self.buf = buf.split(b'\r\n\r\n', 1)
        if b' 101 ' not in head.split(b'\r\n')[0]:
            raise OSError(head[:200])
        self.n = 0
        self.results = {}
        self.events = []

    def _read(self, n):
        while len(self.buf) < n:
            d = self.s.recv(1 << 20)
            if not d:
                raise EOFError
            self.buf += d
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _frame(self):
        data = b''
        while True:
            b0, b1 = self._read(2)
            n = b1 & 0x7f
            if n == 126:
                n = struct.unpack('>H', self._read(2))[0]
            elif n == 127:
                n = struct.unpack('>Q', self._read(8))[0]
            data += self._read(n)
            if b0 & 0x80:
                return b0 & 0x0f, data

    def send(self, method, params=None):
        self.n += 1
        msg = json.dumps({'id': self.n, 'method': method, 'params': params or {}}).encode()
        mask = os.urandom(4)
        n = len(msg)
        head = bytes([0x81]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack('>H', n) if n < 65536 else bytes([0x80 | 127]) + struct.pack('>Q', n))
        self.s.sendall(head + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(msg)))
        return self.n

    def pump(self, timeout=0.3):
        self.s.settimeout(timeout)
        try:
            op, data = self._frame()
        except (socket.timeout, TimeoutError):
            return False
        finally:
            self.s.settimeout(30)
        if op == 1:
            m = json.loads(data)
            if 'id' in m:
                self.results[m['id']] = m
            else:
                self.events.append(m)
        return True

    def wait(self, i, seconds=60):
        import time
        end = time.time() + seconds
        while i not in self.results:
            if time.time() > end:
                raise TimeoutError(i)
            self.pump(1)
        return self.results.pop(i)

    def call(self, method, params=None, seconds=60):
        m = self.wait(self.send(method, params), seconds)
        if 'error' in m:
            raise RuntimeError(m['error'])
        return m['result']

    def eval(self, expr, seconds=60):
        r = self.call('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': True}, seconds)
        if 'exceptionDetails' in r:
            raise RuntimeError(json.dumps(r['exceptionDetails'])[:600])
        return r['result'].get('value')

    def shot(self, path):
        with open(path, 'wb') as f:
            f.write(base64.b64decode(self.call('Page.captureScreenshot', {'format': 'png'})['data']))

    def click(self, x, y, button='left'):
        self.call('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': x, 'y': y})
        self.call('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': x, 'y': y, 'button': button, 'clickCount': 1})
        self.call('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': x, 'y': y, 'button': button, 'clickCount': 1})
