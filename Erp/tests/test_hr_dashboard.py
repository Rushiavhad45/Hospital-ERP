from datetime import date


async def test_attendance_check_in_out(client, staff_h):
    r = await client.post("/api/staff/attendance/check-in", headers=staff_h)
    assert r.status_code == 200, r.text
    assert r.json()["check_in"]

    dup = await client.post("/api/staff/attendance/check-in", headers=staff_h)
    assert dup.status_code in (409, 422)

    out = await client.post("/api/staff/attendance/check-out", headers=staff_h)
    assert out.status_code == 200
    assert out.json()["check_out"]
    assert out.json()["status"] in ("PRESENT", "HALF_DAY")

    today = (await client.get("/api/staff/attendance/today",
                              headers=staff_h)).json()
    assert today and today["check_in"]

    hm = (await client.get("/api/staff/3/attendance/heatmap",
                           headers=staff_h)).json()
    assert any(x["day"] == date.today().isoformat() for x in hm)


async def test_staff_kyc_redacted_for_non_admin(client, staff_h, admin_h):
    mine = (await client.get("/api/staff", headers=staff_h)).json()
    sameer = next(s for s in mine if s["id"] == 1)
    assert sameer["aadhar_number"] in (None, "")           # hidden
    assert sameer["monthly_salary"] in (None, 0)

    full = next(s for s in (await client.get(
        "/api/staff", headers=admin_h)).json() if s["id"] == 1)
    assert full["aadhar_number"] == "111122223333"
    assert full["monthly_salary"] == 50000

    # staff cannot create employees
    deny = await client.post("/api/staff", headers=staff_h, json={})
    assert deny.status_code == 403


async def test_payroll_pay_double_pay_autopay(client, admin_h):
    month, year = date.today().month, date.today().year
    prev = (await client.get(
        f"/api/staff/payroll/preview?month={month}&year={year}",
        headers=admin_h)).json()
    assert all(p["paid"] is False for p in prev)

    r = await client.post("/api/staff/payroll/pay", headers=admin_h, json={
        "staff_id": 3, "month": month, "year": year, "mode": "MANUAL"})
    assert r.status_code == 200, r.text
    assert r.json()["reference"].startswith("PAY-")

    dup = await client.post("/api/staff/payroll/pay", headers=admin_h, json={
        "staff_id": 3, "month": month, "year": year, "mode": "MANUAL"})
    assert dup.status_code == 409

    auto = await client.post("/api/staff/payroll/autopay", headers=admin_h,
                             json={"month": month, "year": year})
    body = auto.json()
    assert len(body["skipped_already_paid"]) == 1          # the manual one
    assert body["total_paid"] == 3                         # remaining staff

    hist = (await client.get("/api/staff/payroll/history",
                             headers=admin_h)).json()
    assert len(hist) == 4


async def test_new_employee_can_login(client, admin_h):
    r = await client.post("/api/staff", headers=admin_h, json={
        "full_name": "Test Technician", "sex": "MALE",
        "date_of_birth": "1995-05-05", "designation": "TECHNICIAN",
        "qualification": "DMLT", "department": "LAB", "phone": "9111111111",
        "monthly_salary": 20000, "date_joined": date.today().isoformat(),
        "shift_start": "09:00", "shift_end": "17:00",
        "username": "techie", "password": "Techie@123"})
    assert r.status_code == 201, r.text
    login = await client.post("/api/auth/login", json={
        "username": "techie", "password": "Techie@123"})
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "STAFF"


async def test_daily_report_and_charts(client, admin_h):
    await client.post("/api/consultations", headers=admin_h, json={
        "patient_id": 1, "department": "ORTHOPAEDICS",
        "chief_complaint": "pain"})
    rep = (await client.get("/api/dashboard/daily-report",
                            headers=admin_h)).json()
    assert rep["consultations"]["count"] >= 1
    assert rep["consultations"]["revenue"] >= 600
    assert {"rooms", "revenue", "patients", "staff_attendance",
            "low_stock"} <= set(rep)
    assert rep["rooms"]["total"] == 2

    ch = (await client.get("/api/dashboard/charts?days=14",
                           headers=admin_h)).json()
    assert len(ch["labels"]) == 14
    assert len(ch["revenue"]) == 14 and len(ch["consultations"]) == 14

    home = (await client.get("/api/dashboard/staff-home",
                             headers=admin_h)).json()
    assert "appointments_today" in home and "rooms" in home


async def test_activity_feed(client, admin_h, staff_h):
    # generate a couple of events
    await client.post("/api/consultations", headers=admin_h, json={
        "patient_id": 1, "department": "ORTHOPAEDICS",
        "chief_complaint": "activity probe"})
    await client.post("/api/staff/attendance/check-in", headers=admin_h)

    r = await client.get("/api/dashboard/activity?limit=20", headers=admin_h)
    assert r.status_code == 200
    feed = r.json()
    assert feed, "feed should not be empty"
    assert {"at", "icon", "kind", "text"} <= set(feed[0])
    ats = [e["at"] for e in feed]
    assert ats == sorted(ats, reverse=True)          # newest first
    kinds = {e["kind"] for e in feed}
    assert "CONSULTATION" in kinds and "CHECK_IN" in kinds

    # admin-only
    assert (await client.get("/api/dashboard/activity",
                             headers=staff_h)).status_code == 403
