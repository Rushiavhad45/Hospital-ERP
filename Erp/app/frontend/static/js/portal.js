/* Patient portal — sees only their own records. */
'use strict';

(async () => {
  const me = await requireUser(['PATIENT']);
  if (!me) return;
  const PID = me.patient_id;

  buildShell({
    me, appName: 'Patient portal',
    navItems: [
      { id: 'home', icon: '🏠', label: 'Home' },
      { id: 'appointments', icon: '📅', label: 'Appointments' },
      { id: 'visits', icon: '🩺', label: 'My visits' },
      { id: 'bills', icon: '🧾', label: 'Bills & payments' },
      { id: 'documents', icon: '🩻', label: 'Scans & reports' },
      { id: 'physio', icon: '🤸', label: 'Physiotherapy' },
      { id: 'claims', icon: '🛡', label: 'Mediclaims' },
    ],
  });

  const render = makeRouter({
    home, appointments, visits, bills, documents, physio, claims,
  }, 'home');
  render();

  /* ---------------------------------------------------------- home */
  async function home(box) {
    const [appts, myBills, consults] = await Promise.all([
      api('/api/appointments?span_days=2'), api('/api/bills'),
      api(`/api/consultations?patient_id=${PID}`)]);
    const next = appts.filter(a => ['BOOKED', 'CONFIRMED'].includes(a.status))[0];
    const pending = myBills.filter(b => b.status === 'PENDING');
    const due = pending.reduce((s, b) => s + b.total, 0);
    box.innerHTML = `
      <h1 class="mb">Your health, in one place</h1>
      <div class="grid g3 mb">
        <div class="card kpi b"><div class="v">${next ? fmtSlot(next.slot) : '—'}</div>
          <div class="l">${next ? `Next visit · ${fmtDate(next.appointment_date)}` : 'No upcoming visit'}</div>
          ${next ? `<div class="tiny muted">${esc(next.doctor_name)}</div>` : ''}</div>
        <div class="card kpi o"><div class="v">${rupee(due)}</div><div class="l">Bills pending</div>
          <div class="tiny muted">${pending.length} unpaid bill${pending.length === 1 ? '' : 's'}</div></div>
        <div class="card kpi"><div class="v">${consults.length}</div><div class="l">Total visits</div></div>
      </div>
      <div class="grid g2" style="align-items:start">
        <div class="card"><h3>Quick actions</h3>
          <div class="flex wrap mt">
            <button class="btn" data-view="appointments">📅 Book an appointment</button>
            ${pending.length ? `<button class="btn orange" data-view="bills">Pay ${rupee(due)}</button>` : ''}
            <button class="btn ghost" data-view="documents">View my scans</button>
          </div>
          <div class="divider"></div>
          <p class="small muted">OPD runs Mon–Sat. Please arrive <b>30 minutes early</b> —
            our front desk confirms appointments on the day of the visit.
            Appointments: <b>9545081608 / 8087381866</b>.</p></div>
        <div class="card"><h3>Recent visits</h3>
          ${consults.slice(0, 4).map(c => `<div class="small" style="margin:8px 0">
            <b>${fmtDate(c.visited_at)}</b> · ${esc(c.doctor_name)}
            <div class="muted">${esc(c.diagnosis || c.chief_complaint)}</div></div>`).join('')
            || '<div class="empty">No visits yet.</div>'}
          <button class="btn ghost sm" data-view="visits">All visits →</button></div>
      </div>`;
  }

  /* -------------------------------------------------- appointments */
  async function appointments(box) {
    const appts = await api('/api/appointments?span_days=7');
    box.innerHTML = `
      <div class="flex between wrap mb"><h1>Appointments</h1>
        <button class="btn" id="ap-book">＋ Book new</button></div>
      ${appts.length ? appts.map(a => `
        <div class="card mb"><div class="flex between wrap">
          <div><b>${fmtDate(a.appointment_date)} · ${fmtSlot(a.slot)}</b> ${badge(a.status)}
            <div class="small muted">${esc(a.doctor_name)} · ${esc(a.department)}</div>
            <div class="tiny muted mono">Code ${esc(a.code)}</div></div>
          ${['BOOKED', 'CONFIRMED'].includes(a.status) ?
            `<button class="btn danger sm" data-cancel="${a.id}">Cancel</button>` : ''}
        </div></div>`).join('')
        : '<div class="card empty"><div class="big">📅</div>No appointments — book your first visit!</div>'}`;
    on(box, async e => {
      if (e.target.id === 'ap-book') return bookModal();
      const c = e.target.closest('[data-cancel]');
      if (c) {
        try {
          await api(`/api/appointments/${c.dataset.cancel}/status`,
            { method: 'PATCH', body: { status: 'CANCELLED' } });
          toast('Appointment cancelled'); appointments(box);
        } catch (err) { toast(err.message, 'err'); }
      }
    });
  }

  async function bookModal() {
    const doctors = await api('/api/public/doctors');
    const d0 = new Date(), d1 = new Date(); d1.setDate(d1.getDate() + 1);
    const iso = d => d.toISOString().slice(0, 10);
    let sel = { doctor: null, date: null, slot: null };
    modal('Book an appointment', `
      <div class="field"><label>Doctor</label><select class="select" id="bk-doc">
        <option value="">Choose…</option>
        ${doctors.map(d => `<option value="${d.id}">${esc(d.full_name)} — ${esc(d.department)}</option>`).join('')}</select></div>
      <div class="field"><label>Date (today or tomorrow only)</label><div class="flex">
        <button class="btn ghost sm" data-d="${iso(d0)}">Today</button>
        <button class="btn ghost sm" data-d="${iso(d1)}">Tomorrow</button></div></div>
      <div id="bk-slots2"></div>
      <div class="field"><label>Reason (optional)</label><input class="input" id="bk-reason2" maxlength="200"></div>
      <p class="tiny muted">Please arrive 30 minutes early — staff confirm bookings at the desk.</p>`,
      `<button class="btn ghost" data-action="close-modal">Cancel</button>
       <button class="btn orange" id="bk-go" disabled>Book slot</button>`);
    const loadSlots = async () => {
      sel.slot = null; $('#bk-go').disabled = true;
      if (!sel.doctor || !sel.date) return;
      $('#bk-slots2').innerHTML = '<div class="loader"></div>';
      try {
        const data = await api(`/api/public/slots?doctor_id=${sel.doctor}&on=${sel.date}`);
        $('#bk-slots2').innerHTML = data.closed
          ? '<div class="empty">Closed on Sundays.</div>'
          : `<div class="slotgrid">${data.slots.map(s =>
              `<div class="slot ${s.available ? '' : 'off'}" data-s="${s.available ? esc(s.slot) : ''}">${fmtSlot(s.slot)}</div>`).join('')}</div>`;
      } catch (err) { $('#bk-slots2').innerHTML = `<div class="empty">${esc(err.message)}</div>`; }
    };
    $('#bk-doc').addEventListener('change', e => { sel.doctor = +e.target.value || null; loadSlots(); });
    on($('#modal-bd'), e => {
      const d = e.target.closest('[data-d]');
      if (d) { sel.date = d.dataset.d;
        $$('#modal-bd [data-d]').forEach(x => x.classList.remove('orange'));
        d.classList.add('orange'); loadSlots(); }
      const s = e.target.closest('.slot:not(.off)');
      if (s) { sel.slot = s.dataset.s;
        $$('#modal-bd .slot').forEach(x => x.classList.toggle('sel', x === s));
        $('#bk-go').disabled = false; }
    });
    $('#bk-go').addEventListener('click', async () => {
      try {
        const a = await api('/api/appointments', { method: 'POST', body: {
          doctor_id: sel.doctor, appointment_date: sel.date, slot: sel.slot,
          reason: $('#bk-reason2').value.trim() } });
        SFX.success(); toast(`Booked! Code ${a.code} — arrive 30 min early.`);
        closeModal(); location.hash = 'appointments'; appointments($('#view'));
      } catch (err) { toast(err.message, 'err'); }
    });
  }

  /* -------------------------------------------------------- visits */
  async function visits(box) {
    const list = await api(`/api/consultations?patient_id=${PID}`);
    box.innerHTML = `<h1 class="mb">My visits</h1>
      ${V.table(['Date', 'Doctor', 'Diagnosis', 'Fee', ''],
        list.map(c => `<tr><td class="nowrap">${fmtDT(c.visited_at)}</td>
          <td>${esc(c.doctor_name)}<div class="tiny muted">${esc(c.department)}</div></td>
          <td>${esc(c.diagnosis || c.chief_complaint)}
            ${c.prescription ? '<span class="chip">💊 Rx</span>' : ''}</td>
          <td class="mono">${rupee(c.fee)}</td>
          <td class="right"><button class="btn ghost sm" data-c="${c.id}">Details</button></td></tr>`),
        'No visits yet — book an appointment to get started.')}`;
    on(box, e => {
      const b = e.target.closest('[data-c]');
      if (b) V.consultModal(+b.dataset.c);
    });
  }

  /* --------------------------------------------------------- bills */
  async function bills(box) {
    const list = await api('/api/bills');
    box.innerHTML = `<h1 class="mb">Bills & payments</h1>
      ${list.length ? list.map(b => `
        <div class="card mb"><div class="flex between wrap">
          <div><b class="mono">${esc(b.bill_number)}</b> <span class="chip">${esc(b.bill_type)}</span> ${badge(b.status)}
            <div class="small muted">${fmtDate(b.generated_at)} · ${b.items.length} item${b.items.length === 1 ? '' : 's'}</div></div>
          <div class="flex"><b class="mono" style="font-size:19px">${rupee(b.total)}</b>
            <button class="btn ghost sm" data-view-bill="${b.id}">View</button>
            ${b.status === 'PENDING' ? `<button class="btn orange sm" data-pay-bill="${b.id}">Pay now</button>` : ''}
          </div></div></div>`).join('')
        : '<div class="card empty"><div class="big">🧾</div>No bills — all clear!</div>'}`;
    on(box, async e => {
      const v = e.target.closest('[data-view-bill]');
      if (v) return V.billModal(+v.dataset.viewBill, () => bills(box));
      const p = e.target.closest('[data-pay-bill]');
      if (p) {
        const b = list.find(x => x.id === +p.dataset.payBill);
        V.payModal(b, () => bills(box));
      }
    });
  }

  /* ----------------------------------------------------- documents */
  async function documents(box) {
    const list = await api(`/api/patients/${PID}/documents`);
    box.innerHTML = `<h1 class="mb">Scans & reports</h1>
      ${list.length ? `<div class="grid g3">${list.map(d => `
        <div class="card"><div class="flex between">${badge(d.doc_type)}
            <span class="tiny muted">${fmtDate(d.taken_on)}</span></div>
          <h4 class="mt">${esc(d.title)}</h4>
          ${d.notes ? `<div class="tiny muted">${esc(d.notes)}</div>` : ''}
          <a class="btn ghost sm mt" target="_blank" href="/api/documents/${d.id}/download">Open ↗</a>
        </div>`).join('')}</div>`
        : '<div class="card empty"><div class="big">🩻</div>No scans or reports uploaded yet.</div>'}`;
  }

  /* -------------------------------------------------------- physio */
  async function physio(box) {
    const plans = await api(`/api/physio/plans?patient_id=${PID}`);
    box.innerHTML = `<h1 class="mb">Physiotherapy</h1>
      ${plans.length ? plans.map(p => `
        <div class="card mb"><div class="flex between wrap">
          <div><b>${p.days_count}-day plan</b> ${p.is_active ? badge('ACTIVE') : badge('DONE')}
            <span class="muted small">· prescribed by ${esc(p.prescribed_by_name)} on ${fmtDate(p.prescribed_on)}</span></div>
          <b>${p.sessions_done}/${p.days_count} sessions</b></div>
        <div class="mt">${p.exercises.map(x => `<span class="chip">🏋️ ${esc(x)}</span>`).join('')}
          ${p.modalities.map(x => `<span class="chip">⚡ ${esc(x)}</span>`).join('')}
          ${p.traction.map(x => `<span class="chip">🪢 ${esc(x)}</span>`).join('')}</div>
        ${p.notes ? `<div class="small muted mt">${esc(p.notes)}</div>` : ''}
        <div class="divider"></div>
        <div class="small">${p.sessions.map(s =>
          `<div>✅ ${fmtDate(s.session_date)} · ${esc(s.timing)} · ${rupee(s.amount)} · ${esc(s.performed_by_name || '')}</div>`).join('')
          || '<span class="muted">No sessions recorded yet.</span>'}</div></div>`).join('')
        : '<div class="card empty"><div class="big">🤸</div>No physiotherapy plans yet.</div>'}
      <p class="tiny muted">Physio centre hours: 11 AM–1 PM & 5–9 PM (Mon–Sat).</p>`;
  }

  /* -------------------------------------------------------- claims */
  async function claims(box) {
    const list = await api('/api/mediclaims');
    box.innerHTML = `<h1 class="mb">Mediclaims</h1>
      <p class="muted small mb">Claims open automatically when you're admitted and are finalized
        with your full stay summary at discharge — share the claim number with your insurer.</p>
      ${list.length ? list.map(c => `
        <div class="card mb"><div class="flex between wrap">
          <div><b class="mono">${esc(c.claim_number)}</b> ${badge(c.status)}
            <div class="small muted">${esc(c.insurer_name || 'Insurer not set')} ${c.policy_number ? `· ${esc(c.policy_number)}` : ''}</div>
            ${c.finalized_at ? `<div class="tiny muted">Finalized ${fmtDT(c.finalized_at)}</div>` : ''}</div>
          ${(c.summary || {}).admission ?
            `<button class="btn ghost sm" data-claim="${c.id}">Stay summary</button>` : ''}
        </div></div>`).join('')
        : '<div class="card empty"><div class="big">🛡</div>No claims — you have never been admitted.</div>'}`;
    on(box, e => {
      const b = e.target.closest('[data-claim]');
      if (!b) return;
      const c = list.find(x => x.id === +b.dataset.claim);
      const s = c.summary;
      const A = s.admission || {}, B = s.bill || {};
      modal(`Claim ${c.claim_number}`, `
        <div class="small">
          <div><b>Admitted:</b> ${fmtDT(A.admitted_at)} → <b>Discharged:</b> ${fmtDT(A.discharged_at)}</div>
          <div><b>Stay:</b> ${A.hours} h · Room ${esc(A.room || '')}</div>
          <div><b>Doctor:</b> ${esc(A.primary_doctor || '')} · <b>Diagnosis:</b> ${esc(A.diagnosis || '—')}</div>
          <table class="table mt"><tbody>
            ${(B.items || []).map(i => `<tr><td>${esc(i.description)}</td>
              <td class="mono right">${rupee(i.amount)}</td></tr>`).join('')}
            ${B.discount ? `<tr><td>Discount</td><td class="mono right">− ${rupee(B.discount)}</td></tr>` : ''}
            <tr><td><b>Total billed (${esc(B.number || '')})</b></td><td class="mono right"><b>${rupee(B.total || 0)}</b></td></tr>
          </tbody></table></div>`,
        `<button class="btn ghost" data-action="print">🖨 Print</button>
         <button class="btn" data-action="close-modal">Close</button>`);
    });
  }
})();
