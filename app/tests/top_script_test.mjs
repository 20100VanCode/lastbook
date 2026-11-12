// Runs bridge.top_script() against stand-ins for window and fetch. Usage: node top_script_test.mjs <script file> <origin> <key> <poll 0|1>
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const [, , file, origin, key, poll] = process.argv;
const src = readFileSync(file, 'utf8');
const u = new URL(origin + '/');
function world(top, winOrigin) {
  const calls = [];
  const fetchStub = async (input, init) => {
    const r = input instanceof Request ? input : new Request(new URL(input, 'https://lastbook.invalid/'), init);
    calls.push({ url: r.url, method: r.method, key: r.headers.get('X-Lastbook-Key'), type: r.headers.get('Content-Type') });
    if (r.url.endsWith('/__bridge/stream/start')) return new Response('', { headers: { 'X-Bridge-Stream': 'a'.repeat(32), 'X-Bridge-Status': '200', 'X-Bridge-Headers': '[["Content-Type","text/event-stream"]]' } });
    if (r.url.endsWith('/next')) return new Response('data: hi\n\n', { headers: { 'X-Bridge-End': '1' } });
    return new Response('ok');
  };
  const win = { fetch: fetchStub, origin: winOrigin };
  win.top = top ? win : {};
  win.self = win;
  const sandbox = { window: win, location: { protocol: u.protocol, host: u.host }, Request, Response, Headers, URL, ReadableStream, DOMException, Uint8Array, JSON };
  vm.runInNewContext(src, sandbox);
  return { win, calls, patched: win.fetch !== fetchStub };
}
const out = {};
const a = world(true, origin);
out.top_patched = a.patched;
const abs = p => origin === 'lastbook://app' ? 'https://lastbook.invalid' + p : origin + p;  // node's Request refuses a custom scheme, so the Mac run uses a stand-in host
if (origin !== 'lastbook://app') {
  await a.win.fetch(origin + '/api/health');
  await a.win.fetch(origin + '/api/tool/x', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  await a.win.fetch('https://elsewhere.example/x', { method: 'POST', body: 'x' });
  await a.win.fetch(origin + '/ui/app.css');
  await a.win.fetch('https://elsewhere.example/y');
  const chat = await a.win.fetch(origin + '/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  out.chat_status = chat.status;
  out.chat_text = await chat.text();
}
out.calls = a.calls;
const frame = world(false, 'null');
out.frame_patched = frame.patched;
const topSandboxed = world(true, 'null');
out.sandboxed_top_patched = topSandboxed.patched;
console.log(JSON.stringify(out));
