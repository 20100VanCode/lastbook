// Lastbook chooser. Available downloads are separate from planned pack choices.

const MAP = {ca:4.6, tx:5.05, vt:0.25, ak:null};   // others: 5
const OTHER_MAP = 5;
const BASE = {small:6, medium:62.07};   // Medium measured 12 Nov: 67.48 GB with its 5.40 GB California map
const ADD = {cc:96.3, fa:2.94};
const ALL_GB = 387.88;   // All measured 12 Nov: Lastbook-All.zip 387,878,571,619 bytes
const LIBRARY_READY = {small:true, medium:true, all:true};   // packs published and verified on downloads.lastbook.org
const AI_GB = 16947541728 / 1e9;

const $ = id => document.getElementById(id);
const stateSel = $('state');
const sizeInputs = [...document.querySelectorAll('input[name="size"]')];
const aiInputs = [...document.querySelectorAll('input[name="ai"]')];
const addons = $('addons');
const cc = $('cc');
const fa = $('fa');
const totalEl = $('total');
const recapEl = $('recap');
const announceEl = $('announce');
const linkEl = $('link');
const copyBtn = $('copy');
const copyStatus = $('copystatus');
const shareBtn = $('share');

const mobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent)
  || (navigator.maxTouchPoints>1 && /Mac/.test(navigator.platform));
const desktopSystem = mobile ? null
  : /Win/.test(navigator.platform) ? 'windows'
  : /Mac/.test(navigator.platform) ? 'mac' : null;

function read(){
  return {state:stateSel.value, size:sizeInputs.find(r => r.checked).value, cc:cc.checked, fa:fa.checked, ai:aiInputs.find(r => r.checked).value === 'yes'};
}

// Two decimal places, so adding 96.3 and 2.94 can't leave a stray digit.
function addSum(c){ return Math.round(((c.cc ? ADD.cc : 0) + (c.fa ? ADD.fa : 0)) * 100) / 100; }

function mapSize(state){
  return state in MAP ? MAP[state] : OTHER_MAP;
}

// Add the exact sizes, then round up once at the end. Only the map note says "up to".
function compute(c){
  const ai = c.ai ? AI_GB : 0;
  if(c.size === 'all'){
    const gb = Math.ceil(ALL_GB + ai);
    return {text:'About ' + gb + ' GB', gb};
  }
  const map = c.state ? mapSize(c.state) : null;
  const gb = Math.ceil(Math.round((BASE[c.size] + addSum(c) + (map || 0) + ai) * 100) / 100);
  return {text:'About ' + gb + ' GB' + (map === null ? ' + a map' : ''), gb};
}

// Same sum as the rows: 200 phone photos to a GB, rounded to read easily.
function photos(gb){
  const n = gb * 200;
  const step = n < 10000 ? 100 : 1000;
  return (Math.round(n / step) * step).toLocaleString('en-US');
}

function mapNote(state){
  if(!state) return 'Maps cover the US only for now.';
  const name = stateName(state);
  const map = mapSize(state);
  if(map === null) return name + " map: we don't know its size yet.";
  if(state in MAP) return name + ' map: up to ' + map + ' GB.';
  return name + ' map: up to about ' + OTHER_MAP + ' GB.';
}

function stateName(state){
  const opt = [...stateSel.options].find(o => o.value === state);
  return opt ? opt.textContent : '';
}

function sizeName(size){ return size.charAt(0).toUpperCase() + size.slice(1); }

// "Texas, Small, Corporals Corner", or just "All".
function choiceWords(c){
  if(c.size === 'all') return c.ai ? 'All, local AI' : 'All';
  const bits = [];
  if(c.state) bits.push(stateName(c.state));
  bits.push(sizeName(c.size));
  if(c.cc) bits.push('Corporals Corner');
  if(c.fa) bits.push('Firearms videos');
  if(c.ai) bits.push('local AI');
  return bits.join(', ');
}

function hashFor(c){
  if(c.size === 'all') return c.ai ? 'all-ai' : 'all';
  return (c.state ? c.state + '-' : '') + c.size + (c.cc ? '-cc' : '') + (c.fa ? '-fa' : '') + (c.ai ? '-ai' : '');
}

function parseHash(raw){
  if(raw === 'all' || raw === 'all-ai') return {size:'all', ai:raw === 'all-ai'};
  const m = /^(?:([a-z]{2})-)?(small|medium)(-cc)?(-fa)?(-ai)?$/.exec(raw);
  if(!m) return null;
  if(m[1] && !stateName(m[1])) return null;
  return {state:m[1] || '', size:m[2], cc:!!m[3], fa:!!m[4], ai:!!m[5]};
}

let announceTimer = 0;
function announce(text, delay){
  clearTimeout(announceTimer);
  announceTimer = setTimeout(() => { announceEl.textContent = text; }, delay);
}

function render(opts){
  const c = read();
  const isAll = c.size === 'all';
  const result = compute(c);

  // Under All the state and add-ons are hidden but keep their values for coming back.
  stateSel.hidden = isAll;
  $('mapnote').hidden = isAll;
  $('allmaps').hidden = !isAll;
  addons.hidden = isAll;
  $('moreall').hidden = !isAll;

  $('mapnote').textContent = mapNote(c.state);
  const extra = addSum(c);
  $('addnote').textContent = extra ? '+' + extra + ' GB' : '';
  $('statelabel').textContent = isAll ? '1. Your maps' : '1. Which state?';

  totalEl.textContent = result.text;
  $('totalnote').textContent = 'Like ' + photos(result.gb) + ' phone photos. An estimate.';
  $('fill').style.transform = 'scaleX(' + (result.gb / Math.ceil(ALL_GB + (c.ai ? AI_GB : 0))) + ')';
  $('barmax').textContent = c.ai ? 'All + AI: about 405 GB' : 'All: about 388 GB';
  $('ai-download').hidden = !c.ai;

  recapEl.textContent = choiceWords(c) + '.';
  $('waitline').textContent = c.size === 'small' && !c.cc && !c.fa
    ? 'Download the app and Small library separately. The available library includes a US base map.'
    : c.size === 'small'
      ? 'The Small library is available. Extra video packs are planned.'
      : c.size === 'medium' && !c.cc && !c.fa
        ? 'Download the app and Medium library separately. The Medium library includes a detailed map of California.'
        : c.size === 'medium'
          ? 'The Medium library is available. Extra video packs are planned.'
          : c.size === 'all'
            ? 'Download the app and All library separately. All includes every video pack and maps for the whole US.'
            : sizeName(c.size) + ' is planned and is not available to download yet.';
  const ready = c.size in LIBRARY_READY;
  $('library-download').hidden = c.size !== 'small';
  $('library-download-medium').hidden = c.size !== 'medium';
  $('library-download-all').hidden = c.size !== 'all';
  $('library-unavailable').hidden = ready;
  $('library-unavailable').textContent = sizeName(c.size) + ' library coming later. Choose Small, Medium or All to download an available library.';
  if(!opts.quiet) announce(choiceWords(c) + '. ' + result.text + '.', 300);

  const hash = hashFor(c);
  const url = location.origin + location.pathname + '#' + hash;
  linkEl.value = url;
  $('emailself').href = 'mailto:?subject=Lastbook&body=' + encodeURIComponent(url);
  $('question').href = 'mailto:hello@lastbook.org?subject='
    + encodeURIComponent('Lastbook: ' + choiceWords(c)) + '&body=' + encodeURIComponent(url);

  if(opts.writeHash){
    try { history.replaceState(null, '', '#' + hash); } catch (e) { /* the link field still works */ }
  }
  remember(c);
}

// This tab's memory, so going to Credits and back keeps your choices. No cookies.
// "kept" also holds the state and add-ons that the #all link leaves out.
function remember(c){
  try {
    sessionStorage.setItem('lastbook-choice', hashFor(c));
    sessionStorage.setItem('lastbook-kept', hashFor(c.size === 'all' ? {...c, size:'small'} : c));
  } catch (e) { /* the link still carries them */ }
}

function recall(key){
  try { return sessionStorage.getItem(key) || ''; } catch (e) { return ''; }
}

function restore(raw, opts){
  const parsed = parseHash(raw);
  if(!parsed) return false;
  sizeInputs.forEach(r => { r.checked = r.value === parsed.size; });
  aiInputs.forEach(r => { r.checked = (r.value === 'yes') === parsed.ai; });
  if(parsed.size !== 'all'){
    stateSel.value = parsed.state;
    cc.checked = parsed.cc;
    fa.checked = parsed.fa;
    if(parsed.cc || parsed.fa) addons.open = true;
  }
  render(opts);
  return true;
}

const onChange = () => render({writeHash:true});
stateSel.addEventListener('change', onChange);
sizeInputs.forEach(r => r.addEventListener('change', onChange));
aiInputs.forEach(r => r.addEventListener('change', onChange));
cc.addEventListener('change', onChange);
fa.addEventListener('change', onChange);

window.addEventListener('hashchange', () => {
  restore(location.hash.slice(1), {});
});

// Copy, share
let copiedTimer = 0;
copyBtn.addEventListener('click', async () => {
  try {
    if(!navigator.clipboard) throw new Error('no clipboard');
    await navigator.clipboard.writeText(linkEl.value);
    copyStatus.textContent = '';
    copyBtn.textContent = 'Copied';
    announce('Copied', 0);
    clearTimeout(copiedTimer);
    copiedTimer = setTimeout(() => { copyBtn.textContent = 'Copy link'; }, 2000);
  } catch (e) {
    clearTimeout(copiedTimer);
    copyBtn.textContent = 'Copy link';
    copyStatus.textContent = mobile ? "Couldn't copy. Press and hold the link."
      : "Couldn't copy. The link is selected. Press " + (desktopSystem === 'mac' ? 'Cmd' : 'Ctrl') + '+C.';
    linkEl.focus();
    linkEl.select();
  }
});

if(navigator.share){
  shareBtn.hidden = false;
  shareBtn.addEventListener('click', () => {
    navigator.share({title:'Lastbook', url:linkEl.value}).catch(() => {
      // Closing the share sheet is not a failure, and Copy link is right there for the rest.
    });
  });
}

// Words for a phone or tablet
if(mobile){
  $('carrytitle').textContent = 'Send this to your computer';
  $('carrytext').textContent = 'Open this link on a Mac or Windows computer to download Lastbook. It keeps your choices.';
}

// A link wins. With no link, pick up where this tab left off.
const start = location.hash.slice(1) || recall('lastbook-choice');
if(start === 'all' || start === 'all-ai') restore(recall('lastbook-kept'), {quiet:true});
if(!restore(start, {quiet:true, writeHash:!location.hash})) render({quiet:true});
