// Credits search. The list is already on the page; this only hides rows that don't match.
// On a narrow screen the long list folds after the first names, behind a "Show all" button.
const input = document.getElementById('q');
const statusEl = document.getElementById('searchstatus');
const list = document.getElementById('owners');
const fold = s => s.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
const rows = [...list.querySelectorAll('li')].map(li => ({li, key: fold(li.textContent)}));
const keep = +list.dataset.fold || 40;
const narrow = window.matchMedia('(max-width: 600px)');
let open = !narrow.matches || rows.length <= keep + 5;
let more = null;
if (!open) {
  more = document.createElement('button');
  more.type = 'button';
  more.className = 'btn-2 more-btn';
  more.setAttribute('aria-controls', 'owners');
  more.setAttribute('aria-expanded', 'false');
  more.textContent = 'Show all ' + rows.length + ' names';
  list.after(more);
  more.addEventListener('click', () => { open = true; show(); more.remove(); });
}
function show() {
  const q = fold(input.value.trim());
  let shown = 0;
  rows.forEach((r, i) => {
    const hit = q ? r.key.includes(q) : (open || i < keep);
    r.li.hidden = !hit;
    if (hit) shown++;
  });
  if (more) more.hidden = !!q;
  statusEl.textContent = !q ? '' : !shown ? 'No match. Try another word.' : shown === 1 ? '1 name' : shown + ' names';
}
input.addEventListener('input', show);
show();
