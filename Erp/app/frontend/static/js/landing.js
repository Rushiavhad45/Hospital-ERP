/* Landing page behaviour: splash, reveals, treatment details, guest booking. */
'use strict';

let INFO = null;

/* splash */
window.addEventListener('load', () => {
  setTimeout(() => $('#splash')?.classList.add('done'), 900);
  setTimeout(() => $('#splash')?.remove(), 1600);
});

/* reveal on scroll (progressive enhancement — never fatal) */
const io = ('IntersectionObserver' in window)
  ? new IntersectionObserver(entries => {
      entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
    }, { threshold: .12 })
  : null;
$$('.reveal').forEach(el => io ? io.observe(el) : el.classList.add('in'));

/* treatment cards → detail modal */
document.addEventListener('click', async e => {
  const card = e.target.closest('.tcard[data-slug]');
  if (!card) return;
  try {
    INFO = INFO || await api('/api/public/info');
    const t = INFO.treatments.find(x => x.slug === card.dataset.slug);
    if (!t) return;
    modal(t.name, `
      <p class="muted small">${esc(t.blurb)}</p>
      <div class="divider"></div>
      ${t.items.map(i => `<div style="margin-bottom:10px">
          <b>• ${esc(i.name)}</b><div class="small muted" style="margin-left:12px">${esc(i.desc)}</div>
        </div>`).join('')}`,
      `<a class="btn orange" href="#book" data-action="close-modal">Book a consultation</a>`);
  } catch (err) { toast(err.message, 'err'); }
});

/* ------------------------------------------------------- booking widget */
const bookState = { doctor: null, date: null, slot: null };

async function initBooking() {
  const box = $('#book-widget');
  if (!box) return;
  let doctors;
  try { doctors = await api('/api/public/doctors'); }
  catch (err) { box.innerHTML = `<div class="empty">${esc(err.message)}</div>`; return; }

  const d0 = new Date(), d1 = new Date(); d1.setDate(d1.getDate() + 1);
  const iso = d => d.toISOString().slice(0, 10);
  const label = d => d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' });

  box.innerHTML = `
    <div class="field"><label>Doctor</label>
      <select class="select" id="bk-doctor">
        <option value="">Select a doctor…</option>
        ${doctors.map(d => `<option value="${d.id}">${esc(d.full_name)} — ${esc(d.department)}</option>`).join('')}
      </select></div>
    <div class="field"><label>Date</label>
      <div class="flex wrap">
        <button class="btn ghost sm" data-date="${iso(d0)}">Today · ${label(d0)}</button>
        <button class="btn ghost sm" data-date="${iso(d1)}">Tomorrow · ${label(d1)}</button>
      </div></div>
    <div id="bk-slots"></div>
    <div id="bk-form" class="hide">
      <div class="divider"></div>
      <div class="formgrid">
        <div class="field"><label>Full name</label><input class="input" id="bk-name" maxlength="80"></div>
        <div class="field"><label>Phone (10 digits)</label><input class="input" id="bk-phone" maxlength="10"></div>
      </div>
      <div class="field"><label>Reason (optional)</label><input class="input" id="bk-reason" maxlength="200"></div>
      <button class="btn orange" id="bk-submit">Confirm booking</button>
    </div>
    <div id="bk-done"></div>`;

  $('#bk-doctor').addEventListener('change', () => { bookState.doctor = +$('#bk-doctor').value || null; loadSlots(); });
  box.addEventListener('click', e => {
    const db = e.target.closest('[data-date]');
    if (db) {
      bookState.date = db.dataset.date;
      $$('#book-widget [data-date]').forEach(b => b.classList.remove('orange'));
      db.classList.add('orange');
      loadSlots();
    }
    const slot = e.target.closest('.slot:not(.off)');
    if (slot) {
      bookState.slot = slot.dataset.slot;
      $$('#bk-slots .slot').forEach(s => s.classList.toggle('sel', s === slot));
      $('#bk-form').classList.remove('hide');
      $('#bk-name').focus();
    }
  });
  $('#bk-submit').addEventListener('click', submitBooking);
}

async function loadSlots() {
  const out = $('#bk-slots');
  $('#bk-form').classList.add('hide');
  bookState.slot = null;
  if (!bookState.doctor || !bookState.date) { out.innerHTML = ''; return; }
  out.innerHTML = '<div class="loader"></div>';
  try {
    const data = await api(`/api/public/slots?doctor_id=${bookState.doctor}&on=${bookState.date}`);
    if (data.closed) {
      out.innerHTML = `<div class="empty">🌿 Closed on Sundays — please pick another date.</div>`;
      return;
    }
    if (!data.slots.length) {
      out.innerHTML = '<div class="empty">All slots are taken for this day.</div>'; return;
    }
    out.innerHTML = `<div class="field"><label>Available 30-minute slots</label>
      <div class="slotgrid">${data.slots.map(s =>
        `<div class="slot ${s.available ? '' : 'off'}" data-slot="${s.available ? esc(s.slot) : ''}">${fmtSlot(s.slot)}</div>`).join('')}
      </div></div>`;
  } catch (err) { out.innerHTML = `<div class="empty">${esc(err.message)}</div>`; }
}

async function submitBooking() {
  const name = $('#bk-name').value.trim();
  const phone = $('#bk-phone').value.trim();
  if (name.length < 3) return toast('Please enter your full name.', 'warn');
  if (!/^[0-9]{10}$/.test(phone)) return toast('Phone must be 10 digits.', 'warn');
  const btn = $('#bk-submit'); btn.disabled = true;
  try {
    const appt = await api('/api/public/appointments', { method: 'POST', body: {
      doctor_id: bookState.doctor, appointment_date: bookState.date,
      slot: bookState.slot, name, phone,
      reason: $('#bk-reason').value.trim() } });
    SFX.success();
    $('#bk-done').innerHTML = `
      <div class="card" style="background:var(--green-soft);border-color:var(--green);margin-top:14px">
        <h3>✅ Appointment booked!</h3>
        <p>Your booking code is <b style="font-size:18px">${esc(appt.code)}</b> — save it to track or modify your visit.</p>
        <p class="small">${esc(appt.doctor_name)} · ${fmtDate(appt.appointment_date)} at <b>${fmtSlot(appt.slot)}</b></p>
        <p class="small muted">⏰ Please arrive <b>30 minutes early</b>. Our staff will confirm your appointment at the front desk.
          Bring any previous reports.</p>
      </div>`;
    $('#bk-form').classList.add('hide');
    $('#bk-done').scrollIntoView({ behavior: 'smooth', block: 'center' });
  } catch (err) {
    toast(err.message, 'err');
    if (err.status === 409) loadSlots();      // slot got taken — refresh
  } finally { btn.disabled = false; }
}

/* ------------------------------------------------------------- tracker */
$('#track-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  const f = new FormData(e.target);
  const out = $('#track-result');
  out.innerHTML = '<div class="loader"></div>';
  try {
    const a = await api(`/api/public/appointments/track?code=${encodeURIComponent(f.get('code').trim())}&phone=${encodeURIComponent(f.get('phone').trim())}`);
    out.innerHTML = `<div class="card" style="background:#FAFBF9">
      <div class="flex between"><b>${esc(a.code)}</b>${badge(a.status)}</div>
      <p class="small" style="margin-top:8px">${esc(a.doctor_name)} · ${esc(a.department)}<br>
      ${fmtDate(a.appointment_date)} at <b>${fmtSlot(a.slot)}</b></p>
      <p class="tiny muted">Arrive 30 minutes early for confirmation at the front desk.</p></div>`;
  } catch (err) { out.innerHTML = `<div class="empty">${esc(err.message)}</div>`; }
});

initBooking();
