/* UI smoke tests — load the REAL pages with the REAL scripts in jsdom
   against a running server (http://127.0.0.1:8000) and assert behaviour.

   Run:  cd tests/ui && npm i && node smoke.mjs
   (start the server first: python run.py)                                */
import { JSDOM, VirtualConsole, ResourceLoader } from 'jsdom';

const BASE = process.env.ERP_BASE || 'http://127.0.0.1:8000';
let failures = 0;
const ok = (cond, name, extra = '') => {
  console.log(`${cond ? '  ✅' : '  ❌'} ${name}${cond ? '' : extra ? ` — ${extra}` : ''}`);
  if (!cond) failures++;
};
const sleep = ms => new Promise(r => setTimeout(r, ms));

/* ------------------------------------------------ cookie jar + fetch */
function makeJar() {
  const jar = new Map();
  return {
    absorb(res) {
      const set = res.headers.getSetCookie?.() ?? [];
      for (const c of set) {
        const [pair] = c.split(';');
        const i = pair.indexOf('=');
        jar.set(pair.slice(0, i).trim(), pair.slice(i + 1).trim());
      }
    },
    header() {
      return [...jar.entries()].map(([k, v]) => `${k}=${v}`).join('; ');
    },
    has(k) { return jar.has(k); },
  };
}

async function rawFetch(jar, path, opts = {}) {
  const url = new URL(path, BASE).href;
  const headers = { ...(opts.headers || {}) };
  if (jar.header()) headers.cookie = jar.header();
  const res = await fetch(url, { ...opts, headers, redirect: 'manual' });
  jar.absorb(res);
  return res;
}

/* Serves the page's subresources through the cookie jar; stubs the Chart
   vendor bundle (jsdom has no <canvas>) and blanks css/img noise.        */
class Loader extends ResourceLoader {
  constructor(jar) { super(); this.jar = jar; }
  fetch(url, _opts) {
    const u = new URL(url);
    if (!u.pathname.endsWith('.js')) return Promise.resolve(Buffer.from(''));
    if (u.pathname.includes('chart.umd'))
      return Promise.resolve(Buffer.from(
        'window.Chart = class { constructor(){} destroy(){} };'));
    return rawFetch(this.jar, u.pathname + u.search)
      .then(r => r.text()).then(t => Buffer.from(t));
  }
}

/* --------------------------------------------------------- page load */
async function loadPage(path, { jar, hash = '' } = {}) {
  jar = jar || makeJar();
  const pageRes = await rawFetch(jar, path);
  const html = await pageRes.text();

  const navAttempts = [];
  const pageErrors = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', e => {
    if (/navigation/i.test(e.message)) navAttempts.push(e.message);
    else if (!/not implemented/i.test(e.message)) pageErrors.push(e.message);
  });

  const calls = [];
  const dom = new JSDOM(html, {
    url: BASE + path + (hash ? '#' + hash : ''),
    runScripts: 'dangerously',
    resources: new Loader(jar),
    pretendToBeVisual: true,
    virtualConsole: vc,
    beforeParse(window) {
      window.scrollTo = () => {};
      window.print = () => {};
      window.fetch = async (p, o = {}) => {
        const rec = { path: String(p), method: (o.method || 'GET').toUpperCase() };
        calls.push(rec);
        const res = await rawFetch(jar, String(p), o);
        rec.status = res.status;
        if (!res.ok) {
          const clone = res.clone();
          rec.body = await clone.text().catch(() => '');
        }
        return res;
      };
      window.addEventListener('error', e =>
        pageErrors.push(e.message || String(e.error || e)));
    },
  });
  const { window } = dom;

  await new Promise(res => {
    if (window.document.readyState === 'complete') return res();
    window.addEventListener('load', res);
    setTimeout(res, 4000);                       // safety net
  });

  return { window, calls, navAttempts, pageErrors, jar,
    authMeCalls: () => calls.filter(c => c.path.includes('/api/auth/me')).length };
}

/* =========================================================== tests */
async function tLoginNoLoop() {
  console.log('▶ /login (signed out) must NOT loop');
  const p = await loadPage('/login');
  await sleep(700);
  ok(p.authMeCalls() === 1, `exactly one /api/auth/me probe (got ${p.authMeCalls()})`);
  ok(p.navAttempts.length === 0, `no navigation attempts (got ${p.navAttempts.length})`);
  ok(!!p.window.document.querySelector('#login-form'), 'login form rendered');
  ok(p.pageErrors.length === 0, 'no script errors', p.pageErrors[0]);
}

async function tLoginSubmit() {
  console.log('▶ /login submit signs in and navigates once');
  const p = await loadPage('/login');
  await sleep(400);
  const d = p.window.document;
  d.querySelector('[name=username]').value = 'sameer';
  d.querySelector('[name=password]').value = 'Palaskar@2014';
  d.querySelector('#login-form').dispatchEvent(
    new p.window.Event('submit', { bubbles: true, cancelable: true }));
  await sleep(900);
  ok(p.calls.some(c => c.path.includes('/api/auth/login') && c.method === 'POST'), 'login POST fired');
  ok(p.jar.has('access_token'), 'auth cookie stored');
  ok(p.navAttempts.length === 1, `navigated exactly once (got ${p.navAttempts.length})`);
  const me = await (await rawFetch(p.jar, '/api/auth/me')).json();
  ok(me.username === 'sameer', 'cookie session valid (me == sameer)');
  return p.jar;
}

async function login(username, password) {
  const jar = makeJar();
  const r = await rawFetch(jar, '/api/auth/login', {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ username, password }) });
  if (r.status !== 200) throw new Error(`login ${username} -> ${r.status}`);
  return jar;
}

async function tShell(path, jar, mustContain, expectFetch, hash = '') {
  console.log(`▶ ${path}${hash ? '#' + hash : ''} renders for signed-in user`);
  const p = await loadPage(path, { jar, hash });
  await sleep(1300);
  const text = p.window.document.body.textContent;
  ok(p.navAttempts.length === 0, `no bounce to /login (got ${p.navAttempts.length})`);
  for (const t of mustContain) ok(text.includes(t), `page shows “${t}”`);
  for (const f of expectFetch) ok(p.calls.some(c => c.path.includes(f)), `fetched ${f}`);
  if (p.window.document.querySelector('table.table tbody tr td')) {
    ok(!!p.window.document.querySelector('td[data-th]'),
       'table cells carry data-th labels (mobile stacking ready)');
  }
  ok(p.pageErrors.length === 0, 'no script errors', p.pageErrors[0]);
  return p;
}

async function tLoginRedirectsWhenAuthed(jar) {
  console.log('▶ /login while signed-in redirects home once');
  const p = await loadPage('/login', { jar });
  await sleep(700);
  ok(p.navAttempts.length === 1, `exactly one redirect (got ${p.navAttempts.length})`);
}

async function tLanding() {
  console.log('▶ / landing: booking widget builds, slots load');
  const p = await loadPage('/');
  await sleep(1200);
  const d = p.window.document;
  ok(!!d.querySelector('#bk-doctor option[value="1"]'), 'doctor list populated');
  ok(p.navAttempts.length === 0, 'no navigation attempts');
  // choose doctor + a date → slot grid should arrive
  const sel = d.querySelector('#bk-doctor');
  sel.value = '1';
  sel.dispatchEvent(new p.window.Event('change', { bubbles: true }));
  const dateBtn = d.querySelector('#book-widget [data-date]');
  dateBtn.dispatchEvent(new p.window.MouseEvent('click', { bubbles: true }));
  await sleep(900);
  ok(p.calls.some(c => c.path.includes('/api/public/slots')), 'slots requested');
  ok(!!d.querySelector('#bk-slots .slot') || d.querySelector('#bk-slots .empty'),
     'slot grid (or closed/empty notice) rendered');
  ok(p.pageErrors.length === 0, 'no script errors', p.pageErrors[0]);
}

async function tStaffCannotLoopOnExpiredCookie() {
  console.log('▶ /staff with NO cookie bounces to /login exactly once');
  const p = await loadPage('/staff');
  await sleep(700);
  ok(p.navAttempts.length === 1, `one redirect to login (got ${p.navAttempts.length})`);
}


async function tConfirmFiresOnce(jar) {
  console.log('▶ appointments: Confirm fires EXACTLY one PATCH after tab hopping (regression)');
  const p = await loadPage('/admin', { jar, hash: 'appointments' });
  await sleep(1200);
  const w = p.window, d = w.document;
  // hop away and back — this used to stack click handlers
  w.location.hash = 'patients';  await sleep(900);
  w.location.hash = 'rooms';     await sleep(900);
  w.location.hash = 'appointments'; await sleep(1100);
  // find the first upcoming day with an actionable row via the API,
  // then drive the UI to it — works on Sundays and after hours too
  let targetDay = null;
  for (let i = 0; i <= 3 && !targetDay; i++) {
    const dISO = new Date(Date.now() + i * 864e5).toISOString().slice(0, 10);
    const rows = await (await rawFetch(jar, `/api/appointments?day=${dISO}`)).json();
    if (rows.some(r => ['BOOKED', 'CONFIRMED'].includes(r.status))) targetDay = dISO;
  }
  ok(!!targetDay, 'an upcoming day with actionable appointments exists');
  const dayInp = d.querySelector('#ap-day');
  dayInp.value = targetDay;
  dayInp.dispatchEvent(new w.Event('change', { bubbles: true }));
  await sleep(1100);
  let btn = d.querySelector('[data-ap][data-st="CONFIRMED"]');
  let expect = /confirmed/i;
  if (!btn) {
    btn = d.querySelector('[data-ap][data-st="CANCELLED"]');
    expect = /cancelled/i;
  }
  ok(!!btn, 'an actionable appointment row is listed');
  const before = p.calls.filter(c => c.method === 'PATCH').length;
  if (btn) {
    btn.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    await sleep(900);
    const patches = p.calls.filter(c => c.method === 'PATCH').length - before;
    ok(patches === 1, `exactly one PATCH fired (got ${patches})`);
    const toasts = [...d.querySelectorAll('.toast')].map(t => t.textContent);
    ok(toasts.filter(t => expect.test(t)).length === 1
       && !toasts.some(t => /cannot|failed|error/i.test(t)),
       'single success toast, no error toast', toasts.join(' | '));
  }
  ok(p.pageErrors.length === 0, 'no script errors', p.pageErrors[0]);
}

async function tDashboardFull(jar) {
  console.log('▶ /admin dashboard: admitted-now KPI + Recent activity feed');
  const p = await loadPage('/admin', { jar });
  await sleep(1800);
  const text = p.window.document.body.textContent;
  ok(text.includes('Patients admitted now'), 'admitted-now KPI shown');
  ok(text.includes('Recent activity'), 'Recent activity card shown');
  ok(p.calls.some(c => c.path.includes('/api/dashboard/activity')), 'activity feed fetched');
  ok(p.window.document.querySelectorAll('.feed li').length >= 5, 'feed has entries');
  ok(p.pageErrors.length === 0, 'no script errors', p.pageErrors[0]);
}

async function tGuestBookingSubmit() {
  console.log('▶ landing: full guest booking submit');
  const p = await loadPage('/');
  await sleep(1100);
  const w = p.window, d = w.document;
  d.querySelector('#bk-doctor').value = '1';
  d.querySelector('#bk-doctor').dispatchEvent(new w.Event('change', { bubbles: true }));
  let slot = null;
  for (const db of d.querySelectorAll('#book-widget [data-date]')) {
    db.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    await sleep(900);
    slot = d.querySelector('#bk-slots .slot:not(.off)');
    if (slot) break;
  }
  if (!slot) {
    ok(!!d.querySelector('#bk-slots .empty'),
       'no bookable slot right now (Sunday/after hours) — closed notice shown instead');
    return;
  }
  slot.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  await sleep(200);
  d.querySelector('#bk-name').value = 'Smoke Tester';
  d.querySelector('#bk-phone').value = '9876500001';
  d.querySelector('#bk-submit').dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  await sleep(1100);
  const posts = p.calls.filter(c =>
    c.method === 'POST' && c.path.includes('/api/public/appointments'));
  ok(posts.length === 1, `exactly one booking POST (got ${posts.length})`);
  ok(posts[0]?.status === 201,
     `booking POST returned 201 (got ${posts[0]?.status})`, posts[0]?.body);
  ok(d.querySelector('#bk-done')?.textContent.includes('APT-'),
     'success card shows an APT- booking code');
  ok(d.querySelector('#bk-done')?.textContent.includes('30 minutes early'),
     'arrive-30-minutes note shown');
  ok(p.pageErrors.length === 0, 'no script errors', p.pageErrors[0]);
}

async function tPayNetbanking(adminJar) {
  console.log('▶ portal: pay a bill via the demo NETBANKING sheet');
  // make sure ramesh has a fresh PENDING bill
  await rawFetch(adminJar, '/api/consultations', {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ patient_id: 1, department: 'ORTHOPAEDICS',
      chief_complaint: 'smoke pay test', fee: 111 }) });
  const jar = await login('ramesh', 'Patient@1234');
  const p = await loadPage('/portal', { jar, hash: 'bills' });
  await sleep(1400);
  const w = p.window, d = w.document;
  const payBtn = d.querySelector('[data-pay-bill]');
  ok(!!payBtn, 'a Pay now button is listed');
  payBtn.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  await sleep(300);
  ok(d.body.classList.contains('modal-open'), 'body scroll locked while modal open');
  ok(!!d.querySelector('.fakeqr'), 'UPI tab shows the QR block');
  const nb = [...d.querySelectorAll('.paytab')].find(t => t.dataset.pm === 'NETBANKING');
  nb.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  await sleep(200);
  ok(!!d.querySelector('#pay-bank'), 'netbanking bank selector rendered');
  d.querySelector('#pay-go').dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  await sleep(2200);                                     // demo gateway delay
  const pays = p.calls.filter(c => c.method === 'POST' && c.path.includes('/pay'));
  ok(pays.length === 1, `exactly one pay POST (got ${pays.length})`);
  const toasts = [...d.querySelectorAll('.toast')].map(t => t.textContent).join(' | ');
  ok(/Payment received — TXN-/.test(toasts), 'success toast with TXN reference', toasts);
  // the paid bill reopens in a modal — lock stays, receipt shows PAID
  ok(d.body.classList.contains('modal-open'), 'receipt modal keeps body locked');
  ok(/PAID/.test(d.querySelector('#modal-bd')?.textContent || ''),
     'receipt shows the bill as PAID');
  ok(!!d.querySelector('.mb2 td[data-th="Item"]',),
     'bill modal table labelled for phones');
  d.querySelector('[data-action="close-modal"]').dispatchEvent(
    new w.MouseEvent('click', { bubbles: true }));
  await sleep(150);
  ok(!d.body.classList.contains('modal-open'),
     'body scroll unlocked after closing the receipt');
  ok(p.pageErrors.length === 0, 'no script errors', p.pageErrors[0]);
}

async function tDrawerToggle(jar) {
  console.log('▶ mobile drawer: burger opens with scrim, outside tap closes');
  const p = await loadPage('/admin', { jar, hash: 'patients' });
  await sleep(1100);
  const w = p.window, d = w.document;
  d.querySelector('[data-action="burger"]').dispatchEvent(
    new w.MouseEvent('click', { bubbles: true }));
  ok(d.querySelector('#sidebar').classList.contains('open'), 'drawer opens');
  ok(d.body.classList.contains('nav-open'), 'scrim class applied to body');
  d.querySelector('#view').dispatchEvent(
    new w.MouseEvent('click', { bubbles: true }));
  ok(!d.querySelector('#sidebar').classList.contains('open'), 'outside tap closes drawer');
  ok(!d.body.classList.contains('nav-open'), 'scrim class removed');
  ok(p.pageErrors.length === 0, 'no script errors', p.pageErrors[0]);
}

async function tAttendanceCalendar(jar) {
  console.log('▶ attendance renders as a month CALENDAR (not a heatmap)');
  const p = await loadPage('/admin', { jar, hash: 'attendance' });
  await sleep(1400);
  const d = p.window.document;
  ok(!!d.querySelector('.attcal'), 'calendar grid rendered');
  ok(d.querySelectorAll('.ac-dow').length === 7, 'weekday headers Sun–Sat');
  ok(!!d.querySelector('.ac-today'), "today's cell highlighted");
  ok(!!d.querySelector('#ac-prev'), 'month navigation present');
  ok(!d.querySelector('.heatmap'), 'old heatmap is gone');
  // flip back one month and assert the header changed
  const before = d.querySelector('.ac-head b').textContent;
  d.querySelector('#ac-prev').dispatchEvent(
    new p.window.MouseEvent('click', { bubbles: true }));
  await sleep(200);
  ok(d.querySelector('.ac-head b').textContent !== before, 'prev-month navigation works');
  ok(p.pageErrors.length === 0, 'no script errors', p.pageErrors[0]);
}

(async () => {
  const health = await fetch(BASE + '/api/health').catch(() => null);
  if (!health || health.status !== 200) {
    console.error(`Server not reachable at ${BASE} — start it with: python run.py`);
    process.exit(2);
  }
  await tLoginNoLoop();
  const adminJar = await tLoginSubmit();
  await tLoginRedirectsWhenAuthed(adminJar);
  await tStaffCannotLoopOnExpiredCookie();
  await tLanding();

  await tShell('/admin', adminJar,
    ['Patients', 'Register patient'], ['/api/patients'], 'patients');
  await tShell('/admin', adminJar,
    ['Pharmacy', 'Inventory'], ['/api/pharmacy/medicines'], 'pharmacy');
  await tShell('/admin', adminJar,
    ['Admissions', 'Admit patient'], ['/api/admissions'], 'admissions');

  const staffJar = await login('anita', 'Staff@1234');
  await tShell('/staff', staffJar,
    ['Today at the hospital', 'Check in'], ['/api/dashboard/staff-home']);

  const patJar = await login('ramesh', 'Patient@1234');
  await tShell('/portal', patJar,
    ['Your health, in one place', 'Book an appointment'],
    ['/api/appointments', '/api/bills']);
  await tShell('/portal', patJar,
    ['Bills & payments'], ['/api/bills'], 'bills');

  await tConfirmFiresOnce(adminJar);
  await tDashboardFull(adminJar);
  await tGuestBookingSubmit();
  await tPayNetbanking(adminJar);
  await tAttendanceCalendar(adminJar);
  await tDrawerToggle(adminJar);

  console.log(failures ? `\n${failures} FAILURE(S)` : '\nALL UI SMOKE TESTS PASSED');
  process.exit(failures ? 1 : 0);
})();
