/* Staff desk — entry point. Uses shared V.* views. */
'use strict';

(async () => {
  const me = await requireUser(['STAFF', 'SUPER_ADMIN']);
  if (!me) return;
  if (me.role === 'SUPER_ADMIN') { location.href = '/admin'; return; }
  V.me = me; V.isAdmin = false;

  buildShell({
    me, appName: 'Staff desk',
    navItems: [
      { id: 'home', icon: '🏠', label: 'Home' },
      { id: 'appointments', icon: '📅', label: 'Appointments' },
      { id: 'patients', icon: '🧑‍🤝‍🧑', label: 'Patients' },
      { id: 'admissions', icon: '🛏', label: 'Admissions' },
      { id: 'rooms', icon: '🚪', label: 'Rooms' },
      { id: 'pharmacy', icon: '💊', label: 'Pharmacy' },
      { id: 'physio', icon: '🤸', label: 'Physiotherapy' },
      { id: 'ot', icon: '🔪', label: 'Operation theatre' },
      { id: 'bills', icon: '🧾', label: 'Billing' },
      { id: 'reminders', icon: '🔔', label: 'Reminders' },
      { id: 'attendance', icon: '🗓', label: 'My attendance' },
    ],
  });

  const views = {
    home: staffHome,
    appointments: V.appointments,
    patients: V.patients,
    admissions: V.admissions,
    rooms: V.rooms,
    pharmacy: V.pharmacy,
    physio: V.physio,
    ot: V.ot,
    bills: V.bills,
    reminders: V.reminders,
    attendance: V.myAttendance,
  };

  /* dynamic routes: #patient-12, #admission-4 */
  const render = makeRouter(new Proxy(views, {
    get(t, k) {
      if (typeof k === 'string') {
        if (k.startsWith('patient-')) return box => V.patientDetail(box, +k.slice(8));
        if (k.startsWith('admission-')) return box => V.admissionDetail(box, +k.slice(10));
      }
      return t[k];
    },
    has: () => true,
  }), 'home');
  render();

  async function staffHome(box) {
    const s = await api('/api/dashboard/staff-home');
    const att = s.my_attendance;
    box.innerHTML = `
      <h1 class="mb">Today at the hospital</h1>
      <div class="grid g4 mb">
        <div class="card kpi b"><div class="v">${s.appointments_today}</div><div class="l">Appointments today</div>
          <div class="tiny muted">${s.appointments_waiting} awaiting confirmation</div></div>
        <div class="card kpi"><div class="v">${s.admitted_now}</div><div class="l">Patients admitted</div></div>
        <div class="card kpi o"><div class="v">${s.rooms.free}/${s.rooms.total}</div><div class="l">Rooms free</div></div>
        <div class="card kpi r"><div class="v">${s.low_stock_count}</div><div class="l">Low-stock medicines</div></div>
      </div>
      <div class="grid g2" style="align-items:start">
        <div class="card"><div class="flex between"><h3>✋ My shift</h3>
            ${att.checked_in ? badge('PRESENT') : '<span class="badge gray">NOT IN</span>'}</div>
          <p class="small">In: <b>${att.checked_in ? fmtTime(att.checked_in) : '—'}</b> ·
            Out: <b>${att.checked_out ? fmtTime(att.checked_out) : '—'}</b></p>
          <div class="flex">
            <button class="btn" id="hm-in" ${att.checked_in ? 'disabled' : ''}>Check in</button>
            <button class="btn orange" id="hm-out" ${!att.checked_in || att.checked_out ? 'disabled' : ''}>Check out</button>
          </div>
          <div class="divider"></div>
          <div class="small muted">Quick actions</div>
          <div class="flex wrap mt">
            <button class="btn ghost sm" data-view="patients">＋ Register patient</button>
            <button class="btn ghost sm" data-view="admissions">＋ Admit</button>
            <button class="btn ghost sm" data-view="pharmacy">Dispense Rx</button>
          </div>
        </div>
        <div class="card"><h3>🔔 Reminders</h3>
          ${s.reminders.length ? `<ul class="timeline">${s.reminders.map(r => `
            <li class="${r.category === 'EMERGENCY' ? 'red' : r.category === 'ADMISSION' ? 'orange' : ''}">
              <div class="small"><b>${esc(r.title)}</b></div>
              <div class="tiny muted">${fmtDT(r.due_at)} · ${esc(r.category.replace('_', ' '))}</div></li>`).join('')}
            </ul><button class="btn ghost sm" data-view="reminders">All reminders →</button>`
          : '<div class="empty">Nothing pending 🎉</div>'}
        </div>
      </div>`;
    $('#hm-in')?.addEventListener('click', async () => {
      try { await api('/api/staff/attendance/check-in', { method: 'POST' });
        SFX.success(); toast('Checked in — have a great shift!'); staffHome(box);
      } catch (err) { toast(err.message, 'err'); }
    });
    $('#hm-out')?.addEventListener('click', async () => {
      try { const r = await api('/api/staff/attendance/check-out', { method: 'POST' });
        toast(`Checked out — ${r.hours_worked} h today`); staffHome(box);
      } catch (err) { toast(err.message, 'err'); }
    });
  }
})();
