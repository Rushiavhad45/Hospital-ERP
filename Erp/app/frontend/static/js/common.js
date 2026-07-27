/* Dr. Palaskar Hospital ERP — shared runtime (no frameworks, CSP-safe). */
'use strict';

/* ------------------------------------------------------------ utilities */
function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
const $  = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const rupee = n => '₹' + Number(n ?? 0).toLocaleString('en-IN');
const fmtDate = s => s ? new Date(s + (s.length === 10 ? 'T00:00:00' : ''))
  .toLocaleDateString('en-IN', { day:'numeric', month:'short', year:'numeric' }) : '—';
const fmtDT = s => s ? new Date(s).toLocaleString('en-IN',
  { day:'numeric', month:'short', hour:'numeric', minute:'2-digit', hour12:true }) : '—';
const fmtTime = s => s ? new Date(s).toLocaleTimeString('en-IN',
  { hour:'numeric', minute:'2-digit', hour12:true }) : '—';
const todayISO = () => new Date().toISOString().slice(0, 10);
const fmtSlot = hm => {
  if (!hm) return '—';
  const [h, m] = hm.split(':').map(Number);
  const ap = h >= 12 ? 'PM' : 'AM';
  return `${((h + 11) % 12) + 1}:${String(m).padStart(2, '0')} ${ap}`;
};
const initials = name => (name || '?').split(' ').filter(Boolean)
  .slice(0, 2).map(w => w[0].toUpperCase()).join('');

function greetWord() {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
}

/* ------------------------------------------------------------ sound fx */
const SFX = (() => {
  let ctx = null;
  const enabled = () => localStorage.getItem('sfx') !== 'off';
  function beep(spec) {
    if (!enabled()) return;
    try {
      ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
      const t0 = ctx.currentTime;
      spec.forEach(([freq, start, dur, type = 'sine', gain = .08]) => {
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.type = type; o.frequency.value = freq;
        g.gain.setValueAtTime(0, t0 + start);
        g.gain.linearRampToValueAtTime(gain, t0 + start + .015);
        g.gain.exponentialRampToValueAtTime(.0001, t0 + start + dur);
        o.connect(g); g.connect(ctx.destination);
        o.start(t0 + start); o.stop(t0 + start + dur + .05);
      });
    } catch (_) { /* audio unavailable */ }
  }
  return {
    click:   () => beep([[620, 0, .06, 'square', .04]]),
    success: () => beep([[523, 0, .12], [659, .09, .12], [784, .18, .2]]),
    error:   () => beep([[196, 0, .2, 'sawtooth', .06], [147, .12, .25, 'sawtooth', .06]]),
    notify:  () => beep([[880, 0, .09], [1175, .1, .14]]),
    toggle() { localStorage.setItem('sfx', enabled() ? 'off' : 'on'); return enabled(); },
    enabled,
  };
})();

/* ------------------------------------------------------------ toasts */
function toast(msg, kind = 'ok') {
  let box = $('#toasts');
  if (!box) { box = document.createElement('div'); box.id = 'toasts'; document.body.appendChild(box); }
  const t = document.createElement('div');
  t.className = 'toast' + (kind === 'err' ? ' err' : kind === 'warn' ? ' warn' : '');
  t.textContent = msg;
  box.appendChild(t);
  if (kind === 'err') SFX.error(); else if (kind === 'ok') SFX.success(); else SFX.notify();
  setTimeout(() => { t.style.opacity = '0'; t.style.transition = '.3s'; }, 3600);
  setTimeout(() => t.remove(), 4000);
}

/* ------------------------------------------------------------ modal */
function modal(title, bodyHTML, footHTML = '') {
  closeModal();
  const bd = document.createElement('div');
  bd.className = 'backdrop'; bd.id = 'modal-bd';
  document.body.classList.add('modal-open');
  bd.innerHTML = `<div class="modal" role="dialog" aria-modal="true">
      <div class="mh"><h3>${esc(title)}</h3>
        <button class="iconbtn" data-action="close-modal" aria-label="Close">✕</button></div>
      <div class="mb2">${bodyHTML}</div>
      ${footHTML ? `<div class="mf">${footHTML}</div>` : ''}
    </div>`;
  bd.addEventListener('click', e => { if (e.target === bd) closeModal(); });
  document.body.appendChild(bd);
  const first = bd.querySelector('input,select,textarea,button:not(.iconbtn)');
  if (first) first.focus();
  return bd;
}
function closeModal() {
  $('#modal-bd')?.remove();
  document.body.classList.remove('modal-open');
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
/* tap outside the drawer closes it (mobile) */
document.addEventListener('click', e => {
  const sb = $('#sidebar');
  if (sb?.classList.contains('open')
      && !e.target.closest('#sidebar')
      && !e.target.closest('[data-action="burger"]')) {
    sb.classList.remove('open');
    document.body.classList.remove('nav-open');
  }
});

/* ------------------------------------------------------------ API */
async function api(path, { method = 'GET', body, form } = {}) {
  const opts = { method, headers: {}, credentials: 'same-origin' };
  if (form) { opts.body = form; }
  else if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  let res;
  try { res = await fetch(path, opts); }
  catch { throw new Error('Network error — is the server running?'); }
  if (res.status === 401 && !path.startsWith('/api/auth/')) {
    // Bounce to the sign-in page only from protected app shells; on /login
    // or the public site just surface the error (prevents redirect loops).
    const p = location.pathname;
    if (p.startsWith('/portal') || p.startsWith('/staff') || p.startsWith('/admin')) {
      location.href = '/login';
    }
    const e = new Error('Please sign in.'); e.status = 401; throw e;
  }
  let data = null;
  const text = await res.text();
  try { data = text ? JSON.parse(text) : null; } catch { data = null; }
  if (!res.ok) {
    const msg = data?.error?.message || data?.detail || `Request failed (${res.status})`;
    const err = new Error(msg); err.status = res.status; err.details = data?.error?.details;
    throw err;
  }
  return data;
}

/* ------------------------------------------------------------ session */
async function requireUser(roles) {
  try {
    const me = await api('/api/auth/me');
    if (roles && !roles.includes(me.role)) {
      location.href = me.role === 'PATIENT' ? '/portal'
        : me.role === 'SUPER_ADMIN' ? '/admin' : '/staff';
      return null;
    }
    return me;
  } catch { location.href = '/login'; return null; }
}
async function logout() {
  try { await api('/api/auth/logout', { method: 'POST' }); } catch (_) {}
  location.href = '/';
}


/* ------------------------------------------- responsive table labels */
/* Copies each table's column headers onto its cells (data-th) so the
   phone stylesheet can restyle rows as labelled cards. Runs for every
   .table rendered anywhere (views, modals) via a MutationObserver.      */
function enhanceTables(root = document) {
  root.querySelectorAll?.('table.table').forEach(tbl => {
    const heads = [...tbl.querySelectorAll('thead tr:last-child th')]
      .map(th => th.textContent.trim());
    if (!heads.length) return;
    tbl.querySelectorAll('tbody tr').forEach(tr => {
      const tds = tr.children;
      if (tds.length !== heads.length) return;       // colspan / empty rows
      for (let i = 0; i < tds.length; i++) {
        if (!tds[i].hasAttribute('data-th'))
          tds[i].setAttribute('data-th', heads[i]);
      }
    });
  });
}
new MutationObserver(muts => {
  if (muts.some(m => m.addedNodes.length)) {
    cancelAnimationFrame(enhanceTables._raf || 0);
    enhanceTables._raf = requestAnimationFrame(() => enhanceTables());
  }
}).observe(document.documentElement, { childList: true, subtree: true });

/* ------------------------------------------------------------ topbar */
function buildShell({ me, navItems, appName }) {
  const first = (me.full_name || '').startsWith('Dr') ? me.full_name.split(' ').slice(0, 2).join(' ')
    : (me.full_name || '').split(' ')[0];
  document.body.innerHTML = `
  <div class="shell">
    <aside class="sidebar" id="sidebar">
      <div class="brand"><img src="/static/img/logo2-320.png" alt="">
        <div><b>Dr. Palaskar Hospital</b><span>${esc(appName)}</span></div></div>
      ${navItems.map(n => `<button class="nav-link" data-view="${n.id}">
          <span class="ic">${n.icon}</span>${esc(n.label)}</button>`).join('')}
      <div class="foot">Reg. No: VVCMC/C-H-202/2014<br>Vasai (W) · Sunday closed</div>
    </aside>
    <div>
      <div class="topbar">
        <div class="flex">
          <button class="iconbtn burger" data-action="burger">☰</button>
          <div class="greet"><span class="muted small">${greetWord()},</span> <b>${esc(first)}</b></div>
        </div>
        <div class="flex">
          <button class="iconbtn" data-action="sfx" title="Sound effects">${SFX.enabled() ? '🔊' : '🔇'}</button>
          <span class="badge ${me.role === 'SUPER_ADMIN' ? 'orange' : me.role === 'STAFF' ? 'blue' : ''}">${esc(me.role.replace('_', ' '))}</span>
          <button class="btn ghost sm" data-action="logout">Sign out</button>
        </div>
      </div>
      <main class="content" id="view"></main>
    </div>
  </div>`;
}

/* ---------------------------------------------------- global delegation */
document.addEventListener('click', e => {
  const el = e.target.closest('[data-action]');
  if (!el) {
    if (e.target.closest('button,.tcard,.slot,.nav-link,.tab')) SFX.click();
    return;
  }
  const a = el.dataset.action;
  if (a === 'close-modal') { SFX.click(); closeModal(); }
  else if (a === 'logout') logout();
  else if (a === 'sfx') { el.textContent = SFX.toggle() ? '🔊' : '🔇'; }
  else if (a === 'burger') {
    const open = $('#sidebar')?.classList.toggle('open');
    document.body.classList.toggle('nav-open', !!open);
  }
  else if (a === 'print') window.print();
  else return;                       // handled — don't double-beep
  if (a !== 'sfx') return;
});

/* ------------------------------------------------------------ router */
function makeRouter(views, defaultView) {
  async function render() {
    const id = location.hash.replace('#', '') || defaultView;
    const view = views[id] || views[defaultView];
    $$('.nav-link').forEach(b => b.classList.toggle('active', b.dataset.view === id));
    $('#sidebar')?.classList.remove('open');
    document.body.classList.remove('nav-open');
    const box = $('#view');
    box.innerHTML = '<div class="loader"></div>';
    try { await view(box); }
    catch (err) {
      box.innerHTML = `<div class="card empty"><div class="big">😕</div>
        <h3>Couldn't load this page</h3><p class="muted">${esc(err.message)}</p></div>`;
    }
    window.scrollTo({ top: 0 });
  }
  window.addEventListener('hashchange', render);
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-view]');
    if (b) { location.hash = b.dataset.view; }
  });
  return render;
}

/* ------------------------------------------------ attendance calendar */
/* Month-view calendar with ‹ › navigation. `records` come from the
   attendance endpoint: [{day, status, hours, check_in, check_out}].       */
function renderAttCalendar(el, records) {
  const map = Object.fromEntries(records.map(r => [r.day, r]));
  const today = new Date();
  let cur = new Date(today.getFullYear(), today.getMonth(), 1);
  const MONTHS = ['January','February','March','April','May','June','July',
    'August','September','October','November','December'];

  const STATE = r => r.status === 'ABSENT' ? ['abs', 'Absent']
    : r.status === 'LEAVE' ? ['leave', 'On leave']
    : r.status === 'HALF_DAY' ? ['half', `Half day · ${r.hours?.toFixed(1) ?? 0} h`]
    : ['ok', `Present · ${r.hours?.toFixed(1) ?? 0} h`];

  function paint() {
    const y = cur.getFullYear(), m = cur.getMonth();
    const firstDow = new Date(y, m, 1).getDay();          // 0 = Sunday
    const daysIn = new Date(y, m + 1, 0).getDate();
    const cells = [];
    for (let i = 0; i < firstDow; i++) cells.push('<div class="ac-cell ac-pad"></div>');
    for (let d = 1; d <= daysIn; d++) {
      const dt = new Date(y, m, d);
      const iso = `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      const rec = map[iso];
      const isToday = dt.toDateString() === today.toDateString();
      const future = dt > today;
      let cls = 'ac-cell', body = '', tip = fmtDate(iso);
      if (dt.getDay() === 0) { cls += ' ac-sun'; body = '<span class="ac-tag">Closed</span>'; tip += ' · Sunday (closed)'; }
      else if (rec) {
        const [k, label] = STATE(rec);
        cls += ' ac-' + k;
        tip += ' · ' + label;
        if (rec.check_in) tip += ` · in ${fmtTime(rec.check_in)}` +
          (rec.check_out ? ` – out ${fmtTime(rec.check_out)}` : '');
        body = k === 'abs' ? '<span class="ac-tag red">Absent</span>'
          : k === 'leave' ? '<span class="ac-tag gray">Leave</span>'
          : `<span class="ac-hrs">${rec.hours ? rec.hours.toFixed(1) + ' h' : '—'}</span>
             ${rec.check_in ? `<span class="ac-io">${fmtTime(rec.check_in)}${rec.check_out ? ' – ' + fmtTime(rec.check_out) : ''}</span>` : ''}`;
      } else if (!future) { cls += ' ac-none'; }
      if (isToday) cls += ' ac-today';
      cells.push(`<div class="${cls}" title="${esc(tip)}">
        <span class="ac-d">${d}</span>${body}</div>`);
    }
    const monthHas = records.some(r => r.day.startsWith(`${y}-${String(m + 1).padStart(2, '0')}`));
    const prevOk = records.length && records[0].day < `${y}-${String(m + 1).padStart(2, '0')}-01`;
    const nextOk = (y < today.getFullYear()) || (y === today.getFullYear() && m < today.getMonth());
    el.innerHTML = `
      <div class="ac-head">
        <button class="iconbtn" id="ac-prev" ${prevOk ? '' : 'disabled'} aria-label="Previous month">‹</button>
        <b>${MONTHS[m]} ${y}</b>
        <button class="iconbtn" id="ac-next" ${nextOk ? '' : 'disabled'} aria-label="Next month">›</button>
      </div>
      <div class="attcal">
        ${['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d => `<div class="ac-dow">${d}</div>`).join('')}
        ${cells.join('')}
      </div>
      <div class="ac-legend">
        <span><i class="ac-dot ok"></i>Present</span>
        <span><i class="ac-dot half"></i>Half day</span>
        <span><i class="ac-dot abs"></i>Absent</span>
        <span><i class="ac-dot leave"></i>Leave</span>
        <span><i class="ac-dot sun"></i>Sunday</span>
      </div>
      ${monthHas ? '' : '<div class="tiny muted center">No attendance records for this month.</div>'}`;
    $('#ac-prev', el)?.addEventListener('click', () => { cur = new Date(y, m - 1, 1); paint(); });
    $('#ac-next', el)?.addEventListener('click', () => { cur = new Date(y, m + 1, 1); paint(); });
  }
  paint();
}

/* ---------------------------------------------------- status → badge */
function badge(status) {
  const map = {
    PAID:'', PRESENT:'', AVAILABLE:'', CONFIRMED:'', COMPLETED:'', ADMITTED:'', ACTIVE:'', DONE:'gray',
    PENDING:'orange', BOOKED:'blue', DRAFT:'gray', SCHEDULED:'blue', FINALIZED:'blue',
    IN_PROGRESS:'orange', OCCUPIED:'orange', HALF_DAY:'orange', SUBMITTED:'orange', LOW:'orange',
    CANCELLED:'red', NO_SHOW:'red', ABSENT:'red', REJECTED:'red', EMERGENCY:'red', MAINTENANCE:'red',
    DISCHARGED:'gray', LEAVE:'gray', APPROVED:'', WEEK_OFF:'gray',
  };
  const cls = map[status] ?? 'gray';
  return `<span class="badge ${cls}">${esc(String(status).replace(/_/g, ' '))}</span>`;
}

/* Attach ONE live click handler per element — re-attaching replaces the
   previous one (AbortController), so views can never stack duplicate
   handlers on persistent containers like #view.                          */
function on(el, handler) {
  el.__clickAC?.abort();
  el.__clickAC = new AbortController();
  el.addEventListener('click', handler, { signal: el.__clickAC.signal });
}

/* form → object */
function formData(formEl) {
  const o = {};
  new FormData(formEl).forEach((v, k) => {
    if (v === '' || v === null) return;
    o[k] = v;
  });
  return o;
}
