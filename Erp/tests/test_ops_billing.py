from datetime import datetime, timedelta

from tests.conftest import next_weekday


async def test_standalone_surgery_generates_own_bill(client, admin_h):
    r = await client.post("/api/ot/surgeries", headers=admin_h, json={
        "theatre_id": 2, "patient_id": 2, "surgeon_id": 2,
        "name": "Phaco cataract (right eye)",
        "scheduled_at": datetime.now().isoformat(timespec="seconds")})
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["charges"] == 6000                     # MINOR default

    # invalid jump SCHEDULED → COMPLETED
    bad = await client.patch(f"/api/ot/surgeries/{s['id']}/status",
                             headers=admin_h, json={"status": "COMPLETED"})
    assert bad.status_code == 422

    for st in ("IN_PROGRESS", "COMPLETED"):
        r = await client.patch(f"/api/ot/surgeries/{s['id']}/status",
                               headers=admin_h, json={"status": st})
        assert r.status_code == 200, r.text
    done = r.json()
    assert done["status"] == "COMPLETED" and done["bill_id"]

    bill = (await client.get(f"/api/bills/{done['bill_id']}",
                             headers=admin_h)).json()
    assert bill["bill_type"] == "SURGERY"
    assert bill["total"] == 6000
    # theatre is free again
    th = (await client.get("/api/ot/theatres", headers=admin_h)).json()
    assert next(t for t in th if t["id"] == 2)["status"] == "AVAILABLE"


async def test_patient_pays_own_bill_only(client, admin_h, patient_h,
                                          patient2_h):
    c = await client.post("/api/consultations", headers=admin_h, json={
        "patient_id": 1, "department": "ORTHOPAEDICS",
        "chief_complaint": "pain"})
    bills = (await client.get("/api/bills", headers=patient_h)).json()
    bill = next(b for b in bills if b["consultation_id"] == c.json()["id"])
    assert bill["status"] == "PENDING"

    deny = await client.post(f"/api/bills/{bill['id']}/pay",
                             headers=patient2_h,
                             json={"mode": "UPI", "upi_id": "x@upi"})
    assert deny.status_code == 403

    pay = await client.post(f"/api/bills/{bill['id']}/pay", headers=patient_h,
                            json={"mode": "UPI", "upi_id": "ramesh@upi"})
    assert pay.status_code == 200
    paid = pay.json()
    assert paid["status"] == "PAID"
    assert paid["transaction_ref"].startswith("TXN-")

    twice = await client.post(f"/api/bills/{bill['id']}/pay",
                              headers=patient_h, json={"mode": "UPI"})
    assert twice.status_code in (409, 422)


async def test_reminders_lifecycle(client, staff_h):
    due = (datetime.now() + timedelta(hours=2)).isoformat(timespec="seconds")
    r = await client.post("/api/reminders", headers=staff_h, json={
        "title": "Order Timolol", "message": "5 left", "category": "GENERAL",
        "due_at": due})
    assert r.status_code == 201
    rid = r.json()["id"]
    listed = (await client.get("/api/reminders?status=PENDING",
                               headers=staff_h)).json()
    assert any(x["id"] == rid for x in listed)
    done = await client.patch(f"/api/reminders/{rid}/done", headers=staff_h)
    assert done.json()["status"] == "DONE"


async def test_mediclaim_transition_rules(client, admin_h):
    r = await client.post("/api/admissions", headers=admin_h, json={
        "patient_id": 2, "room_id": 1, "primary_doctor_id": 1,
        "admission_type": "PLANNED", "reason": "obs"})
    adm = r.json()
    claim = (await client.get("/api/mediclaims?patient_id=2",
                              headers=admin_h)).json()[0]
    # DRAFT cannot jump to SUBMITTED
    bad = await client.patch(f"/api/mediclaims/{claim['id']}",
                             headers=admin_h, json={"status": "SUBMITTED"})
    assert bad.status_code == 422
    # details can still be edited in DRAFT
    ok = await client.patch(f"/api/mediclaims/{claim['id']}", headers=admin_h,
                            json={"insurer_name": "Star Health",
                                  "policy_number": "SH-1"})
    assert ok.json()["insurer_name"] == "Star Health"

    await client.post(f"/api/admissions/{adm['id']}/discharge",
                      headers=admin_h, json={"discharge_summary": "ok"})
    for st in ("SUBMITTED", "APPROVED"):
        r = await client.patch(f"/api/mediclaims/{claim['id']}",
                               headers=admin_h, json={"status": st})
        assert r.status_code == 200, r.text
    assert r.json()["status"] == "APPROVED"


async def test_appointment_status_rules(client, admin_h, patient_h,
                                        patient2_h):
    doc = 1
    on = next_weekday()
    slots = (await client.get(
        f"/api/public/slots?doctor_id={doc}&on={on}")).json()["slots"]
    free = [s["slot"] for s in slots if s["available"]]
    a = (await client.post("/api/appointments", headers=patient_h, json={
        "doctor_id": doc, "appointment_date": on, "slot": free[0]})).json()

    # another patient cannot touch it
    deny = await client.patch(f"/api/appointments/{a['id']}/status",
                              headers=patient2_h,
                              json={"status": "CANCELLED"})
    assert deny.status_code == 403
    # the owner cannot self-confirm
    deny2 = await client.patch(f"/api/appointments/{a['id']}/status",
                               headers=patient_h,
                               json={"status": "CONFIRMED"})
    assert deny2.status_code == 403

    # staff confirm works on the day itself; if the slot was booked for
    # tomorrow (today is Sunday) confirmation must be rejected instead.
    r = await client.patch(f"/api/appointments/{a['id']}/status",
                           headers=admin_h, json={"status": "CONFIRMED"})
    from datetime import date
    if on == date.today().isoformat():
        assert r.status_code == 200 and r.json()["confirmed_at"]
    else:
        assert r.status_code == 422

    # owner can cancel their own
    ok = await client.patch(f"/api/appointments/{a['id']}/status",
                            headers=patient_h, json={"status": "CANCELLED"})
    assert ok.status_code in (200, 422)  # 422 only if already CONFIRMED today


async def test_pay_via_netbanking(client, admin_h, patient_h):
    c = await client.post("/api/consultations", headers=admin_h, json={
        "patient_id": 1, "department": "ORTHOPAEDICS",
        "chief_complaint": "netbanking test", "fee": 250})
    bills = (await client.get("/api/bills", headers=patient_h)).json()
    bill = next(b for b in bills if b["consultation_id"] == c.json()["id"])
    r = await client.post(f"/api/bills/{bill['id']}/pay", headers=patient_h,
                          json={"mode": "NETBANKING"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "PAID"
    assert r.json()["payment_mode"] == "NETBANKING"
    assert r.json()["transaction_ref"].startswith("TXN-")
