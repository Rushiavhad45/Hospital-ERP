/* Shared authenticated views for the staff desk and admin console.
   Everything lives under the V namespace; admin-only affordances are gated
   on V.isAdmin (set by staff.js / admin.js before routing starts). */
'use strict';

const V = { isAdmin: false, me: null };

/* tiny helpers -------------------------------------------------------- */
V.table = (heads, rows, emptyMsg = 'Nothing here yet.') => rows.length
  ? `<div class="card pad0"><table class="table"><thead><tr>
      ${heads.map(h => `<th>${h}</th>`).join('')}</tr></thead>
      <tbody>${rows.join('')}</tbody></table></div>`
  : `<div class="card empty"><div class="big">🍃</div>${emptyMsg}</div>`;

V.opts = (list, val, lab, sel) => list.map(o =>
  `<option value="${o[val]}" ${sel == o[val] ? 'selected' : ''}>${esc(o[lab])}</option>`).join('');

V.doctorOptions = async sel =>
  V.opts(await api('/api/staff/doctors'), 'id', 'full_name', sel);
V.nurseOptions = async sel =>
  V.opts(await api('/api/staff/nurses'), 'id', 'full_name', sel);

V.patientPicker = (id = 'pt-pick') => `
  <div class="field"><label>Patient</label>
    <input class="input" id="${id}" list="${id}-list" placeholder="Search name / phone / code…" autocomplete="off">
    <datalist id="${id}-list"></datalist>
    <input type="hidden" id="${id}-id"></div>`;

V.wirePatientPicker = (root, id = 'pt-pick') => {
  const inp = $(`#${id}`, root), list = $(`#${id}-list`, root), hid = $(`#${id}-id`, root);
  let items = [];
  inp.addEventListener('input', async () => {
    const q = inp.value.trim();
    const hit = items.find(p => `${p.full_name} · ${p.patient_code}` === q);
    if (hit) { hid.value = hit.id; return; }
    hid.value = '';
    if (q.length < 2) return;
    try {
      items = await api(`/api/patients?q=${encodeURIComponent(q)}`);
      list.innerHTML = items.map(p =>
        `<option value="${esc(p.full_name)} · ${esc(p.patient_code)}">${esc(p.phone)}</option>`).join('');
    } catch (_) {}
  });
  return () => +hid.value || null;
};

/* =====================================================  PATIENTS  ==== */
V.patients = async box => {
  box.innerHTML = `
    <div class="flex between wrap mb"><h1>Patients</h1>
      <button class="btn" id="pt-new">＋ Register patient</button></div>
    <div class="searchbar"><input class="input" id="pt-q" placeholder="Search by name, phone or code…">
      <button class="btn ghost" id="pt-go">Search</button></div>
    <div id="pt-list"><div class="loader"></div></div>`;
  const load = async () => {
    const q = $('#pt-q').value.trim();
    const list = await api(`/api/patients?q=${encodeURIComponent(q)}`);
    $('#pt-list').innerHTML = V.table(
      ['Patient', 'Code', 'Age / Sex', 'Phone', 'Portal', ''],
      list.map(p => `<tr class="clickable" data-pid="${p.id}">
        <td><div class="flex"><span class="avatar">${initials(p.full_name)}</span>
            <div><b>${esc(p.full_name)}</b><div class="tiny muted">${esc(p.blood_group || '')}</div></div></div></td>
        <td class="mono">${esc(p.patient_code)}</td>
        <td>${p.age} · ${p.sex[0]}</td><td class="mono">${esc(p.phone)}</td>
        <td>${p.has_login ? badge('ACTIVE') : '<span class="badge gray">NO LOGIN</span>'}</td>
        <td class="right"><button class="btn ghost sm" data-pid="${p.id}">Open</button></td></tr>`),
      'No patients match that search.');
  };
  $('#pt-go').addEventListener('click', load);
  $('#pt-q').addEventListener('keydown', e => e.key === 'Enter' && load());
  on(box, e => {
    const row = e.target.closest('[data-pid]');
    if (row) location.hash = `patient-${row.dataset.pid}`;
    if (e.target.id === 'pt-new') V.patientForm();
  });
  await load();
};

V.patientForm = () => {
  modal('Register a new patient', `
    <form id="pt-form"><div class="formgrid">
      <div class="field"><label>Full name *</label><input class="input" name="full_name" required></div>
      <div class="field"><label>Phone *</label><input class="input" name="phone" pattern="[0-9]{10}" required></div>
      <div class="field"><label>Sex *</label><select class="select" name="sex">
        <option>MALE</option><option>FEMALE</option><option>OTHER</option></select></div>
      <div class="field"><label>Date of birth *</label><input class="input" type="date" name="date_of_birth" required></div>
      <div class="field"><label>Blood group</label><select class="select" name="blood_group"><option value="">—</option>
        <option>A+</option><option>A-</option><option>B+</option><option>B-</option>
        <option>AB+</option><option>AB-</option><option>O+</option><option>O-</option></select></div>
      <div class="field"><label>Email</label><input class="input" type="email" name="email"></div>
    </div>
    <div class="field"><label>Address</label><input class="input" name="address"></div>
    <div class="formgrid">
      <div class="field"><label>Emergency contact</label><input class="input" name="emergency_contact_name"></div>
      <div class="field"><label>Emergency phone</label><input class="input" name="emergency_contact_phone"></div>
    </div>
    <div class="field"><label>Allergies</label><input class="input" name="allergies"></div>
    <div class="field"><label>Medical history</label><textarea class="textarea" name="medical_history"></textarea></div>
    <label class="check"><input type="checkbox" id="pt-login"> Create patient-portal login</label>
    <div class="formgrid hide" id="pt-login-fields">
      <div class="field"><label>Username</label><input class="input" name="username" pattern="[a-z0-9_.]{3,30}"></div>
      <div class="field"><label>Password (min 8)</label><input class="input" type="password" name="password" minlength="8"></div>
    </div></form>`,
    `<button class="btn ghost" data-action="close-modal">Cancel</button>
     <button class="btn" id="pt-save">Register</button>`);
  $('#pt-login').addEventListener('change', e =>
    $('#pt-login-fields').classList.toggle('hide', !e.target.checked));
  $('#pt-save').addEventListener('click', async () => {
    const body = formData($('#pt-form'));
    body.create_login = $('#pt-login').checked;
    try {
      const p = await api('/api/patients', { method: 'POST', body });
      toast(`Registered ${p.full_name} (${p.patient_code})`);
      closeModal(); location.hash = `patient-${p.id}`;
    } catch (err) { toast(err.message, 'err'); }
  });
};

/* ------------------------------------------------- patient detail ---- */
V.patientDetail = async (box, id) => {
  const p = await api(`/api/patients/${id}`);
  box.innerHTML = `
    <button class="btn ghost sm mb" data-view="patients">← All patients</button>
    <div class="card mb"><div class="flex between wrap">
      <div class="flex"><span class="avatar" style="width:54px;height:54px;font-size:20px">${initials(p.full_name)}</span>
        <div><h2 style="margin:0">${esc(p.full_name)}</h2>
          <div class="muted small">${esc(p.patient_code)} · ${p.age} yrs · ${p.sex} · ${esc(p.blood_group || '—')}
            · 📞 ${esc(p.phone)}</div></div></div>
      <div class="flex">${p.has_login ? badge('ACTIVE') + '<span class="tiny muted">portal</span>'
        : `<button class="btn ghost sm" id="pd-enable">Enable portal login</button>`}</div></div>
    <div class="divider"></div>
    <div class="grid g3 small">
      <div><b>Address</b><div class="muted">${esc(p.address || '—')}</div></div>
      <div><b>Emergency</b><div class="muted">${esc(p.emergency_contact_name || '—')} · ${esc(p.emergency_contact_phone || '')}</div></div>
      <div><b>Allergies</b><div class="muted">${esc(p.allergies || '—')}</div></div>
    </div>
    ${p.medical_history ? `<div class="small mt"><b>History:</b> <span class="muted">${esc(p.medical_history)}</span></div>` : ''}
    </div>
    <div class="tabbar" id="pd-tabs">
      <button class="tab active" data-tab="visits">Visits</button>
      <button class="tab" data-tab="docs">Documents</button>
      <button class="tab" data-tab="physio">Physiotherapy</button>
      <button class="tab" data-tab="bills">Bills</button>
      <button class="tab" data-tab="adm">Admissions</button>
    </div>
    <div id="pd-body"><div class="loader"></div></div>`;

  $('#pd-enable')?.addEventListener('click', () => V.enableLogin(p));
  const tabs = {
    visits: () => V.pdVisits(id), docs: () => V.pdDocs(id),
    physio: () => V.pdPhysio(id), bills: () => V.pdBills(id),
    adm: () => V.pdAdmissions(id),
  };
  $('#pd-tabs').addEventListener('click', e => {
    const t = e.target.closest('.tab'); if (!t) return;
    $$('#pd-tabs .tab').forEach(x => x.classList.toggle('active', x === t));
    tabs[t.dataset.tab]();
  });
  tabs.visits();
};

V.enableLogin = p => {
  modal(`Portal login for ${p.full_name}`, `
    <div class="field"><label>Username</label><input class="input" id="el-u" pattern="[a-z0-9_.]{3,30}"></div>
    <div class="field"><label>Password (min 8 chars)</label><input class="input" id="el-p" type="password"></div>`,
    `<button class="btn ghost" data-action="close-modal">Cancel</button>
     <button class="btn" id="el-save">Create login</button>`);
  $('#el-save').addEventListener('click', async () => {
    const form = new FormData();
    form.set('username', $('#el-u').value.trim());
    form.set('password', $('#el-p').value);
    try {
      await api(`/api/patients/${p.id}/enable-login`, { method: 'POST', form });
      toast('Portal login created'); closeModal(); location.reload();
    } catch (err) { toast(err.message, 'err'); }
  });
};

V.pdVisits = async id => {
  const list = await api(`/api/consultations?patient_id=${id}`);
  const root = document.createElement('div');
  root.innerHTML = V.table(['Date', 'Doctor', 'Diagnosis', 'Fee', ''],
    list.map(c => `<tr><td class="nowrap">${fmtDT(c.visited_at)}</td>
      <td>${esc(c.doctor_name)}</td><td>${esc(c.diagnosis || c.chief_complaint)}</td>
      <td class="mono">${rupee(c.fee)}</td>
      <td class="right"><button class="btn ghost sm" data-cid="${c.id}">View</button></td></tr>`),
    'No consultations recorded yet.');
  root.addEventListener('click', e => {
    const b = e.target.closest('[data-cid]');
    if (b) V.consultModal(+b.dataset.cid);
  });
  $('#pd-body').replaceChildren(root);
};

V.consultModal = async cid => {
  const c = await api(`/api/consultations/${cid}`);
  const rx = c.prescription;
  modal(`Consultation · ${fmtDT(c.visited_at)}`, `
    <div class="small"><b>${esc(c.patient_name)}</b> (${esc(c.patient_code)}) · ${esc(c.doctor_name)} · ${esc(c.department)}</div>
    <div class="divider"></div>
    <p><b>Complaint:</b> ${esc(c.chief_complaint)}</p>
    <p><b>Diagnosis:</b> ${esc(c.diagnosis || '—')}</p>
    ${c.clinical_notes ? `<p><b>Notes:</b> ${esc(c.clinical_notes)}</p>` : ''}
    ${c.treatments_given ? `<p><b>Treatment:</b> ${esc(c.treatments_given)}</p>` : ''}
    <p><b>Fee:</b> ${rupee(c.fee)} ${c.follow_up_on ? ` · <b>Follow-up:</b> ${fmtDate(c.follow_up_on)}` : ''}</p>
    ${rx ? `<div class="divider"></div><h4>Prescription ${rx.dispensed ? badge('COMPLETED') : badge('PENDING')}</h4>
      ${rx.items.map(i => `<div class="small" style="margin:6px 0">💊 <b>${esc(i.medicine_name)}</b>
        — ${esc(i.dosage)} · ${esc(i.frequency)} · ${i.duration_days} days · qty ${i.quantity}</div>`).join('')}
      ${rx.notes ? `<div class="tiny muted">${esc(rx.notes)}</div>` : ''}` : ''}`,
    `<button class="btn ghost" data-action="print">🖨 Print</button>
     <button class="btn" data-action="close-modal">Close</button>`);
};

V.pdDocs = async id => {
  const list = await api(`/api/patients/${id}/documents`);
  const root = document.createElement('div');
  root.innerHTML = `
    <div class="card mb"><h4>Upload scan / report</h4>
      <form id="doc-form" class="formgrid">
        <div class="field"><label>File (png / jpg / webp / pdf, ≤ 10 MB)</label>
          <input class="input" type="file" name="file" accept=".png,.jpg,.jpeg,.webp,.pdf" required></div>
        <div class="field"><label>Type</label><select class="select" name="doc_type">
          <option>XRAY</option><option>MRI</option><option>CT_SCAN</option><option>ULTRASOUND</option>
          <option>LAB_REPORT</option><option>PRESCRIPTION_PAPER</option>
          <option>TREATMENT_PAPER</option><option>DISCHARGE_SUMMARY</option></select></div>
        <div class="field"><label>Title</label><input class="input" name="title" required minlength="2"></div>
        <div class="field"><label>Taken on</label><input class="input" type="date" name="taken_on"></div>
        <div class="field" style="grid-column:1/-1"><label>Notes</label><input class="input" name="notes"></div>
        <div><button class="btn">Upload</button></div>
      </form></div>
    ${V.table(['Title', 'Type', 'Taken', 'Size', ''],
      list.map(d => `<tr><td><b>${esc(d.title)}</b><div class="tiny muted">${esc(d.original_name)}</div></td>
        <td>${badge(d.doc_type)}</td><td>${fmtDate(d.taken_on)}</td>
        <td class="mono">${(d.size_bytes / 1024).toFixed(0)} KB</td>
        <td class="right"><a class="btn ghost sm" target="_blank" href="/api/documents/${d.id}/download">Open</a></td></tr>`),
      'No documents uploaded yet.')}`;
  $('#pd-body').replaceChildren(root);
  $('#doc-form').addEventListener('submit', async e => {
    e.preventDefault();
    try {
      await api(`/api/patients/${id}/documents`, { method: 'POST', form: new FormData(e.target) });
      toast('Document uploaded'); V.pdDocs(id);
    } catch (err) { toast(err.message, 'err'); }
  });
};

V.pdPhysio = async id => { await V.physioList($('#pd-body'), id); };
V.pdBills = async id => { await V.billList($('#pd-body'), { patient_id: id }); };
V.pdAdmissions = async id => {
  const list = await api(`/api/admissions?patient_id=${id}`);
  const root = document.createElement('div');
  root.innerHTML = V.table(['Admitted', 'Room', 'Reason', 'Status', ''],
    list.map(a => `<tr><td class="nowrap">${fmtDT(a.admitted_at)}</td>
      <td><b>${esc(a.room_number)}</b> <span class="tiny muted">${esc(a.room_type)}</span></td>
      <td>${esc(a.reason)}</td><td>${badge(a.status)}</td>
      <td class="right"><button class="btn ghost sm" data-goadm="${a.id}">Open</button></td></tr>`),
    'Never admitted.');
  root.addEventListener('click', e => {
    const b = e.target.closest('[data-goadm]');
    if (b) location.hash = `admission-${b.dataset.goadm}`;
  });
  $('#pd-body').replaceChildren(root);
};

/* ==================================================  APPOINTMENTS ==== */
V.appointments = async box => {
  const today = todayISO();
  box.innerHTML = `
    <div class="flex between wrap mb"><h1>Appointments</h1>
      <input class="input" type="date" id="ap-day" value="${today}" style="max-width:180px"></div>
    <div id="ap-list"><div class="loader"></div></div>`;
  const load = async () => {
    const day = $('#ap-day').value || today;
    const list = await api(`/api/appointments?day=${day}`);
    $('#ap-list').innerHTML = V.table(
      ['Slot', 'Patient', 'Doctor', 'Booked via', 'Status', 'Actions'],
      list.map(a => {
        const sameDay = a.appointment_date === today;
        const acts = [];
        if (a.status === 'BOOKED' && sameDay)
          acts.push(`<button class="btn sm" data-ap="${a.id}" data-st="CONFIRMED">Confirm</button>`);
        if (a.status === 'CONFIRMED')
          acts.push(`<button class="btn ghost sm" data-ap="${a.id}" data-st="COMPLETED">Done</button>`);
        if (['BOOKED', 'CONFIRMED'].includes(a.status)) {
          acts.push(`<button class="btn ghost sm" data-ap="${a.id}" data-st="NO_SHOW">No-show</button>`);
          acts.push(`<button class="btn danger sm" data-ap="${a.id}" data-st="CANCELLED">✕</button>`);
        }
        return `<tr><td class="mono"><b>${fmtSlot(a.slot)}</b></td>
          <td><b>${esc(a.patient_name)}</b><div class="tiny muted mono">${esc(a.phone)} · ${esc(a.code)}</div></td>
          <td>${esc(a.doctor_name)}</td><td><span class="chip">${esc(a.booked_via)}</span></td>
          <td>${badge(a.status)}</td><td class="right nowrap">${acts.join(' ')}</td></tr>`;
      }), 'No appointments for this day.');
  };
  $('#ap-day').addEventListener('change', load);
  on(box, async e => {
    const b = e.target.closest('[data-ap]');
    if (!b) return;
    try {
      await api(`/api/appointments/${b.dataset.ap}/status`,
        { method: 'PATCH', body: { status: b.dataset.st } });
      toast(`Appointment ${b.dataset.st.toLowerCase().replace('_', ' ')}`); load();
    } catch (err) { toast(err.message, 'err'); }
  });
  await load();
};

/* ====================================================  ADMISSIONS ==== */
V.admissions = async box => {
  box.innerHTML = `
    <div class="flex between wrap mb"><h1>Admissions</h1>
      <button class="btn" id="adm-new">＋ Admit patient</button></div>
    <div class="tabbar"><button class="tab active" data-f="ADMITTED">Active</button>
      <button class="tab" data-f="">All</button></div>
    <div id="adm-list"><div class="loader"></div></div>`;
  let filter = 'ADMITTED';
  const load = async () => {
    const list = await api(`/api/admissions${filter ? `?status=${filter}` : ''}`);
    $('#adm-list').innerHTML = V.table(
      ['Patient', 'Room', 'Doctor', 'Since', 'Type', 'Status', ''],
      list.map(a => `<tr class="clickable" data-adm="${a.id}">
        <td><b>${esc(a.patient_name)}</b><div class="tiny muted">${esc(a.reason)}</div></td>
        <td><b>${esc(a.room_number)}</b> <span class="tiny muted">${esc(a.room_type)}</span></td>
        <td>${esc(a.doctor_name)}</td>
        <td class="nowrap">${fmtDT(a.admitted_at)}<div class="tiny muted">${a.hours_admitted} h</div></td>
        <td>${a.admission_type === 'EMERGENCY' ? badge('EMERGENCY') : '<span class="badge gray">PLANNED</span>'}</td>
        <td>${badge(a.status)}</td>
        <td class="right"><button class="btn ghost sm" data-adm="${a.id}">Open</button></td></tr>`),
      'No admissions.');
  };
  on(box, e => {
    const t = e.target.closest('.tab');
    if (t) { $$('.tab', box).forEach(x => x.classList.toggle('active', x === t)); filter = t.dataset.f; load(); }
    const row = e.target.closest('[data-adm]');
    if (row) location.hash = `admission-${row.dataset.adm}`;
    if (e.target.id === 'adm-new') V.admitForm();
  });
  await load();
};

V.admitForm = async () => {
  const rooms = (await api('/api/rooms')).filter(r => r.status === 'AVAILABLE');
  modal('Admit a patient', `
    <form id="adm-form">
      ${V.patientPicker('adm-pt')}
      <div class="formgrid">
        <div class="field"><label>Room</label><select class="select" name="room_id">
          ${rooms.map(r => `<option value="${r.id}">${esc(r.room_number)} — ${esc(r.room_type)} (${rupee(r.daily_rate)}/day)</option>`).join('')}
        </select></div>
        <div class="field"><label>Type</label><select class="select" name="admission_type">
          <option>PLANNED</option><option>EMERGENCY</option></select></div>
        <div class="field"><label>Primary doctor</label><select class="select" name="primary_doctor_id">${await V.doctorOptions()}</select></div>
        <div class="field"><label>Assigned nurse</label><select class="select" name="assigned_nurse_id">
          <option value="">—</option>${await V.nurseOptions()}</select></div>
      </div>
      <div class="field"><label>Reason for admission *</label><input class="input" name="reason" required minlength="2"></div>
      <div class="field"><label>Diagnosis</label><input class="input" name="diagnosis"></div>
      <div class="field"><label>Admitted at (leave blank = now; backdating allowed)</label>
        <input class="input" type="datetime-local" name="admitted_at"></div>
    </form>`,
    `<button class="btn ghost" data-action="close-modal">Cancel</button>
     <button class="btn" id="adm-save">Admit</button>`);
  const getPid = V.wirePatientPicker($('#modal-bd'), 'adm-pt');
  $('#adm-save').addEventListener('click', async () => {
    const body = formData($('#adm-form'));
    body.patient_id = getPid();
    if (!body.patient_id) return toast('Pick a patient from the list.', 'warn');
    ['room_id', 'primary_doctor_id', 'assigned_nurse_id'].forEach(k => body[k] && (body[k] = +body[k]));
    try {
      const a = await api('/api/admissions', { method: 'POST', body });
      toast(`Admitted to ${a.room_number}`); closeModal();
      location.hash = `admission-${a.id}`;
    } catch (err) { toast(err.message, 'err'); }
  });
};

const CARE_ICON = { MEDICATION: '💊', DOCTOR_VISIT: '🩺', MEAL: '🍲', VITALS: '📈',
  TREATMENT: '🩹', SERVICE: '🧾', NOTE: '📝' };
const CARE_DOT = { MEDICATION: 'orange', DOCTOR_VISIT: 'blue', VITALS: '', MEAL: '',
  TREATMENT: 'orange', SERVICE: 'blue', NOTE: '' };

V.admissionDetail = async (box, id) => {
  const a = await api(`/api/admissions/${id}`);
  const active = a.status === 'ADMITTED';
  box.innerHTML = `
    <button class="btn ghost sm mb" data-view="admissions">← Admissions</button>
    <div class="card mb"><div class="flex between wrap">
      <div><h2 style="margin:0">${esc(a.patient_name)} <span class="muted small">(${esc(a.patient_code)})</span></h2>
        <div class="small muted">Room <b>${esc(a.room_number)}</b> (${esc(a.room_type)}) ·
          ${esc(a.doctor_name)} · Nurse: ${esc(a.nurse_name || '—')}</div>
        <div class="small muted">Admitted ${fmtDT(a.admitted_at)} · <b>${a.hours_admitted} h</b>
          ${a.admission_type === 'EMERGENCY' ? badge('EMERGENCY') : ''} ${badge(a.status)}</div>
        <div class="small mt"><b>Reason:</b> ${esc(a.reason)} ${a.diagnosis ? `· <b>Dx:</b> ${esc(a.diagnosis)}` : ''}</div>
        ${a.claim_number ? `<div class="tiny muted">Mediclaim ${esc(a.claim_number)}</div>` : ''}</div>
      <div class="flex" style="align-items:flex-start">
        ${active ? `<button class="btn orange" id="ad-discharge">Discharge & bill</button>`
                 : a.bill_id ? `<button class="btn ghost" data-bill="${a.bill_id}">View final bill</button>` : ''}</div>
    </div>
    ${a.discharge_summary ? `<div class="small"><b>Discharge summary:</b> <span class="muted">${esc(a.discharge_summary)}</span></div>` : ''}
    </div>
    <div class="grid g2" style="align-items:start">
      <div class="card">
        <h3>🕐 Care timeline</h3>
        <ul class="timeline" id="ad-timeline">${a.care_logs.map(l => `
          <li class="${CARE_DOT[l.log_type] || ''}">
            <div class="small"><b>${CARE_ICON[l.log_type] || '•'} ${esc(l.log_type.replace('_', ' '))}</b>
              <span class="tiny muted"> · ${fmtDT(l.logged_at)} · ${esc(l.logged_by || '')}</span></div>
            <div class="small muted">${esc(l.description)}
              ${l.charge ? ` — <b class="mono">${rupee(l.charge)}</b>` : ''}</div></li>`).join('')
          || '<div class="empty">No entries yet.</div>'}</ul>
      </div>
      <div>
        ${active ? `<div class="card mb"><h3>＋ Add care entry</h3>
          <form id="cl-form">
            <div class="field"><label>Type</label><select class="select" name="log_type" id="cl-type">
              <option>MEDICATION</option><option>DOCTOR_VISIT</option><option>VITALS</option>
              <option>MEAL</option><option>TREATMENT</option><option>SERVICE</option><option>NOTE</option>
            </select></div>
            <div id="cl-extra"></div>
            <div class="field"><label>Description *</label><input class="input" name="description" required></div>
            <button class="btn">Add entry</button>
          </form></div>` : ''}
        <div class="card"><h3>💰 Running charges</h3>
          <div class="small muted">Room, nursing and doctor-visit charges are computed at discharge.
            Medication and service charges below are already logged.</div>
          <div class="mt mono" style="font-size:20px;font-weight:800">${rupee(a.care_logs.reduce((t,l)=>t+(l.charge||0),0))}</div>
          <div class="tiny muted">logged so far (medicines, treatments, services)</div>
        </div>
      </div>
    </div>`;

  /* dynamic extra fields for the care-log form */
  const extra = async () => {
    const t = $('#cl-type').value;
    const box2 = $('#cl-extra');
    if (t === 'MEDICATION') {
      const meds = await api('/api/pharmacy/medicines');
      box2.innerHTML = `<div class="formgrid">
        <div class="field"><label>Medicine (stock is deducted)</label>
          <select class="select" name="medicine_id">${meds.map(m =>
            `<option value="${m.id}">${esc(m.name)} — ${rupee(m.unit_price)} (${m.stock_quantity} left)</option>`).join('')}
          </select></div>
        <div class="field"><label>Quantity</label><input class="input" type="number" name="quantity" value="1" min="1"></div></div>`;
    } else if (t === 'DOCTOR_VISIT') {
      box2.innerHTML = `<div class="field"><label>Doctor (₹400 per visit at discharge)</label>
        <select class="select" name="doctor_id">${await V.doctorOptions(a.primary_doctor_id)}</select></div>`;
    } else if (t === 'TREATMENT' || t === 'SERVICE') {
      box2.innerHTML = `<div class="field"><label>Charge (₹)</label>
        <input class="input" type="number" name="charge" value="0" min="0"></div>`;
    } else box2.innerHTML = '';
  };
  $('#cl-type')?.addEventListener('change', extra);
  if (active) await extra();

  $('#cl-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const body = formData(e.target);
    body.admission_id = a.id;
    ['medicine_id', 'quantity', 'doctor_id', 'charge'].forEach(k => body[k] && (body[k] = +body[k]));
    try {
      await api('/api/care-logs', { method: 'POST', body });
      toast('Entry added'); V.admissionDetail(box, id);
    } catch (err) { toast(err.message, 'err'); }
  });

  $('#ad-discharge')?.addEventListener('click', () => V.dischargeModal(a, box));
  on(box, e => {
    const b = e.target.closest('[data-bill]');
    if (b) V.billModal(+b.dataset.bill);
  });
};

V.dischargeModal = (a, box) => {
  modal(`Discharge ${a.patient_name}`, `
    <p class="small muted">The final bill is generated automatically: admission ₹1,000
      ${a.admission_type === 'EMERGENCY' ? '+ emergency ₹1,500 ' : ''}+ room × billable days (stay hours ÷ 24, rounded up)
      + nursing ₹500/day + doctor visits ₹400 each + logged medicines / treatments / services
      + completed surgeries.</p>
    <div class="field"><label>Discharge summary</label>
      <textarea class="textarea" id="dc-summary" placeholder="Condition at discharge, medications, review advice…"></textarea></div>
    <div class="field"><label>Discount (₹)</label>
      <input class="input" type="number" id="dc-discount" value="0" min="0"></div>`,
    `<button class="btn ghost" data-action="close-modal">Cancel</button>
     <button class="btn orange" id="dc-go">Discharge & generate bill</button>`);
  $('#dc-go').addEventListener('click', async () => {
    try {
      const res = await api(`/api/admissions/${a.id}/discharge`, { method: 'POST',
        body: { discharge_summary: $('#dc-summary').value.trim(), discount: +$('#dc-discount').value || 0 } });
      toast('Patient discharged — bill generated');
      closeModal();
      await V.admissionDetail(box, a.id);
      if (res.bill_id) V.billModal(res.bill_id);
    } catch (err) { toast(err.message, 'err'); }
  });
};

/* =========================================================  ROOMS ==== */
V.rooms = async box => {
  const list = await api('/api/rooms');
  const groups = {};
  list.forEach(r => (groups[r.room_type] = groups[r.room_type] || []).push(r));
  box.innerHTML = `
    <div class="flex between wrap mb"><h1>Room board</h1>
      ${V.isAdmin ? '<button class="btn" id="rm-new">＋ Add room</button>' : ''}</div>
    ${['ICU', 'VIP', 'DELUXE', 'ECONOMY'].filter(t => groups[t]).map(t => `
      <h3 class="mt">${t} <span class="muted small">· ${rupee(groups[t][0].daily_rate)}/day</span></h3>
      <div class="grid g4 roomgrid">${groups[t].map(r => `
        <div class="roomcard ${r.status === 'OCCUPIED' ? 'occ' : ''}">
          <div class="flex between"><span class="rn">${esc(r.room_number)}</span>${badge(r.status)}</div>
          ${r.status === 'OCCUPIED' ? `
            <div class="small mt"><b>${esc(r.occupant_name)}</b></div>
            <div class="tiny muted">since ${fmtDT(r.admitted_at)}</div>
            <div class="tiny muted">${esc(r.doctor_name || '')}</div>
            <button class="btn ghost sm mt" data-goadm="${r.admission_id}">Open admission</button>`
          : `<div class="tiny muted mt">Floor ${r.floor}${r.notes ? ` · ${esc(r.notes)}` : ''}</div>
             ${V.isAdmin && r.status !== 'OCCUPIED' ? `<button class="btn ghost sm mt" data-rmtoggle="${r.id}" data-cur="${r.status}">
               ${r.status === 'MAINTENANCE' ? 'Mark available' : 'Maintenance'}</button>` : ''}`}
        </div>`).join('')}</div>`).join('')}`;
  on(box, async e => {
    const g = e.target.closest('[data-goadm]');
    if (g) return location.hash = `admission-${g.dataset.goadm}`;
    const t = e.target.closest('[data-rmtoggle]');
    if (t) {
      const next = t.dataset.cur === 'MAINTENANCE' ? 'AVAILABLE' : 'MAINTENANCE';
      try { await api(`/api/rooms/${t.dataset.rmtoggle}`, { method: 'PATCH', body: { status: next } });
        toast(`Room marked ${next.toLowerCase()}`); V.rooms(box);
      } catch (err) { toast(err.message, 'err'); }
    }
    if (e.target.id === 'rm-new') V.roomForm(box);
  });
};

V.roomForm = box => {
  modal('Add a room', `
    <form id="rm-form" class="formgrid">
      <div class="field"><label>Room number</label><input class="input" name="room_number" required></div>
      <div class="field"><label>Type</label><select class="select" name="room_type" id="rm-type">
        <option value="ECONOMY">ECONOMY (₹1,500)</option><option value="DELUXE">DELUXE (₹3,000)</option>
        <option value="VIP">VIP (₹6,000)</option><option value="ICU">ICU (₹5,000)</option></select></div>
      <div class="field"><label>Daily rate (₹)</label><input class="input" type="number" name="daily_rate" value="1500" min="0"></div>
      <div class="field"><label>Floor</label><input class="input" type="number" name="floor" value="1" min="0"></div>
      <div class="field" style="grid-column:1/-1"><label>Notes</label><input class="input" name="notes"></div>
    </form>`,
    `<button class="btn ghost" data-action="close-modal">Cancel</button>
     <button class="btn" id="rm-save">Add room</button>`);
  const rates = { ECONOMY: 1500, DELUXE: 3000, VIP: 6000, ICU: 5000 };
  $('#rm-type').addEventListener('change', e =>
    $('#rm-form [name=daily_rate]').value = rates[e.target.value]);
  $('#rm-save').addEventListener('click', async () => {
    const body = formData($('#rm-form'));
    body.daily_rate = +body.daily_rate; body.floor = +body.floor;
    try { await api('/api/rooms', { method: 'POST', body });
      toast('Room added'); closeModal(); V.rooms(box);
    } catch (err) { toast(err.message, 'err'); }
  });
};

/* ======================================================  PHARMACY ==== */
V.pharmacy = async box => {
  box.innerHTML = `
    <div class="flex between wrap mb"><h1>Pharmacy</h1>
      ${V.isAdmin ? '<button class="btn" id="md-new">＋ Add medicine</button>' : ''}</div>
    <div class="tabbar">
      <button class="tab active" data-t="stock">Inventory</button>
      <button class="tab" data-t="pending">Pending prescriptions</button>
      <button class="tab" data-t="history">Stock audit</button></div>
    <div id="ph-body"><div class="loader"></div></div>`;
  const tabs = { stock: V.phStock, pending: V.phPending, history: V.phHistory };
  on(box, e => {
    const t = e.target.closest('.tab');
    if (t) { $$('.tab', box).forEach(x => x.classList.toggle('active', x === t)); tabs[t.dataset.t](); }
    if (e.target.id === 'md-new') V.medicineForm();
  });
  await V.phStock();
};

V.phStock = async () => {
  const meds = await api('/api/pharmacy/medicines');
  const low = meds.filter(m => m.low_stock);
  const root = document.createElement('div');
  root.innerHTML = `
    ${low.length ? `<div class="card mb" style="border-color:var(--orange);background:#FFF9F0">
      <b>⚠️ Low stock:</b> ${low.map(m => `<span class="chip">${esc(m.name)} — ${m.stock_quantity} left</span>`).join(' ')}</div>` : ''}
    ${V.table(['Medicine', 'Category', 'Unit price', 'Stock', 'Reorder at', ''],
      meds.map(m => `<tr>
        <td><b>${esc(m.name)}</b><div class="tiny muted">${esc(m.generic_name || '')} · ${esc(m.manufacturer || '')}</div></td>
        <td><span class="chip">${esc(m.category || '—')}</span></td>
        <td class="mono">${rupee(m.unit_price)}<div class="tiny muted">${esc(m.unit)}</div></td>
        <td class="mono"><b>${m.stock_quantity}</b> ${m.low_stock ? badge('LOW') : ''}</td>
        <td class="mono muted">${m.reorder_level}</td>
        <td class="right nowrap"><button class="btn ghost sm" data-stk="${m.id}" data-name="${esc(m.name)}">Stock ±</button>
          ${V.isAdmin ? `<button class="btn ghost sm" data-edit="${m.id}">Edit</button>` : ''}</td></tr>`))}`;
  root.addEventListener('click', e => {
    const s = e.target.closest('[data-stk]');
    if (s) V.stockModal(+s.dataset.stk, s.dataset.name);
    const ed = e.target.closest('[data-edit]');
    if (ed) V.medicineForm(meds.find(m => m.id === +ed.dataset.edit));
  });
  $('#ph-body').replaceChildren(root);
};

V.stockModal = (id, name) => {
  modal(`Adjust stock — ${name}`, `
    <div class="formgrid">
      <div class="field"><label>Movement</label><select class="select" id="st-type">
        <option value="IN">Stock IN (purchase)</option>
        <option value="OUT">Stock OUT (damage / expiry)</option>
        <option value="ADJUST">Set exact count (audit)</option></select></div>
      <div class="field"><label>Quantity</label><input class="input" type="number" id="st-qty" value="1" min="1"></div>
    </div>
    <div class="field"><label>Reference / note</label><input class="input" id="st-ref" placeholder="e.g. Invoice #4411"></div>`,
    `<button class="btn ghost" data-action="close-modal">Cancel</button>
     <button class="btn" id="st-save">Apply</button>`);
  $('#st-save').addEventListener('click', async () => {
    try {
      await api('/api/pharmacy/stock', { method: 'POST', body: {
        medicine_id: id, txn_type: $('#st-type').value,
        quantity: +$('#st-qty').value, reference: $('#st-ref').value.trim() } });
      toast('Stock updated'); closeModal(); V.phStock();
    } catch (err) { toast(err.message, 'err'); }
  });
};

V.medicineForm = (m = null) => {
  modal(m ? `Edit — ${m.name}` : 'Add medicine', `
    <form id="md-form" class="formgrid">
      <div class="field"><label>Name *</label><input class="input" name="name" value="${esc(m?.name || '')}" required></div>
      <div class="field"><label>Generic name</label><input class="input" name="generic_name" value="${esc(m?.generic_name || '')}"></div>
      <div class="field"><label>Category</label><input class="input" name="category" value="${esc(m?.category || '')}"></div>
      <div class="field"><label>Manufacturer</label><input class="input" name="manufacturer" value="${esc(m?.manufacturer || '')}"></div>
      <div class="field"><label>Unit</label><input class="input" name="unit" value="${esc(m?.unit || 'strip of 10')}"></div>
      <div class="field"><label>Unit price (₹) *</label><input class="input" type="number" name="unit_price" value="${m?.unit_price ?? ''}" min="0" required></div>
      ${m ? '' : `<div class="field"><label>Opening stock</label><input class="input" type="number" name="stock_quantity" value="0" min="0"></div>`}
      <div class="field"><label>Reorder level</label><input class="input" type="number" name="reorder_level" value="${m?.reorder_level ?? 10}" min="0"></div>
      <div class="field"><label>Batch no.</label><input class="input" name="batch_number" value="${esc(m?.batch_number || '')}"></div>
      <div class="field"><label>Expiry</label><input class="input" type="date" name="expiry_date" value="${m?.expiry_date || ''}"></div>
    </form>`,
    `<button class="btn ghost" data-action="close-modal">Cancel</button>
     <button class="btn" id="md-save">${m ? 'Save changes' : 'Add medicine'}</button>`);
  $('#md-save').addEventListener('click', async () => {
    const body = formData($('#md-form'));
    ['unit_price', 'stock_quantity', 'reorder_level'].forEach(k => body[k] !== undefined && (body[k] = +body[k]));
    try {
      await api(m ? `/api/pharmacy/medicines/${m.id}` : '/api/pharmacy/medicines',
        { method: m ? 'PATCH' : 'POST', body });
      toast(m ? 'Medicine updated' : 'Medicine added'); closeModal(); V.phStock();
    } catch (err) { toast(err.message, 'err'); }
  });
};

V.phPending = async () => {
  const list = await api('/api/pharmacy/prescriptions/pending');
  const root = document.createElement('div');
  root.innerHTML = list.length ? list.map(rx => `
    <div class="card mb"><div class="flex between wrap">
      <div><b>${esc(rx.patient_name)}</b> <span class="muted small">(${esc(rx.patient_code)}) · ${fmtDT(rx.created_at)}</span>
        ${rx.items.map(i => `<div class="small">💊 ${esc(i.medicine_name)} × ${i.quantity} <span class="tiny muted">${esc(i.dosage)}</span></div>`).join('')}
        ${rx.notes ? `<div class="tiny muted">${esc(rx.notes)}</div>` : ''}</div>
      <button class="btn" data-disp="${rx.id}">Dispense & bill</button></div></div>`).join('')
    : '<div class="card empty"><div class="big">✅</div>All prescriptions dispensed.</div>';
  root.addEventListener('click', async e => {
    const b = e.target.closest('[data-disp]');
    if (!b) return;
    b.disabled = true;
    try {
      const res = await api(`/api/pharmacy/prescriptions/${b.dataset.disp}/dispense`, { method: 'POST' });
      toast(`Dispensed — ${res.billed_items} item(s) billed`);
      V.phPending();
      if (res.bill_id) V.billModal(res.bill_id);
    } catch (err) { toast(err.message, 'err'); b.disabled = false; }
  });
  $('#ph-body').replaceChildren(root);
};

V.phHistory = async () => {
  const list = await api('/api/pharmacy/stock/history');
  const root = document.createElement('div');
  root.innerHTML = V.table(['When', 'Medicine', 'Movement', 'Qty', 'Balance', 'Reference'],
    list.map(t => `<tr><td class="nowrap">${fmtDT(t.created_at)}</td>
      <td>${esc(t.medicine_name)}</td>
      <td><span class="badge ${t.txn_type === 'IN' ? '' : t.txn_type === 'OUT' ? 'red' : 'gray'}">${esc(t.txn_type)}</span></td>
      <td class="mono">${t.txn_type === 'OUT' ? '−' : '+'}${t.quantity}</td>
      <td class="mono">${t.balance_after}</td><td class="small muted">${esc(t.reference || '—')}</td></tr>`),
    'No stock movements yet.');
  $('#ph-body').replaceChildren(root);
};

/* ========================================================  PHYSIO ==== */
V.physioList = async (el, patientId = null) => {
  const plans = await api(`/api/physio/plans${patientId ? `?patient_id=${patientId}` : ''}`);
  const root = document.createElement('div');
  root.innerHTML = `
    <div class="flex between wrap mb">${patientId ? '<h4>Physiotherapy plans</h4>' : '<h1>Physiotherapy</h1>'}
      <button class="btn" id="phy-new">＋ Prescribe plan</button></div>
    ${plans.length ? plans.map(p => `
      <div class="card mb"><div class="flex between wrap">
        <div><b>${esc(p.patient_name)}</b>
          <span class="muted small">· by ${esc(p.prescribed_by_name)} on ${fmtDate(p.prescribed_on)}</span>
          ${p.is_active ? badge('ACTIVE') : badge('DONE')}
          <div class="small mt"><b>${p.sessions_done}/${p.days_count}</b> sessions ·
            ${rupee(350)} per session</div>
          <div class="mt">${p.exercises.map(x => `<span class="chip">🏋️ ${esc(x)}</span>`).join('')}
            ${p.modalities.map(x => `<span class="chip">⚡ ${esc(x)}</span>`).join('')}
            ${p.traction.map(x => `<span class="chip">🪢 ${esc(x)}</span>`).join('')}</div>
          ${p.notes ? `<div class="tiny muted mt">${esc(p.notes)}</div>` : ''}</div>
        <div style="min-width:210px">
          ${p.is_active ? `<button class="btn sm" data-sess="${p.id}">＋ Record session</button>` : ''}
          <div class="small mt">${p.sessions.slice(0, 5).map(s =>
            `<div class="tiny">✅ ${fmtDate(s.session_date)} · ${esc(s.timing)} · ${rupee(s.amount)}</div>`).join('')}
            ${p.sessions.length > 5 ? `<div class="tiny muted">+${p.sessions.length - 5} more…</div>` : ''}</div>
        </div></div></div>`).join('')
      : '<div class="card empty"><div class="big">🤸</div>No physiotherapy plans yet.</div>'}`;
  root.addEventListener('click', e => {
    if (e.target.id === 'phy-new') V.physioForm(patientId, () => V.physioList(el, patientId));
    const s = e.target.closest('[data-sess]');
    if (s) V.sessionForm(+s.dataset.sess, () => V.physioList(el, patientId));
  });
  el.replaceChildren(root);
};

V.physio = box => V.physioList(box);

const PHYSIO_EX = ['Core Muscle Strengthening', 'Cervical Spine Strengthening', 'L.S. Spine Strengthening',
  'Knee Joint Strengthening (Right)', 'Knee Joint Strengthening (Left)', 'Knee Joint Strengthening (Both)',
  'Shoulder Joint Strengthening (Right)', 'Shoulder Joint Strengthening (Left)', 'Shoulder Joint Strengthening (Both)',
  'Shoulder Mobilization & Capsular Stretching (Right)', 'Shoulder Mobilization & Capsular Stretching (Left)',
  'Shoulder Mobilization & Capsular Stretching (Both)'];
const PHYSIO_MOD = ['SWD (Short Wave Diathermy)', 'IFT (Interferential Therapy)',
  'TENS (Transcutaneous Electrical Nerve Stimulation)', 'U.S. (Ultrasound Therapy)'];
const PHYSIO_TRAC = ['Lumbar Traction', 'Cervical Traction'];

V.physioForm = (patientId, done) => {
  const checks = (list, name) => list.map(x =>
    `<label class="check"><input type="checkbox" name="${name}" value="${esc(x)}"> ${esc(x)}</label>`).join('');
  modal('Prescribe physiotherapy', `
    <form id="phy-form">
      ${patientId ? `<input type="hidden" id="phy-pid" value="${patientId}">` : V.patientPicker('phy-pt')}
      <div class="field"><label>Number of days *</label>
        <input class="input" type="number" name="days_count" min="1" max="90" value="7" required></div>
      <h4>Exercises</h4>${checks(PHYSIO_EX, 'ex')}
      <h4 class="mt">Modalities</h4>${checks(PHYSIO_MOD, 'mod')}
      <h4 class="mt">Traction</h4>${checks(PHYSIO_TRAC, 'trac')}
      <div class="field mt"><label>Notes</label><textarea class="textarea" name="notes"></textarea></div>
    </form>`,
    `<button class="btn ghost" data-action="close-modal">Cancel</button>
     <button class="btn" id="phy-save">Prescribe</button>`);
  const getPid = patientId ? () => patientId : V.wirePatientPicker($('#modal-bd'), 'phy-pt');
  $('#phy-save').addEventListener('click', async () => {
    const f = $('#phy-form');
    const grab = n => $$(`[name=${n}]:checked`, f).map(i => i.value);
    const pid = getPid();
    if (!pid) return toast('Pick a patient.', 'warn');
    try {
      await api('/api/physio/plans', { method: 'POST', body: {
        patient_id: pid, days_count: +f.days_count.value,
        exercises: grab('ex'), modalities: grab('mod'), traction: grab('trac'),
        notes: f.notes.value.trim() } });
      toast('Plan prescribed'); closeModal(); done();
    } catch (err) { toast(err.message, 'err'); }
  });
};

V.sessionForm = (planId, done) => {
  modal('Record physiotherapy session', `
    <div class="formgrid">
      <div class="field"><label>Date</label><input class="input" type="date" id="ss-date" value="${todayISO()}"></div>
      <div class="field"><label>Timing</label><input class="input" id="ss-time" placeholder="e.g. 6:30 PM" required></div>
      <div class="field"><label>Amount (₹)</label><input class="input" type="number" id="ss-amt" value="350" min="0"></div>
    </div>
    <div class="field"><label>Notes</label><input class="input" id="ss-notes"></div>`,
    `<button class="btn ghost" data-action="close-modal">Cancel</button>
     <button class="btn" id="ss-save">Save session</button>`);
  $('#ss-save').addEventListener('click', async () => {
    try {
      await api('/api/physio/sessions', { method: 'POST', body: {
        plan_id: planId, session_date: $('#ss-date').value,
        timing: $('#ss-time').value.trim() || '—', amount: +$('#ss-amt').value || 0,
        notes: $('#ss-notes').value.trim() } });
      toast('Session recorded'); closeModal(); done();
    } catch (err) { toast(err.message, 'err'); }
  });
};

/* ============================================================  OT ==== */
V.ot = async box => {
  const [theatres, surgeries] = await Promise.all([
    api('/api/ot/theatres'), api('/api/ot/surgeries')]);
  box.innerHTML = `
    <div class="flex between wrap mb"><h1>Operation theatre</h1>
      ${V.isAdmin ? '<button class="btn" id="sx-new">＋ Schedule surgery</button>' : ''}</div>
    <div class="grid g2 mb">${theatres.map(t => `
      <div class="card"><div class="flex between"><h3>🏥 ${esc(t.name)}</h3>${badge(t.status)}</div>
        <div class="small muted">${esc(t.category)} theatre</div>
        <div class="mt">${t.equipment.split(';').map(x => `<span class="chip">${esc(x.trim())}</span>`).join('')}</div>
      </div>`).join('')}</div>
    <h3>Surgeries</h3>
    ${V.table(['Scheduled', 'Surgery', 'Patient', 'Surgeon', 'Theatre', 'Charges', 'Status', ''],
      surgeries.map(s => {
        const acts = [];
        if (s.status === 'SCHEDULED') {
          acts.push(`<button class="btn sm" data-sx="${s.id}" data-st="IN_PROGRESS">Start</button>`);
          acts.push(`<button class="btn danger sm" data-sx="${s.id}" data-st="CANCELLED">✕</button>`);
        }
        if (s.status === 'IN_PROGRESS')
          acts.push(`<button class="btn orange sm" data-sx="${s.id}" data-st="COMPLETED">Complete</button>`);
        return `<tr><td class="nowrap">${fmtDT(s.scheduled_at)}</td>
          <td><b>${esc(s.name)}</b>${s.equipment_used ? `<div class="tiny muted">${esc(s.equipment_used)}</div>` : ''}</td>
          <td>${esc(s.patient_name)}</td><td>${esc(s.surgeon_name)}</td>
          <td class="small">${esc(s.theatre_name)}</td><td class="mono">${rupee(s.charges)}</td>
          <td>${badge(s.status)}</td><td class="right nowrap">${acts.join(' ')}</td></tr>`;
      }), 'No surgeries scheduled.')}`;
  on(box, async e => {
    const b = e.target.closest('[data-sx]');
    if (b) {
      try {
        const res = await api(`/api/ot/surgeries/${b.dataset.sx}/status`,
          { method: 'PATCH', body: { status: b.dataset.st } });
        toast(`Surgery ${b.dataset.st.toLowerCase().replace('_', ' ')}`);
        V.ot(box);
        if (res.bill_id) V.billModal(res.bill_id);
      } catch (err) { toast(err.message, 'err'); }
    }
    if (e.target.id === 'sx-new') V.surgeryForm(theatres, box);
  });
};

V.surgeryForm = async (theatres, box) => {
  const admissions = await api('/api/admissions?status=ADMITTED');
  modal('Schedule a surgery', `
    <form id="sx-form">
      ${V.patientPicker('sx-pt')}
      <div class="formgrid">
        <div class="field"><label>Theatre</label><select class="select" name="theatre_id">
          ${theatres.map(t => `<option value="${t.id}">${esc(t.name)} — ${esc(t.category)}</option>`).join('')}</select></div>
        <div class="field"><label>Surgeon</label><select class="select" name="surgeon_id">${await V.doctorOptions()}</select></div>
        <div class="field"><label>Scheduled at</label><input class="input" type="datetime-local" name="scheduled_at" required></div>
        <div class="field"><label>Charges (blank = default: Major ₹15,000 / Minor ₹6,000)</label>
          <input class="input" type="number" name="charges" min="0" placeholder="auto"></div>
      </div>
      <div class="field"><label>Surgery name *</label><input class="input" name="name" required minlength="2"></div>
      <div class="field"><label>Link to active admission (optional — billed at discharge)</label>
        <select class="select" name="admission_id"><option value="">Standalone (own bill on completion)</option>
        ${admissions.map(a => `<option value="${a.id}">${esc(a.patient_name)} — ${esc(a.room_number)}</option>`).join('')}</select></div>
      <div class="field"><label>Equipment</label><input class="input" name="equipment_used" placeholder="C-arm; implant set…"></div>
      <div class="field"><label>Notes</label><input class="input" name="notes"></div>
    </form>`,
    `<button class="btn ghost" data-action="close-modal">Cancel</button>
     <button class="btn" id="sx-save">Schedule</button>`);
  const getPid = V.wirePatientPicker($('#modal-bd'), 'sx-pt');
  $('#sx-save').addEventListener('click', async () => {
    const body = formData($('#sx-form'));
    body.patient_id = getPid();
    if (!body.patient_id) return toast('Pick a patient.', 'warn');
    ['theatre_id', 'surgeon_id', 'admission_id', 'charges'].forEach(k => body[k] && (body[k] = +body[k]));
    try {
      await api('/api/ot/surgeries', { method: 'POST', body });
      toast('Surgery scheduled'); closeModal(); V.ot($('#view'));
    } catch (err) { toast(err.message, 'err'); }
  });
};

/* =========================================================  BILLS ==== */
V.billList = async (el, { patient_id = null } = {}) => {
  const root = document.createElement('div');
  const load = async status => {
    const q = new URLSearchParams();
    if (patient_id) q.set('patient_id', patient_id);
    if (status) q.set('status', status);
    const bills = await api(`/api/bills?${q}`);
    $('#bl-list', root).innerHTML = V.table(['Bill', 'Patient', 'Type', 'Date', 'Amount', 'Status', ''],
      bills.map(b => `<tr><td class="mono"><b>${esc(b.bill_number)}</b></td>
        <td>${esc(b.patient_name)}</td><td><span class="chip">${esc(b.bill_type)}</span></td>
        <td class="nowrap">${fmtDate(b.generated_at)}</td>
        <td class="mono"><b>${rupee(b.total)}</b></td><td>${badge(b.status)}</td>
        <td class="right"><button class="btn ghost sm" data-bill="${b.id}">View</button></td></tr>`),
      'No bills found.');
  };
  root.innerHTML = `
    ${patient_id ? '' : '<h1 class="mb">Billing</h1>'}
    <div class="tabbar"><button class="tab active" data-s="">All</button>
      <button class="tab" data-s="PENDING">Pending</button>
      <button class="tab" data-s="PAID">Paid</button></div>
    <div id="bl-list"><div class="loader"></div></div>`;
  root.addEventListener('click', e => {
    const t = e.target.closest('.tab');
    if (t) { $$('.tab', root).forEach(x => x.classList.toggle('active', x === t)); load(t.dataset.s); }
    const b = e.target.closest('[data-bill]');
    if (b) V.billModal(+b.dataset.bill, () => load(''));
  });
  el.replaceChildren(root);
  await load('');
};

V.bills = box => V.billList(box);

V.billModal = async (id, refresh = null) => {
  const b = await api(`/api/bills/${id}`);
  const canPay = b.status === 'PENDING';
  modal(`Bill ${b.bill_number}`, `
    <div class="flex between wrap">
      <div><b>${esc(b.patient_name)}</b> <span class="muted small">(${esc(b.patient_code)})</span>
        <div class="tiny muted">${esc(b.bill_type)} · generated ${fmtDT(b.generated_at)}</div></div>
      ${badge(b.status)}</div>
    <div class="divider"></div>
    <table class="table"><thead><tr><th>Item</th><th>Qty</th><th class="right">Rate</th><th class="right">Amount</th></tr></thead>
      <tbody>${b.items.map(i => `<tr><td>${esc(i.description)}
          <div class="tiny muted">${esc(i.category.replace('_', ' '))}</div></td>
        <td class="mono">${i.quantity}</td><td class="mono right">${rupee(i.unit_price)}</td>
        <td class="mono right">${rupee(i.amount)}</td></tr>`).join('')}</tbody></table>
    <div class="divider"></div>
    <div class="right small">Subtotal <b class="mono">${rupee(b.subtotal)}</b><br>
      ${b.discount ? `Discount <b class="mono">− ${rupee(b.discount)}</b><br>` : ''}
      <span style="font-size:19px">Total <b class="mono">${rupee(b.total)}</b></span><br>
      ${b.status === 'PAID' ? `<span class="tiny muted">Paid via ${esc(b.payment_mode)} · ${esc(b.transaction_ref || '')} · ${fmtDT(b.paid_at)}</span>` : ''}
    </div>
    ${b.notes ? `<div class="tiny muted">${esc(b.notes)}</div>` : ''}`,
    `<button class="btn ghost" data-action="print">🖨 Print</button>
     ${canPay ? `<button class="btn orange" id="bl-pay">Collect payment</button>` : ''}
     <button class="btn ghost" data-action="close-modal">Close</button>`);
  $('#bl-pay')?.addEventListener('click', () => V.payModal(b, refresh));
};

V.payModal = (b, refresh) => {
  /* Demo payment sheet — UPI (with QR) / card / netbanking / cash.
     Nothing real is charged; card & bank details never leave the browser. */
  const bd = modal(`Pay ${rupee(b.total)} — ${b.bill_number}`, `
    <div class="paytabs" id="pay-tabs">
      <button class="paytab active" data-pm="UPI">📱 UPI</button>
      <button class="paytab" data-pm="CARD">💳 Card</button>
      <button class="paytab" data-pm="NETBANKING">🏦 Netbanking</button>
      <button class="paytab" data-pm="CASH">💵 Cash</button>
    </div>
    <div id="pay-body"></div>
    <p class="tiny muted center" style="margin-top:12px">🔒 Demo payment — a transaction
      reference is generated and the bill is marked PAID. No money moves.</p>`,
    `<button class="btn ghost" data-action="close-modal">Cancel</button>
     <button class="btn orange" id="pay-go">Pay ${rupee(b.total)}</button>`);

  let mode = 'UPI';
  const qr = seed => {
    let h = 0; for (const c of seed) h = (h * 31 + c.charCodeAt(0)) >>> 0;
    const cells = [];
    for (let i = 0; i < 441; i++) {                     // 21×21 fake QR
      h = (h * 1103515245 + 12345) >>> 0;
      const r = Math.floor(i / 21), c = i % 21;
      const finder = (r < 7 && c < 7) || (r < 7 && c > 13) || (r > 13 && c < 7);
      const ring = finder && (r % 20 === 0 || c % 20 === 0 ||
        ((r % 20 === 6 || c % 20 === 6) && r < 7 === c < 7) ||
        (r > 1 && r < 5 && c > 1 && c < 5) || (r > 1 && r < 5 && c > 15 && c < 19) ||
        (r > 15 && r < 19 && c > 1 && c < 5));
      cells.push(`<i class="${finder ? (ring ? 'on' : '') : (h & 1024 ? 'on' : '')}"></i>`);
    }
    return `<div class="fakeqr" aria-hidden="true">${cells.join('')}</div>`;
  };

  const bodies = {
    UPI: () => `
      <div class="payupi">
        ${qr(b.bill_number)}
        <div>
          <div class="small"><b>Scan with any UPI app</b></div>
          <div class="tiny muted">GPay · PhonePe · Paytm · BHIM</div>
          <div class="tiny muted mt">payee: <span class="mono">palaskarhospital@upi</span></div>
          <div class="divider"></div>
          <div class="field"><label>…or enter your UPI ID</label>
            <input class="input" id="pay-upi" placeholder="name@bank" autocomplete="off"></div>
        </div>
      </div>`,
    CARD: () => `
      <div class="field"><label>Card number</label>
        <input class="input mono" id="pay-cardno" inputmode="numeric" maxlength="19"
               placeholder="4111 1111 1111 1111" autocomplete="off"></div>
      <div class="formgrid">
        <div class="field"><label>Expiry</label>
          <input class="input mono" id="pay-exp" maxlength="5" placeholder="MM/YY" autocomplete="off"></div>
        <div class="field"><label>CVV</label>
          <input class="input mono" id="pay-cvv" type="password" maxlength="3" placeholder="•••" autocomplete="off"></div>
      </div>
      <div class="field"><label>Name on card</label>
        <input class="input" id="pay-name" placeholder="As printed on the card"></div>`,
    NETBANKING: () => `
      <div class="field"><label>Choose your bank</label>
        <select class="select" id="pay-bank">
          <option>State Bank of India</option><option>HDFC Bank</option>
          <option>ICICI Bank</option><option>Axis Bank</option>
          <option>Bank of Baroda</option><option>Kotak Mahindra Bank</option>
          <option>Punjab National Bank</option><option>Union Bank of India</option>
        </select></div>
      <p class="small muted">You would normally be redirected to your bank's
        secure page — in this demo the payment is simulated instantly.</p>`,
    CASH: () => `
      <div class="card" style="background:var(--green-soft);border-color:var(--green)">
        <b>💵 Collect ${rupee(b.total)} at the front desk</b>
        <p class="small muted" style="margin:6px 0 0">Marking as paid records a
          cash receipt with a reference number for the day-book.</p></div>`,
  };
  const paint = () => { $('#pay-body').innerHTML = bodies[mode](); };
  paint();

  on($('#pay-tabs'), e => {
    const t = e.target.closest('.paytab');
    if (!t) return;
    mode = t.dataset.pm;
    $$('.paytab', bd).forEach(x => x.classList.toggle('active', x === t));
    paint();
  });

  /* light input affordances (demo only) */
  bd.addEventListener('input', e => {
    if (e.target.id === 'pay-cardno')
      e.target.value = e.target.value.replace(/\D/g, '').slice(0, 16)
        .replace(/(.{4})/g, '$1 ').trim();
    if (e.target.id === 'pay-exp')
      e.target.value = e.target.value.replace(/\D/g, '').slice(0, 4)
        .replace(/(..)(.)/, '$1/$2');
  });

  $('#pay-go').addEventListener('click', async () => {
    if (mode === 'UPI') {
      const v = $('#pay-upi').value.trim();
      if (v && !/^[\w.\-]{2,}@[a-z]{2,}$/i.test(v))
        return toast('That UPI ID doesn\'t look right (name@bank).', 'warn');
    }
    if (mode === 'CARD') {
      if ($('#pay-cardno').value.replace(/\s/g, '').length !== 16)
        return toast('Enter the 16-digit card number.', 'warn');
      if (!/^\d\d\/\d\d$/.test($('#pay-exp').value))
        return toast('Expiry as MM/YY.', 'warn');
      if ($('#pay-cvv').value.length !== 3)
        return toast('3-digit CVV.', 'warn');
    }
    const btn = $('#pay-go');
    btn.disabled = true;
    btn.innerHTML = '<span class="spin"></span> Processing…';
    await new Promise(r => setTimeout(r, 1100));        // demo gateway delay
    try {
      const res = await api(`/api/bills/${b.id}/pay`, { method: 'POST', body: {
        mode, upi_id: mode === 'UPI' ? ($('#pay-upi')?.value?.trim() || null) : null } });
      SFX.success();
      toast(`Payment received — ${res.transaction_ref}`);
      closeModal(); refresh?.(); V.billModal(b.id, refresh);
    } catch (err) {
      toast(err.message, 'err');
      btn.disabled = false; btn.textContent = `Pay ${rupee(b.total)}`;
    }
  });
};

/* =====================================================  REMINDERS ==== */
V.reminders = async box => {
  box.innerHTML = `
    <div class="flex between wrap mb"><h1>Reminders</h1>
      <button class="btn" id="rem-new">＋ New reminder</button></div>
    <div class="tabbar"><button class="tab active" data-s="PENDING">Pending</button>
      <button class="tab" data-s="">All</button></div>
    <div id="rem-list"><div class="loader"></div></div>`;
  const CATC = { EMERGENCY: 'red', ADMISSION: 'orange', DISCHARGE: 'blue',
    FOLLOW_UP: '', GENERAL: 'gray' };
  const load = async (status = 'PENDING') => {
    const list = await api(`/api/reminders${status ? `?status=${status}` : ''}`);
    $('#rem-list').innerHTML = list.length ? `<ul class="timeline">${list.map(r => `
      <li class="${CATC[r.category] ?? ''}">
        <div class="flex between wrap"><div>
          <b>${esc(r.title)}</b> <span class="badge ${CATC[r.category] ?? 'gray'}">${esc(r.category.replace('_', ' '))}</span>
          ${r.status === 'DONE' ? badge('DONE') : ''}
          <div class="small muted">${esc(r.message || '')}</div>
          <div class="tiny muted">Due ${fmtDT(r.due_at)}${r.patient_name ? ` · ${esc(r.patient_name)}` : ''}</div></div>
        ${r.status === 'PENDING' ? `<button class="btn ghost sm" data-done="${r.id}">✓ Done</button>` : ''}</div>
      </li>`).join('')}</ul>`
      : '<div class="card empty"><div class="big">🔔</div>Nothing pending — nice.</div>';
  };
  on(box, async e => {
    const t = e.target.closest('.tab');
    if (t) { $$('.tab', box).forEach(x => x.classList.toggle('active', x === t)); load(t.dataset.s); }
    const d = e.target.closest('[data-done]');
    if (d) {
      try { await api(`/api/reminders/${d.dataset.done}/done`, { method: 'PATCH' });
        toast('Marked done'); load('PENDING');
      } catch (err) { toast(err.message, 'err'); }
    }
    if (e.target.id === 'rem-new') V.reminderForm(() => load('PENDING'));
  });
  await load();
};

V.reminderForm = done => {
  const dt = new Date(Date.now() + 3600e3).toISOString().slice(0, 16);
  modal('New reminder', `
    <div class="field"><label>Title *</label><input class="input" id="rm2-title" required></div>
    <div class="field"><label>Message</label><input class="input" id="rm2-msg"></div>
    <div class="formgrid">
      <div class="field"><label>Category</label><select class="select" id="rm2-cat">
        <option>GENERAL</option><option>FOLLOW_UP</option><option>ADMISSION</option>
        <option>DISCHARGE</option><option>EMERGENCY</option></select></div>
      <div class="field"><label>Due at</label><input class="input" type="datetime-local" id="rm2-due" value="${dt}"></div>
    </div>`,
    `<button class="btn ghost" data-action="close-modal">Cancel</button>
     <button class="btn" id="rm2-save">Create</button>`);
  $('#rm2-save').addEventListener('click', async () => {
    try {
      await api('/api/reminders', { method: 'POST', body: {
        title: $('#rm2-title').value.trim(), message: $('#rm2-msg').value.trim(),
        category: $('#rm2-cat').value, due_at: $('#rm2-due').value } });
      toast('Reminder created'); closeModal(); done();
    } catch (err) { toast(err.message, 'err'); }
  });
};

/* ====================================================  ATTENDANCE ==== */
V.myAttendance = async box => {
  const me = V.me;
  const today = await api('/api/staff/attendance/today');
  box.innerHTML = `
    <h1 class="mb">My attendance</h1>
    <div class="card mb"><div class="flex between wrap">
      <div><h3>Today</h3>
        <div class="small">In: <b>${today?.check_in ? fmtTime(today.check_in) : '—'}</b> ·
          Out: <b>${today?.check_out ? fmtTime(today.check_out) : '—'}</b>
          ${today ? badge(today.status) : ''}</div></div>
      <div class="flex">
        <button class="btn" id="att-in" ${today?.check_in ? 'disabled' : ''}>✋ Check in</button>
        <button class="btn orange" id="att-out" ${!today?.check_in || today?.check_out ? 'disabled' : ''}>👋 Check out</button>
      </div></div></div>
    <div class="card"><h3>🗓 My calendar</h3><div id="att-map"><div class="loader"></div></div></div>`;
  const draw = async () => {
    const recs = await api(`/api/staff/${me.staff_id}/attendance/heatmap?days=366`);
    renderAttCalendar($('#att-map'), recs);
  };
  $('#att-in').addEventListener('click', async () => {
    try { await api('/api/staff/attendance/check-in', { method: 'POST' });
      SFX.success(); toast('Checked in — have a great shift!'); V.myAttendance(box);
    } catch (err) { toast(err.message, 'err'); }
  });
  $('#att-out').addEventListener('click', async () => {
    try { const r = await api('/api/staff/attendance/check-out', { method: 'POST' });
      toast(`Checked out — ${r.hours_worked} h today`); V.myAttendance(box);
    } catch (err) { toast(err.message, 'err'); }
  });
  await draw();
};
