/* Admin console — Dr. Sameer / Dr. Lalan. All staff views + management. */
'use strict';

(async () => {
  const me = await requireUser(['SUPER_ADMIN']);
  if (!me) return;
  V.me = me; V.isAdmin = true;
  let CHARTS = [];

  buildShell({
    me, appName: 'Admin console',
    navItems: [
      { id: 'dashboard', icon: '📊', label: 'Dashboard' },
      { id: 'consult', icon: '🩺', label: 'New consultation' },
      { id: 'appointments', icon: '📅', label: 'Appointments' },
      { id: 'patients', icon: '🧑‍🤝‍🧑', label: 'Patients' },
      { id: 'admissions', icon: '🛏', label: 'Admissions' },
      { id: 'rooms', icon: '🚪', label: 'Rooms' },
      { id: 'pharmacy', icon: '💊', label: 'Pharmacy' },
      { id: 'physio', icon: '🤸', label: 'Physiotherapy' },
      { id: 'ot', icon: '🔪', label: 'Operation theatre' },
      { id: 'bills', icon: '🧾', label: 'Billing' },
      { id: 'mediclaims', icon: '🛡', label: 'Mediclaims' },
      { id: 'staffm', icon: '🧑‍⚕️', label: 'Staff & HR' },
      { id: 'payroll', icon: '💰', label: 'Payroll' },
      { id: 'reminders', icon: '🔔', label: 'Reminders' },
      { id: 'attendance', icon: '🗓', label: 'My attendance' },
    ],
  });

  const views = {
    dashboard, consult, mediclaims, staffm: staffMgmt, payroll,
    appointments: V.appointments, patients: V.patients, admissions: V.admissions,
    rooms: V.rooms, pharmacy: V.pharmacy, physio: V.physio, ot: V.ot,
    bills: V.bills, reminders: V.reminders, attendance: V.myAttendance,
  };
  const render = makeRouter(new Proxy(views, {
    get(t, k) {
      if (typeof k === 'string') {
        if (k.startsWith('patient-')) return box => V.patientDetail(box, +k.slice(8));
        if (k.startsWith('admission-')) return box => V.admissionDetail(box, +k.slice(10));
        if (k.startsWith('staff-')) return box => staffDetail(box, +k.slice(6));
      }
      return t[k];
    },
    has: () => true,
  }), 'dashboard');
  render();

  /* ================================================== DASHBOARD ====== */
  async function dashboard(box, day = null) {
    CHARTS.forEach(c => c.destroy()); CHARTS = [];
    const [rep, ch, feed] = await Promise.all([
      api(`/api/dashboard/daily-report${day ? `?day=${day}` : ''}`),
      api('/api/dashboard/charts?days=30'),
      api('/api/dashboard/activity?limit=30')]);
    const dep = rep.consultations.by_department;
    box.innerHTML = `
      <div class="flex between wrap mb"><h1>Daily report</h1>
        <div class="flex"><input class="input" type="date" id="db-day" value="${rep.date}" style="max-width:170px">
        <button class="btn ghost" data-action="print">🖨 Print report</button></div></div>
      <div class="grid g4 mb">
        <div class="card kpi"><div class="v">${rep.consultations.count}</div><div class="l">Consultations</div>
          <div class="tiny muted">${Object.entries(dep).map(([k, v]) => `${k.slice(0, 5)}: ${v}`).join(' · ') || '—'}</div></div>
        <div class="card kpi o"><div class="v">${rupee(rep.revenue.collected_today)}</div><div class="l">Collected today</div>
          <div class="tiny muted">${rupee(rep.revenue.pending_overall)} pending overall</div></div>
        <div class="card kpi b"><div class="v">${rep.patients.currently_admitted}</div><div class="l">Patients admitted now</div>
          <div class="tiny muted">+${rep.patients.admitted_today} admitted · ${rep.patients.discharged_today} discharged today</div></div>
        <div class="card kpi r"><div class="v">${rep.staff_attendance.present}/${rep.staff_attendance.total}</div>
          <div class="l">Staff present</div>
          <div class="tiny muted">${rep.patients.new_registrations} new patients registered</div></div>
      </div>
      <div class="grid g2 mb" style="align-items:start">
        <div class="card feedcard"><div class="flex between"><h3>🕐 Recent activity</h3>
            <span class="tiny muted">live across the hospital</span></div>
          <ul class="timeline feed">${feed.map(e => `
            <li class="${e.kind === 'ADMISSION' ? 'orange' : e.kind === 'PAYMENT' ? '' :
                        e.kind === 'DISCHARGE' ? 'blue' : e.kind === 'SURGERY' ? 'red' : 'gray'}">
              <div class="small">${e.icon} ${esc(e.text)}</div>
              <div class="tiny muted">${fmtDT(e.at)}</div></li>`).join('')
            || '<div class="empty">No activity yet today.</div>'}</ul>
        </div>
        <div>
          <div class="card mb"><h3>💹 Revenue — last 30 days</h3><div class="canvasbox"><canvas id="ch-rev"></canvas></div></div>
          <div class="card"><h3>🩺 Consultations — last 30 days</h3><div class="canvasbox"><canvas id="ch-con"></canvas></div></div>
        </div>
      </div>
      <div class="grid g3 mb">
        <div class="card"><h3>🏥 Department split</h3><div class="canvasbox"><canvas id="ch-dep"></canvas></div></div>
        <div class="card"><h3>💊 Top medicines (30 d)</h3><div class="canvasbox"><canvas id="ch-med"></canvas></div></div>
        <div class="card"><h3>🛏 Room occupancy</h3><div class="canvasbox"><canvas id="ch-occ"></canvas></div>
          <div class="tiny muted center">${rep.rooms.occupied}/${rep.rooms.total} occupied</div></div>
      </div>
      <div class="grid g2 mb" style="align-items:start">
        <div class="card pad0"><table class="table"><thead><tr><th colspan="4">Today's consultations</th></tr>
          <tr><th>Time</th><th>Patient</th><th>Doctor</th><th>Diagnosis</th></tr></thead><tbody>
          ${rep.consultations.list.map(c => `<tr><td class="mono">${esc(c.time)}</td>
            <td>${esc(c.patient)}</td><td class="small">${esc(c.doctor)}</td>
            <td class="small">${esc(c.diagnosis)}</td></tr>`).join('')
            || '<tr><td colspan="4" class="empty">No consultations yet today.</td></tr>'}</tbody></table></div>
        <div>
          <div class="card mb"><h3>🔪 Surgeries today</h3>
            ${rep.surgeries.list.map(s => `<div class="small" style="margin:6px 0">
              <b>${esc(s.name)}</b> — ${esc(s.patient)} ${badge(s.status)}
              <div class="tiny muted">${esc(s.surgeon)} · ${esc(s.theatre)}</div></div>`).join('')
              || '<div class="empty">No surgeries today.</div>'}</div>
          <div class="card mb"><h3>📅 Appointments</h3>
            <div class="small">${Object.entries(rep.appointments.by_status).map(([k, v]) =>
              `<span class="chip">${esc(k)}: <b>${v}</b></span>`).join(' ') || 'None'}</div>
            <div class="tiny muted mt">Physio sessions today: <b>${rep.physio_sessions}</b></div></div>
          ${rep.low_stock.length ? `<div class="card" style="border-color:var(--orange)">
            <h3>⚠️ Low stock</h3>${rep.low_stock.map(m =>
              `<div class="small">${esc(m.name)} — <b>${m.stock}</b> (reorder at ${m.reorder_level})</div>`).join('')}</div>` : ''}
        </div>
      </div>`;

    $('#db-day').addEventListener('change', e => dashboard(box, e.target.value));

    const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
    const G = css('--green'), O = css('--orange'), R = css('--red'), B = '#2563EB', GD = css('--green-deep');
    const labels = ch.labels.map(d => d.slice(5));
    const base = { responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } } };
    CHARTS.push(new Chart($('#ch-rev'), { type: 'line',
      data: { labels, datasets: [{ data: ch.revenue, borderColor: GD, tension: .35,
        fill: true, backgroundColor: 'rgba(30,158,74,.10)', pointRadius: 0, borderWidth: 2.5 }] },
      options: { ...base, scales: { y: { ticks: { callback: v => '₹' + (v >= 1000 ? (v / 1000) + 'k' : v) } },
        x: { ticks: { maxTicksLimit: 8 } } } } }));
    CHARTS.push(new Chart($('#ch-con'), { type: 'bar',
      data: { labels, datasets: [{ data: ch.consultations, backgroundColor: G, borderRadius: 4 }] },
      options: { ...base, scales: { x: { ticks: { maxTicksLimit: 8 } }, y: { ticks: { precision: 0 } } } } }));
    CHARTS.push(new Chart($('#ch-dep'), { type: 'doughnut',
      data: { labels: ch.departments.map(d => d.department),
        datasets: [{ data: ch.departments.map(d => d.count), backgroundColor: [G, O, B, R] }] },
      options: { ...base, plugins: { legend: { position: 'bottom' } }, cutout: '62%' } }));
    CHARTS.push(new Chart($('#ch-med'), { type: 'bar', 
      data: { labels: ch.top_medicines.map(m => m.name.length > 18 ? m.name.slice(0, 17) + '…' : m.name),
        datasets: [{ data: ch.top_medicines.map(m => m.quantity), backgroundColor: O, borderRadius: 4 }] },
      options: { ...base, indexAxis: 'y' } }));
    const occ = Object.entries(ch.occupancy);
    CHARTS.push(new Chart($('#ch-occ'), { type: 'bar',
      data: { labels: occ.map(([k]) => k), datasets: [
        { label: 'Occupied', data: occ.map(([, v]) => v.occupied), backgroundColor: O, borderRadius: 4 },
        { label: 'Free', data: occ.map(([, v]) => v.total - v.occupied), backgroundColor: G, borderRadius: 4 }] },
      options: { ...base, plugins: { legend: { position: 'bottom' } },
        scales: { x: { stacked: true }, y: { stacked: true, ticks: { precision: 0 } } } } }));
  }

  /* ============================================ NEW CONSULTATION ===== */
  async function consult(box) {
    const info = await api('/api/public/info');
    const treatments = info.treatments.flatMap(t => t.items.map(i => `${t.name} — ${i.name}`));
    const meds = await api('/api/pharmacy/medicines');
    let rxRows = 0;
    box.innerHTML = `
      <h1 class="mb">New consultation</h1>
      <div class="card" style="max-width:860px">
        <form id="cn-form">
          ${V.patientPicker('cn-pt')}
          <div class="formgrid">
            <div class="field"><label>Department</label><select class="select" name="department">
              <option ${me.username === 'lalan' ? '' : 'selected'}>ORTHOPAEDICS</option>
              <option ${me.username === 'lalan' ? 'selected' : ''}>OPHTHALMOLOGY</option>
              <option>GENERAL</option></select></div>
            <div class="field"><label>Fee (₹ — blank = your standard fee)</label>
              <input class="input" type="number" name="fee" min="0" placeholder="auto"></div>
          </div>
          <div class="field"><label>Chief complaint *</label><input class="input" name="chief_complaint" required minlength="2"></div>
          <div class="field"><label>Diagnosis</label><input class="input" name="diagnosis"></div>
          <div class="field"><label>Clinical notes</label><textarea class="textarea" name="clinical_notes"></textarea></div>
          <div class="field"><label>Treatment / service given</label>
            <input class="input" name="treatments_given" list="cn-treat" placeholder="Start typing to pick from the 14 programmes…">
            <datalist id="cn-treat">${treatments.map(t => `<option value="${esc(t)}">`).join('')}</datalist></div>
          <div class="field"><label>Follow-up on</label><input class="input" type="date" name="follow_up_on"></div>
          <div class="divider"></div>
          <div class="flex between"><h3>💊 Prescription</h3>
            <button type="button" class="btn ghost sm" id="cn-addrx">＋ Add medicine</button></div>
          <div id="cn-rx"></div>
          <div class="field"><label>Prescription notes</label><input class="input" name="prescription_notes" placeholder="e.g. Take after food"></div>
          <button class="btn" style="margin-top:8px">Save consultation & generate OPD bill</button>
        </form>
      </div>`;
    const getPid = V.wirePatientPicker(box, 'cn-pt');

    const addRx = () => {
      const i = rxRows++;
      const row = document.createElement('div');
      row.className = 'formgrid'; row.dataset.rx = i;
      row.innerHTML = `
        <div class="field" style="grid-column:1/-1"><label>Medicine</label>
          <select class="select" data-f="medicine_id">${meds.map(m =>
            `<option value="${m.id}">${esc(m.name)} — ${rupee(m.unit_price)} (${m.stock_quantity} in stock)</option>`).join('')}</select></div>
        <div class="field"><label>Dosage</label><input class="input" data-f="dosage" value="1-0-1"></div>
        <div class="field"><label>Frequency</label><input class="input" data-f="frequency" value="Twice a day"></div>
        <div class="field"><label>Days</label><input class="input" type="number" data-f="duration_days" value="5" min="1"></div>
        <div class="field"><label>Qty</label><input class="input" type="number" data-f="quantity" value="1" min="1"></div>
        <div class="field" style="grid-column:1/-1"><label>Instructions
          <button type="button" class="btn danger sm" data-rmrx="${i}" style="float:right">Remove</button></label>
          <input class="input" data-f="instructions" value="After food"></div>`;
      $('#cn-rx').appendChild(row);
    };
    $('#cn-addrx').addEventListener('click', addRx);
    on(box, e => {
      const rm = e.target.closest('[data-rmrx]');
      if (rm) $(`[data-rx="${rm.dataset.rmrx}"]`)?.remove();
    });

    $('#cn-form').addEventListener('submit', async e => {
      e.preventDefault();
      const body = formData(e.target);
      body.patient_id = getPid();
      if (!body.patient_id) return toast('Pick a patient from the search list.', 'warn');
      if (body.fee) body.fee = +body.fee;
      body.prescription_items = $$('#cn-rx [data-rx]').map(row => {
        const g = f => $(`[data-f=${f}]`, row).value;
        return { medicine_id: +g('medicine_id'), dosage: g('dosage'),
          frequency: g('frequency'), duration_days: +g('duration_days'),
          quantity: +g('quantity'), instructions: g('instructions') };
      });
      try {
        const c = await api('/api/consultations', { method: 'POST', body });
        SFX.success();
        toast(`Saved — OPD bill generated for ${esc(c.patient_name)}`);
        location.hash = `patient-${c.patient_id}`;
      } catch (err) { toast(err.message, 'err'); }
    });
  }

  /* ==================================================== MEDICLAIMS === */
  async function mediclaims(box) {
    const list = await api('/api/mediclaims');
    const NEXT = { DRAFT: [], FINALIZED: ['SUBMITTED'], SUBMITTED: ['APPROVED', 'REJECTED'] };
    box.innerHTML = `
      <h1 class="mb">Mediclaims</h1>
      <p class="muted small mb">A claim opens as <b>DRAFT</b> at admission and is frozen as
        <b>FINALIZED</b> (with the complete stay summary) at discharge — then it can be
        submitted to the insurer and approved / rejected.</p>
      ${V.table(['Claim', 'Patient', 'Insurer', 'Status', 'Finalized', ''],
        list.map(c => `<tr><td class="mono"><b>${esc(c.claim_number)}</b></td>
          <td>${esc(c.patient_name)} <span class="tiny muted">${esc(c.patient_code)}</span></td>
          <td class="small">${esc(c.insurer_name || '—')}<div class="tiny muted">${esc(c.policy_number || '')}</div></td>
          <td>${badge(c.status)}</td><td class="nowrap small">${c.finalized_at ? fmtDT(c.finalized_at) : '—'}</td>
          <td class="right nowrap">
            <button class="btn ghost sm" data-claim="${c.id}">Open</button>
            ${(NEXT[c.status] || []).map(n =>
              `<button class="btn ${n === 'REJECTED' ? 'danger' : ''} sm" data-cl="${c.id}" data-st="${n}">${n[0] + n.slice(1).toLowerCase()}</button>`).join(' ')}
          </td></tr>`), 'No claims yet.')}`;
    on(box, async e => {
      const open = e.target.closest('[data-claim]');
      if (open) {
        const c = list.find(x => x.id === +open.dataset.claim);
        return claimModal(c);
      }
      const st = e.target.closest('[data-cl]');
      if (st) {
        try {
          await api(`/api/mediclaims/${st.dataset.cl}`, { method: 'PATCH', body: { status: st.dataset.st } });
          toast(`Claim ${st.dataset.st.toLowerCase()}`); mediclaims(box);
        } catch (err) { toast(err.message, 'err'); }
      }
    });

    function claimModal(c) {
      const s = c.summary || {};
      modal(`Claim ${c.claim_number}`, `
        <div class="flex between"><div><b>${esc(c.patient_name)}</b> (${esc(c.patient_code)})</div>${badge(c.status)}</div>
        <form id="clm-form" class="formgrid mt">
          <div class="field"><label>Insurer</label><input class="input" name="insurer_name" value="${esc(c.insurer_name || '')}"></div>
          <div class="field"><label>Policy no.</label><input class="input" name="policy_number" value="${esc(c.policy_number || '')}"></div>
          <div class="field" style="grid-column:1/-1"><label>TPA</label><input class="input" name="tpa_name" value="${esc(c.tpa_name || '')}"></div>
        </form>
        ${s.admission ? `<div class="divider"></div><h4>Frozen discharge summary</h4>
          <div class="small">
            <div><b>Admitted:</b> ${fmtDT(s.admission.admitted_at)} → <b>Discharged:</b> ${fmtDT(s.admission.discharged_at)}
              (${s.admission.hours} h · ${Math.ceil(s.admission.hours / 24)} billable day${s.admission.hours > 24 ? 's' : ''})</div>
            <div><b>Room:</b> ${esc(s.admission.room || '')} · <b>Doctor:</b> ${esc(s.admission.primary_doctor || '')}</div>
            <div><b>Diagnosis:</b> ${esc(s.admission.diagnosis || '—')} · <b>Type:</b> ${esc(s.admission.type)}</div>
            <table class="table mt"><tbody>
              ${(s.bill?.items || []).map(i => `<tr><td>${esc(i.description)}</td>
                <td class="mono right">${rupee(i.amount)}</td></tr>`).join('')}
              ${s.bill?.discount ? `<tr><td>Discount</td><td class="mono right">− ${rupee(s.bill.discount)}</td></tr>` : ''}
              <tr><td><b>Total billed (${esc(s.bill?.number || '')})</b></td><td class="mono right"><b>${rupee(s.bill?.total || 0)}</b></td></tr>
            </tbody></table>
            ${s.discharge_summary ? `<div class="tiny muted mt">${esc(s.discharge_summary)}</div>` : ''}</div>` : '<p class="tiny muted mt">Summary will be frozen automatically at discharge.</p>'}`,
        `<button class="btn ghost" data-action="close-modal">Close</button>
         <button class="btn" id="clm-save">Save details</button>`);
      $('#clm-save').addEventListener('click', async () => {
        try {
          await api(`/api/mediclaims/${c.id}`, { method: 'PATCH', body: formData($('#clm-form')) });
          toast('Claim updated'); closeModal(); mediclaims(box);
        } catch (err) { toast(err.message, 'err'); }
      });
    }
  }

  /* ================================================= STAFF & HR ====== */
  async function staffMgmt(box) {
    const list = await api('/api/staff');
    box.innerHTML = `
      <div class="flex between wrap mb"><h1>Staff & HR</h1>
        <button class="btn" id="st-new">＋ Add employee</button></div>
      ${V.table(['Employee', 'Designation', 'Department', 'Phone', 'Salary', 'Joined', ''],
        list.map(s => `<tr class="clickable" data-st="${s.id}">
          <td><div class="flex"><span class="avatar">${initials(s.full_name)}</span>
            <div><b>${esc(s.full_name)}</b><div class="tiny muted">@${esc(s.username || '—')} · ${esc(s.qualification)}</div></div></div></td>
          <td>${badge(s.designation)}</td><td class="small">${esc(s.department)}</td>
          <td class="mono">${esc(s.phone)}</td><td class="mono">${rupee(s.monthly_salary)}</td>
          <td class="small">${fmtDate(s.date_joined)}</td>
          <td class="right"><button class="btn ghost sm" data-st="${s.id}">Open</button></td></tr>`))}`;
    on(box, e => {
      const r = e.target.closest('[data-st]');
      if (r) location.hash = `staff-${r.dataset.st}`;
      if (e.target.id === 'st-new') staffForm();
    });
  }

  function staffForm() {
    modal('Add employee', `
      <form id="stf-form"><div class="formgrid">
        <div class="field"><label>Full name *</label><input class="input" name="full_name" required></div>
        <div class="field"><label>Designation</label><select class="select" name="designation">
          <option>NURSE</option><option>CLERK</option><option>PHARMACIST</option>
          <option>PHYSIOTHERAPIST</option><option>TECHNICIAN</option><option>INTERN</option>
          <option>DOCTOR</option><option>ADMIN_STAFF</option></select></div>
        <div class="field"><label>Sex</label><select class="select" name="sex">
          <option>FEMALE</option><option>MALE</option><option>OTHER</option></select></div>
        <div class="field"><label>Date of birth *</label><input class="input" type="date" name="date_of_birth" required></div>
        <div class="field"><label>Qualification</label><input class="input" name="qualification"></div>
        <div class="field"><label>Department</label><input class="input" name="department" value="NURSING"></div>
        <div class="field"><label>Phone *</label><input class="input" name="phone" pattern="[0-9]{10}" required></div>
        <div class="field"><label>Email</label><input class="input" name="email" type="email"></div>
        <div class="field"><label>Monthly salary (₹) *</label><input class="input" type="number" name="monthly_salary" min="0" required></div>
        <div class="field"><label>Date joined *</label><input class="input" type="date" name="date_joined" value="${todayISO()}" required></div>
        <div class="field"><label>Shift start</label><input class="input" name="shift_start" value="09:00" pattern="[0-2][0-9]:[0-5][0-9]"></div>
        <div class="field"><label>Shift end</label><input class="input" name="shift_end" value="17:00" pattern="[0-2][0-9]:[0-5][0-9]"></div>
      </div>
      <h4 class="mt">KYC & bank (private to admin)</h4>
      <div class="formgrid">
        <div class="field"><label>Aadhar (12 digits)</label><input class="input" name="aadhar_number" pattern="[0-9]{12}"></div>
        <div class="field"><label>PAN</label><input class="input" name="pan_number" pattern="[A-Z]{5}[0-9]{4}[A-Z]" placeholder="ABCDE1234F"></div>
        <div class="field"><label>Bank account</label><input class="input" name="bank_account_number"></div>
        <div class="field"><label>IFSC</label><input class="input" name="bank_ifsc"></div>
        <div class="field" style="grid-column:1/-1"><label>Bank name & branch</label><input class="input" name="bank_name"></div>
      </div>
      <h4 class="mt">Login</h4>
      <div class="formgrid">
        <div class="field"><label>Username *</label><input class="input" name="username" pattern="[a-z0-9_.]{3,30}" required></div>
        <div class="field"><label>Password * (min 8)</label><input class="input" type="password" name="password" minlength="8" required></div>
      </div>
      <div class="field"><label>Address</label><input class="input" name="address"></div>
      </form>`,
      `<button class="btn ghost" data-action="close-modal">Cancel</button>
       <button class="btn" id="stf-save">Add employee</button>`);
    $('#stf-save').addEventListener('click', async () => {
      const body = formData($('#stf-form'));
      if (body.monthly_salary) body.monthly_salary = +body.monthly_salary;
      try {
        const s = await api('/api/staff', { method: 'POST', body });
        toast(`${s.full_name} added to the team`); closeModal(); location.hash = `staff-${s.id}`;
      } catch (err) { toast(err.message, 'err'); }
    });
  }

  async function staffDetail(box, id) {
    const [s, pays] = await Promise.all([
      api(`/api/staff/${id}`), api(`/api/staff/payroll/history?staff_id=${id}`)]);
    box.innerHTML = `
      <button class="btn ghost sm mb" data-view="staffm">← All staff</button>
      <div class="card mb"><div class="flex between wrap">
        <div class="flex"><span class="avatar" style="width:54px;height:54px;font-size:20px">${initials(s.full_name)}</span>
          <div><h2 style="margin:0">${esc(s.full_name)}</h2>
            <div class="small muted">${badge(s.designation)} ${esc(s.department)} · @${esc(s.username || '—')}
              · joined ${fmtDate(s.date_joined)}</div>
            <div class="small muted">${esc(s.qualification || '')}</div></div></div>
        <div class="right small">
          <div class="mono" style="font-size:20px;font-weight:800">${rupee(s.monthly_salary)}<span class="tiny muted">/mo</span></div>
          <div class="tiny muted">Shift ${esc(s.shift_start)}–${esc(s.shift_end)}</div></div></div>
      <div class="divider"></div>
      <div class="grid g3 small">
        <div><b>Contact</b><div class="muted">${esc(s.phone)} · ${esc(s.email || '—')}</div>
          <div class="muted">${esc(s.address || '')}</div></div>
        <div><b>KYC</b><div class="muted">Aadhar: ${esc(s.aadhar_number || '—')}</div>
          <div class="muted">PAN: ${esc(s.pan_number || '—')}</div></div>
        <div><b>Bank</b><div class="muted">${esc(s.bank_name || '—')}</div>
          <div class="muted mono">${esc(s.bank_account_number || '')} ${s.bank_ifsc ? `· ${esc(s.bank_ifsc)}` : ''}</div></div>
      </div></div>
      <div class="card mb"><h3>🗓 Attendance calendar</h3><div id="sd-map"><div class="loader"></div></div></div>
      <div class="card"><h3>💰 Salary history</h3>
        ${V.table(['Period', 'Amount', 'Mode', 'Reference', 'Paid on'],
          pays.map(p => `<tr><td><b>${String(p.month).padStart(2, '0')}/${p.year}</b></td>
            <td class="mono">${rupee(p.amount)}</td>
            <td>${p.mode === 'AUTOPAY' ? badge('APPROVED') : '<span class="badge blue">MANUAL</span>'}</td>
            <td class="mono small">${esc(p.reference)}</td><td class="small">${fmtDT(p.paid_on)}</td></tr>`),
          'No salary payments recorded.')}</div>`;
    renderAttCalendar($('#sd-map'), await api(`/api/staff/${id}/attendance/heatmap?days=366`));
  }

  /* ===================================================== PAYROLL ===== */
  async function payroll(box) {
    const now = new Date();
    box.innerHTML = `
      <div class="flex between wrap mb"><h1>Payroll</h1>
        <div class="flex">
          <select class="select" id="pr-month" style="max-width:130px">
            ${Array.from({ length: 12 }, (_, i) => `<option value="${i + 1}" ${i === now.getMonth() ? 'selected' : ''}>
              ${new Date(2000, i).toLocaleString('en', { month: 'long' })}</option>`).join('')}</select>
          <input class="input" type="number" id="pr-year" value="${now.getFullYear()}" style="max-width:110px">
          <button class="btn orange" id="pr-autopay">⚡ Autopay all</button>
        </div></div>
      <div id="pr-list"><div class="loader"></div></div>`;
    const load = async () => {
      const m = +$('#pr-month').value, y = +$('#pr-year').value;
      const rows = await api(`/api/staff/payroll/preview?month=${m}&year=${y}`);
      $('#pr-list').innerHTML = V.table(
        ['Employee', 'Days present', 'Salary', 'Status', ''],
        rows.map(r => `<tr><td><b>${esc(r.full_name)}</b>
            <div class="tiny muted">${esc(r.designation)}</div></td>
          <td class="mono">${r.days_present}</td>
          <td class="mono">${rupee(r.monthly_salary)}</td>
          <td>${r.paid ? badge('PAID') + `<div class="tiny muted mono">${esc(r.reference)}</div>` : badge('PENDING')}</td>
          <td class="right">${r.paid ? '' :
            `<button class="btn sm" data-pay="${r.staff_id}">Pay now</button>`}</td></tr>`));
    };
    $('#pr-month').addEventListener('change', load);
    $('#pr-year').addEventListener('change', load);
    on(box, async e => {
      const m = +$('#pr-month').value, y = +$('#pr-year').value;
      const b = e.target.closest('[data-pay]');
      if (b) {
        try {
          const p = await api('/api/staff/payroll/pay', { method: 'POST',
            body: { staff_id: +b.dataset.pay, month: m, year: y, mode: 'MANUAL' } });
          SFX.success(); toast(`Paid — ${p.reference}`); load();
        } catch (err) { toast(err.message, 'err'); }
      }
      if (e.target.id === 'pr-autopay') {
        try {
          const res = await api('/api/staff/payroll/autopay', { method: 'POST', body: { month: m, year: y } });
          SFX.success();
          toast(`Autopay: ${(res.paid || []).length} paid · ${(res.skipped_already_paid || []).length} already done`);
          load();
        } catch (err) { toast(err.message, 'err'); }
      }
    });
    await load();
  }
})();
