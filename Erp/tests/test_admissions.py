from datetime import datetime, timedelta


async def _admit(client, admin_h, *, room_id=2, adm_type="EMERGENCY",
                 hours_back=49.5, patient_id=1):
    admitted = (datetime.now() - timedelta(hours=hours_back)).isoformat(
        timespec="seconds")
    r = await client.post("/api/admissions", headers=admin_h, json={
        "patient_id": patient_id, "room_id": room_id, "primary_doctor_id": 1,
        "assigned_nurse_id": 3, "admission_type": adm_type,
        "reason": "RTA — observation", "diagnosis": "Fracture femur",
        "admitted_at": admitted})
    assert r.status_code == 201, r.text
    return r.json()


async def test_admission_guards(client, admin_h):
    a = await _admit(client, admin_h)               # ICU occupied now
    # same room again
    r = await client.post("/api/admissions", headers=admin_h, json={
        "patient_id": 2, "room_id": 2, "primary_doctor_id": 1,
        "admission_type": "PLANNED", "reason": "obs"})
    assert r.status_code == 409
    # same patient with an active stay
    r = await client.post("/api/admissions", headers=admin_h, json={
        "patient_id": 1, "room_id": 1, "primary_doctor_id": 1,
        "admission_type": "PLANNED", "reason": "obs"})
    assert r.status_code == 409
    # future backdate refused
    future = (datetime.now() + timedelta(hours=3)).isoformat(timespec="seconds")
    r = await client.post("/api/admissions", headers=admin_h, json={
        "patient_id": 2, "room_id": 1, "primary_doctor_id": 1,
        "admission_type": "PLANNED", "reason": "obs", "admitted_at": future})
    assert r.status_code == 422
    # room board shows occupancy + draft mediclaim exists
    rooms = (await client.get("/api/rooms", headers=admin_h)).json()
    icu = next(x for x in rooms if x["id"] == 2)
    assert icu["status"] == "OCCUPIED" and icu["occupant_patient_id"] == 1
    claims = (await client.get("/api/mediclaims?patient_id=1",
                               headers=admin_h)).json()
    assert claims[0]["status"] == "DRAFT"
    assert a["claim_number"] == claims[0]["claim_number"]


async def test_full_discharge_bill_math(client, admin_h, staff_h):
    """49.5 h ago → 50 h → 3 billable days; verify every line item."""
    a = await _admit(client, admin_h, hours_back=49.5)

    # care logs: one medication (2 × ₹100, deducts stock), one doctor visit,
    # one chargeable service, one vitals note (free)
    med_before = next(m for m in (await client.get(
        "/api/pharmacy/medicines", headers=staff_h)).json() if m["id"] == 1)
    for payload in (
        {"log_type": "MEDICATION", "description": "Diclofenac given",
         "medicine_id": 1, "quantity": 2},
        {"log_type": "DOCTOR_VISIT", "description": "Evening round",
         "doctor_id": 1},
        {"log_type": "SERVICE", "description": "Ambulance transfer",
         "charge": 750},
        {"log_type": "VITALS", "description": "BP 120/80"},
    ):
        r = await client.post("/api/care-logs", headers=staff_h,
                              json={"admission_id": a["id"], **payload})
        assert r.status_code == 201, r.text

    med_after = next(m for m in (await client.get(
        "/api/pharmacy/medicines", headers=staff_h)).json() if m["id"] == 1)
    assert med_after["stock_quantity"] == med_before["stock_quantity"] - 2

    r = await client.post(f"/api/admissions/{a['id']}/discharge",
                          headers=admin_h,
                          json={"discharge_summary": "Stable.",
                                "discount": 500})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "DISCHARGED" and out["bill_id"]

    bill = (await client.get(f"/api/bills/{out['bill_id']}",
                             headers=admin_h)).json()
    by_cat = {}
    for i in bill["items"]:
        by_cat[i["category"]] = by_cat.get(i["category"], 0) + i["amount"]

    assert by_cat["ADMISSION"] == 1000
    assert by_cat["EMERGENCY"] == 1500
    assert by_cat["ROOM"] == 3 * 5000            # ICU, 3 billable days
    assert by_cat["NURSING"] == 3 * 500
    assert by_cat["DOCTOR_VISIT"] == 400         # one logged visit
    assert by_cat["MEDICINE"] == 200
    assert by_cat["SERVICE"] == 750
    expected_subtotal = 1000 + 1500 + 15000 + 1500 + 400 + 200 + 750
    assert bill["subtotal"] == expected_subtotal
    assert bill["discount"] == 500
    assert bill["total"] == expected_subtotal - 500
    assert bill["bill_type"] == "IPD"

    # room freed
    rooms = (await client.get("/api/rooms", headers=admin_h)).json()
    assert next(x for x in rooms if x["id"] == 2)["status"] == "AVAILABLE"

    # mediclaim frozen with the same total
    claim = (await client.get("/api/mediclaims?patient_id=1",
                              headers=admin_h)).json()[0]
    assert claim["status"] == "FINALIZED"
    assert claim["summary"]["bill"]["total"] == bill["total"]
    assert claim["summary"]["admission"]["hours"] == 50

    # discharge reminder was raised
    rems = (await client.get("/api/reminders", headers=admin_h)).json()
    assert any(x["category"] == "DISCHARGE" and x["patient_id"] == 1
               for x in rems)

    # cannot discharge twice / log care on a closed stay
    again = await client.post(f"/api/admissions/{a['id']}/discharge",
                              headers=admin_h, json={"discharge_summary": ""})
    assert again.status_code in (409, 422)
    late = await client.post("/api/care-logs", headers=staff_h, json={
        "admission_id": a["id"], "log_type": "NOTE", "description": "late"})
    assert late.status_code in (409, 422)


async def test_discount_cannot_exceed_subtotal(client, admin_h):
    a = await _admit(client, admin_h, room_id=1, adm_type="PLANNED",
                     hours_back=2, patient_id=2)
    r = await client.post(f"/api/admissions/{a['id']}/discharge",
                          headers=admin_h,
                          json={"discharge_summary": "obs", "discount": 10**7})
    assert r.status_code == 422
