# 🏥 Dr. Palaskar Hospital — ERP

A complete, self-contained hospital ERP for **Dr. Palaskar Hospital, Vasai-Virar**
(Accident • Orthopaedic • Ophthalmic Care — Reg. No. VVCMC/C-H-202/2014).

One `python run.py` gives you a public hospital website with guest appointment
booking, a patient portal, a staff desk and a super-admin console — backed by a
FastAPI + async SQLAlchemy backend with 76 API routes over 23 tables, and a
31-test pytest suite.

> **Demo software.** Payments are simulated (no gateway is called), and the
> seeded people, phone numbers and records are fictional.

---

## 1. Quick start

```bash
# Python 3.11+ recommended (built and tested on 3.12)
pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:8000** — the database is created and seeded with rich
demo data automatically on first start (file: `data/palaskar.db`).

| URL          | What it is                                   |
|--------------|----------------------------------------------|
| `/`          | Public hospital website + guest booking      |
| `/login`     | Sign-in for all roles                        |
| `/portal`    | Patient portal                               |
| `/staff`     | Staff desk                                   |
| `/admin`     | Super-admin console (the two doctors)        |
| `/api/docs`  | Interactive OpenAPI (Swagger) documentation  |

Reset to a fresh demo state at any time:

```bash
python scripts/reset_db.py
```

Run the test suite (uses its own throwaway database):

```bash
python -m pytest tests/
```

---

## 2. Demo credentials

| Role        | Username(s)                                              | Password        |
|-------------|----------------------------------------------------------|-----------------|
| SUPER_ADMIN | `sameer` (Dr. Sameer — Ortho), `lalan` (Dr. Lalan — Eye) | `Palaskar@2014` |
| STAFF       | `anita`, `kavita` (nurses) · `priya` (clerk) · `suresh` (pharmacist) · `rohan` (physio) · `meena` (intern) | `Staff@1234` |
| PATIENT     | `ramesh`, `sunita`, `vijay`                              | `Patient@1234`  |

Seeded world: 10 patients (P00001–P00010), ~250 consultations across the last
120 days with OPD bills and prescriptions, 25 medicines (2 deliberately at low
stock), 14 rooms (Economy/Deluxe/VIP/ICU), 2 operation theatres, 3 completed
in-patient stays with finalized mediclaims, **2 live admissions** (one ACL
post-op in E103, one emergency ICU case) ready for you to discharge, an ACL
surgery scheduled for tomorrow, appointments today/tomorrow, 120 days of staff
attendance and 3 months of paid payroll.

---

## 3. Feature tour by role

### 3.1 Guest (no login) — the public website `/`
* Hospital profile: the 14 treatment programmes (with per-programme detail
  modals), 15 facilities, physiotherapy services, consultant timings.
* **Book an appointment** — pick a doctor, **today or tomorrow only** (the
  hospital is closed on Sundays), choose a free 30-minute slot inside that
  doctor's OPD hours, leave name + 10-digit phone. You get a booking code
  (`APT-XXXXXX`) and a reminder to **arrive 30 minutes early** — bookings stay
  `BOOKED` until front-desk staff confirm them on the day.
* **Track an appointment** with code + phone.
* If the phone number matches an existing patient, the booking auto-links to
  their record.

### 3.2 Patient — `/portal`
* Home: next appointment, pending dues, visit count.
* Book (same today/tomorrow slot rules) and cancel own appointments.
* Full visit history with prescriptions (printable).
* Bills with itemised breakdowns and a **demo payment sheet** — UPI (with a
  scannable-style QR + VPA field), card, netbanking (bank picker) or cash,
  complete with a simulated processing step. A `TXN-…` reference is generated;
  nothing real is charged and card/bank details never leave the browser.
* Scans & reports uploaded by the hospital (X-ray/MRI/CT/lab…), opened inline.
* Physiotherapy plans and session history (read-only).
* Mediclaims with the frozen discharge summary once finalized.
* Patients can only ever see **their own** records — enforced server-side.

### 3.3 Staff — `/staff`
* Home: today's KPIs, one-tap **attendance check-in/out**, pending reminders.
* Appointments desk: confirm (same-day only), complete, no-show, cancel.
* Patient registry: register (optionally with portal login), search, full
  profile with visits, documents (upload), physio, bills, admissions.
* Admissions: admit into a free room (backdating allowed, never future),
  live **care timeline** (medication — deducts pharmacy stock —, doctor
  visits, vitals, meals, treatments, services), and **discharge** which
  auto-generates the final bill.
* Room board grouped by type with live occupancy.
* Pharmacy: inventory with low-stock alerts, stock IN/OUT/ADJUST with a full
  audit trail, **dispense pending prescriptions** (deducts stock, adds the
  medicine lines to the patient's OPD bill).
* Physiotherapy: prescribe plans from the printed catalogue (12 exercises,
  4 modalities, 2 traction types), record ₹350 sessions.
* Operation theatre: view theatres, move surgeries through
  `SCHEDULED → IN_PROGRESS → COMPLETED/CANCELLED`.
* Billing: view/collect any bill; reminders board; own attendance calendar
  (month view with check-in/out times and ‹ › navigation).
* Staff **cannot** see colleagues' KYC/salary, create staff, run payroll, or
  open the admin dashboard.

### 3.4 Super-admin — `/admin` (Dr. Sameer / Dr. Lalan)
Everything staff can do, plus:
* **Daily report dashboard**: KPI row (consultations, revenue collected /
  pending, **patients admitted right now** with today's in/out, staff
  presence), a **Recent activity feed** (admissions, discharges, staff
  check-ins/outs, payments, consultations, bookings, surgeries, new
  registrations — newest first), low stock — plus 5 live charts (30-day revenue line, consultations bar,
  department doughnut, top-dispensed medicines, room occupancy). Date picker
  re-renders the report for any past day. Printable.
* **New consultation** with a prescription builder (auto-fee: Sameer ₹600 /
  Lalan ₹500, overridable) — generates the OPD bill instantly.
* Mediclaim processing: edit insurer details, move
  `FINALIZED → SUBMITTED → APPROVED/REJECTED`.
* Staff & HR: full employee records **including KYC** (Aadhar, PAN, bank),
  add employees (login created automatically), per-employee attendance
  calendar and salary history.
* Payroll: month preview with days-present, **pay one** or **⚡ Autopay all**
  (skips anyone already paid), `PAY-…` references.
* Room and medicine catalogue management.

---

## 4. Architecture

```
erp/
├── run.py                     # uvicorn entrypoint (127.0.0.1:8000)
├── requirements.txt
├── pyproject.toml             # pytest config
├── scripts/reset_db.py        # wipe + reseed demo data
├── data/                      # SQLite db + uploaded documents (created at runtime)
├── tests/                     # 31 pytest tests (isolated tmp DB)
└── app/
    ├── main.py                # app factory, lifespan (init+seed), security headers
    ├── core/                  # config, database, security (JWT+bcrypt), deps
    ├── exceptions/            # AppError hierarchy + envelope handlers
    ├── models/                # 23 SQLAlchemy ORM models + enums
    ├── schemas/               # Pydantic v2 request/response models
    ├── repositories/          # query layer (no commits)
    ├── services/              # business rules — the ONLY layer that commits
    ├── routers/               # thin FastAPI routers (DI: get_db, roles)
    ├── utils/                 # ids, timeslots, seeder, catalog, files, rate_limit
    └── frontend/
        ├── templates/         # Jinja2: index, login, portal, staff, admin
        └── static/            # css/app.css, js/*, fonts, img, vendor/chart.umd.js
```

**Layering rule:** routers stay thin and never touch the session directly;
repositories only query; **all commits happen in services**, so every business
action is one transaction.

**Stack:** FastAPI · SQLAlchemy 2 (async) + aiosqlite · Pydantic v2 ·
python-jose (JWT HS256) · passlib[bcrypt] · Jinja2 · vanilla JS (no build
step) · Chart.js (vendored) · pytest + pytest-asyncio + httpx.
No Docker, no Node, no external services — SQLite is created in `data/`.

---

## 5. Database schema (23 tables)

| Area | Tables | Notes |
|------|--------|-------|
| Identity | `users` | one login per person; role = SUPER_ADMIN / STAFF / PATIENT |
| People | `staff`, `patients` | staff holds KYC + shift + salary; patients get `P0000N` codes |
| OPD | `appointments`, `consultations`, `prescriptions`, `prescription_items` | appointments carry guest name/phone when unregistered |
| Pharmacy | `medicines`, `stock_transactions` | every movement audited with balance-after |
| IPD | `rooms`, `admissions`, `care_logs` | room status is the single source of occupancy |
| OT | `operation_theatres`, `surgeries` | MAJOR ₹15,000 / MINOR ₹6,000 defaults |
| Physio | `physio_plans`, `physio_sessions` | plan stores the prescribed exercise/modality/traction lists |
| Money | `bills`, `bill_items` | types OPD / PHARMACY / IPD / SURGERY; items categorised |
| Insurance | `mediclaims` | DRAFT → FINALIZED (frozen JSON summary) → SUBMITTED → APPROVED/REJECTED |
| Ops | `reminders`, `patient_documents` | documents stored under `data/uploads/` with randomized names |
| HR | `attendance`, `salary_payments` | daily check-in/out; unique (staff, month, year) payment |

Key relationships: a consultation may spawn one prescription and one OPD bill;
an admission belongs to a room and accumulates care logs, ends with one IPD
bill and freezes its mediclaim; a surgery optionally links to an admission
(billed at discharge) or bills standalone on completion.

---

## 6. Billing — the exact discharge formula

At discharge, `stay_hours = ceil(now − admitted_at)` and
`billable_days = ceil(stay_hours / 24)` (so 25 hours = 2 days). The IPD bill
is assembled as:

```
  Admission & registration ............ ₹1,000 (flat)
+ Emergency / casualty care ........... ₹1,500 (only for EMERGENCY admissions)
+ Room .......... billable_days × room daily rate
+ Nursing care .. billable_days × ₹500
+ Doctor ward visits .. logged DOCTOR_VISIT count × ₹400
+ Medicines ..... Σ logged MEDICATION (qty × unit price, stock already deducted)
+ Treatments / services .. Σ logged charges
+ Operation theatre ..... Σ completed surgeries linked to this admission
− Discount (cannot exceed subtotal)
```

Standard tariff (seeded): consultation Sameer ₹600 / Lalan ₹500 · rooms
Economy ₹1,500 / Deluxe ₹3,000 / ICU ₹5,000 / VIP ₹6,000 per day · OT Major
₹15,000 / Minor ₹6,000 · physiotherapy ₹350 per session.

On discharge the room returns to `AVAILABLE`, a DISCHARGE reminder is raised,
and the admission's mediclaim is **FINALIZED** with a frozen JSON snapshot
(patient, stay, room, doctor, every bill line, totals, discharge summary) so
later catalogue/price changes can never alter a submitted claim.

---

## 7. API overview

76 routes under `/api` — explore them interactively at `/api/docs`. Highlights:

| Group | Examples |
|-------|----------|
| Auth | `POST /api/auth/login` (sets HttpOnly cookie **and** returns a bearer token), `/me`, `/change-password`, `/logout` |
| Public | `GET /api/public/info`, `/doctors`, `/slots?doctor_id&on`, `POST /appointments` (rate-limited), `GET /appointments/track` |
| Patients | CRUD + search, `POST /{id}/enable-login`, documents upload/download |
| Clinical | consultations (+prescription), physio plans/sessions |
| Pharmacy | medicines, `POST /stock`, `/stock/history`, pending prescriptions, `POST /{id}/dispense` |
| Wards | rooms board, admissions, care-logs, `POST /admissions/{id}/discharge` |
| OT | theatres, surgeries, `PATCH /surgeries/{id}/status` |
| Billing | bills, `POST /{id}/pay`, reminders, mediclaims |
| HR | staff CRUD, attendance check-in/out/heatmap, payroll preview/pay/autopay/history |
| Dashboard | `/daily-report?day=`, `/charts?days=`, `/staff-home` |

Cancelled / no-show appointments free their slot immediately — the row is
reused on rebooking, so a freed slot is genuinely bookable again.

The UI is fully responsive, phone-first: on iPhone/Android every data table
restyles into labelled stacked cards (no sideways scrolling), the sidebar
becomes a slide-in drawer with a dim scrim (tap outside or pick a page to
close, background scroll locks), modals are top-aligned and keyboard-safe
with full-width footer buttons, toasts sit centred above the home indicator,
and safe-area insets handle notches and rounded corners (`viewport-fit=cover`).
Landscape phones get a compact short-height layout; tablets keep two-column
grids with the drawer in portrait and the full sidebar in landscape. Inputs
are 16 px (no iOS auto-zoom), touch targets are ≥44 px on touchscreens, and
`100dvh` sizing avoids the mobile URL-bar jump. Static assets are
version-stamped (`?v=…`) so browsers pick up updates without a manual
hard-refresh.

Errors always use one envelope:
`{"error": {"code": "...", "message": "...", "details": {...}}}` with proper
status codes (401 unauthenticated, 403 forbidden, 404, **409 for state
conflicts** like a taken slot or occupied room, 422 for broken business rules,
429 rate-limited).

---

## 8. Security notes

* **Passwords** bcrypt-hashed; login is locked for 5 minutes after 5 failed
  attempts per username/IP.
* **JWT (HS256)** carried two ways: an `HttpOnly; SameSite=Strict` cookie for
  the built-in UI (JS never reads the token) and a `Bearer` header for API
  clients. The signing secret is generated once into `data/.secret_key`
  (override with `SECRET_KEY` env or `.env`).
* **RBAC** enforced in dependencies per route group; ownership checks ensure
  patients only reach their own rows. Staff see colleagues' KYC/salary
  **redacted**; only super-admins see them.
* **Headers/CSP**: strict `Content-Security-Policy` (self-only, no inline
  scripts/styles), `X-Frame-Options: DENY`, `nosniff`, `no-store` on API
  responses. All JS/fonts/charts are served locally — the app runs fully
  offline.
* **Uploads**: extension + size allow-list (png/jpg/jpeg/webp/pdf ≤ 10 MB),
  randomized stored names, traversal-safe paths, inline `Content-Disposition`
  with the original name only as a hint.
* **Rate limits**: guest booking 5/hour/IP, tracking 30/hour/IP
  (disable for load tests with `RATE_LIMIT_ENABLED=0`).
* Simulated payments never call any gateway; UPI IDs are echoed, not stored
  beyond the bill's reference field.

Configuration lives in `.env` (see `.env.example`): `DATABASE_URL`,
`SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `UPLOAD_DIR`, `SEED_ON_STARTUP`,
`RATE_LIMIT_ENABLED`.

---

## 9. Tests

`tests/` spins up the app against a throwaway SQLite in a temp dir (no seed,
rate limits off) and covers: auth + lockout-free login/logout/password change,
RBAC guards, the public info payload, slot generation + Sunday/window rules,
guest booking conflicts and tracking, patient CRUD + portal-login creation +
ownership isolation, document upload validation and inline download, default
vs explicit consultation fees, OPD billing, dispensing (stock deduction,
audit trail, insufficient stock, double dispense), stock adjust + low-stock
flag, admission guards (occupied room, double admission, future backdate),
**the exact discharge bill arithmetic line by line**, discount cap, room
release, frozen-mediclaim contents, claim status transitions, standalone
surgery billing + status rules, patient payment ownership + double payment,
reminders lifecycle, attendance check-in/out + heatmap, KYC redaction,
payroll pay/double-pay/autopay/history, and dashboard payload shapes.

```bash
python -m pytest tests/          # 35 passed
```

There is also a browser-level UI smoke suite that loads the real pages with
the real scripts (jsdom) against a running server and asserts sign-in flow,
redirects, that every shell renders without script errors or loops, that the
appointment actions fire exactly once, the full guest-booking submit succeeds
end-to-end, the demo netbanking payment completes, and the attendance
calendar renders with working month navigation:

```bash
python run.py                    # terminal 1
cd tests/ui && npm i && node smoke.mjs   # terminal 2 (needs Node 20+)
```

---

## 10. Small print & troubleshooting

* **Port in use** — edit `run.py` or `lsof -i :8000`.
* **Start fresh** — `python scripts/reset_db.py` (or delete `data/`).
* **Old styles on a phone?** Assets are version-stamped, but if you upgraded
  from a previous build do one hard refresh (pull-to-refresh twice on mobile,
  Ctrl+F5 on desktop) to clear the old cache.
* **Sunday** — booking is intentionally closed; slot lists show `closed: true`.
* Demo dates in the seed are generated **relative to today**, so charts and
  "today" views are always populated no matter when you run it.
* Logos: `logo2.png` is the original artwork; `logo1.png` (the ⊕ mark used on
  the splash screen) is a programmatic reconstruction of the hospital's mark.

Built with ❤️ for Dr. Palaskar Hospital — Sai Nagar, Vasai (W), Dist. Palghar
401202 · ☎ 0250-2380099 / 2380888 · Appointments 9545081608 / 8087381866 ·
palaskarhospital@gmail.com
