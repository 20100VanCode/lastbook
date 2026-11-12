// Credits list. Built with textContent only; the data is never treated as HTML.
const list = document.getElementById('owners');
const noteEl = document.getElementById('ownernote');
const searchBox = document.getElementById('search');
const input = document.getElementById('q');
const statusEl = document.getElementById('searchstatus');
const loadError = document.getElementById('loaderror');

const fold = s => s.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();

function line(cls, text){
  const span = document.createElement('span');
  span.className = cls;
  span.textContent = text;
  return span;
}

function whatLine(o){
  const words = [];
  if(o.videos) words.push('videos');
  if(o.documents) words.push('documents');
  if(o.collections) words.push('collections');
  const joined = words.join(', ');
  return joined.charAt(0).toUpperCase() + joined.slice(1);
}

function build(data){
  const rows = data.owners.map(o => {
    const li = document.createElement('li');
    li.append(line('owner', o.name));
    const what = whatLine(o);
    if(what) li.append(line('what', what));
    if(o.source) li.append(line('from', 'From ' + o.source));
    list.append(li);
    return {li, key:fold([o.name, what, o.source].join(' '))};
  });

  noteEl.textContent = data.note;
  noteEl.hidden = !data.note;
  list.hidden = false;

  input.addEventListener('input', () => {
    const q = fold(input.value.trim());
    let shown = 0;
    rows.forEach(r => {
      const hit = r.key.includes(q);
      r.li.hidden = !hit;
      if(hit) shown++;
    });
    statusEl.textContent = !q ? ''
      : !shown ? 'No match. Try another word.'
      : shown === 1 ? '1 name' : shown + ' names';
  });
}

fetch('../data/credits.json')
  .then(r => {
    if(!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  })
  .then(build)
  .catch(() => {
    searchBox.hidden = true;
    loadError.hidden = false;
  });
