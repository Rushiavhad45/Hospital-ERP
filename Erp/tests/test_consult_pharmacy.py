async def _consult_with_rx(client, admin_h, patient_id=1, qty=2):
    r = await client.post("/api/consultations", headers=admin_h, json={
        "patient_id": patient_id, "department": "ORTHOPAEDICS",
        "chief_complaint": "Knee pain 3 weeks", "diagnosis": "Osteoarthritis",
        "treatments_given": "Joint Replacement — Consultation",
        "follow_up_on": None,
        "prescription_notes": "After food",
        "prescription_items": [{"medicine_id": 1, "dosage": "1-0-1",
                                "frequency": "BD", "duration_days": 5,
                                "quantity": qty}]})
    assert r.status_code == 201, r.text
    return r.json()


async def test_consultation_creates_opd_bill_with_default_fee(client, admin_h):
    c = await _consult_with_rx(client, admin_h)
    assert c["fee"] == 600                      # Dr. Sameer's standard fee
    assert c["prescription"]["dispensed"] is False

    bills = (await client.get("/api/bills?patient_id=1",
                              headers=admin_h)).json()
    opd = [b for b in bills if b["consultation_id"] == c["id"]]
    assert len(opd) == 1
    assert opd[0]["bill_type"] == "OPD"
    assert opd[0]["total"] == 600
    assert opd[0]["status"] == "PENDING"

    # follow-up reminder wasn't requested → none with FOLLOW_UP for this visit
    r = await client.post("/api/consultations", headers=admin_h, json={
        "patient_id": 1, "department": "ORTHOPAEDICS",
        "chief_complaint": "review", "fee": 350,
        "follow_up_on": None})
    assert r.json()["fee"] == 350               # explicit fee wins


async def test_lalan_default_fee(client, lalan_h):
    r = await client.post("/api/consultations", headers=lalan_h, json={
        "patient_id": 2, "department": "OPHTHALMOLOGY",
        "chief_complaint": "Blurred vision"})
    assert r.status_code == 201
    assert r.json()["fee"] == 500


async def test_dispense_deducts_stock_and_bills(client, admin_h, staff_h):
    before = next(m for m in (await client.get(
        "/api/pharmacy/medicines", headers=staff_h)).json() if m["id"] == 1)
    c = await _consult_with_rx(client, admin_h, qty=2)

    pending = (await client.get("/api/pharmacy/prescriptions/pending",
                                headers=staff_h)).json()
    rx = next(p for p in pending if p["consultation_id"] == c["id"])

    r = await client.post(f"/api/pharmacy/prescriptions/{rx['id']}/dispense",
                          headers=staff_h)
    assert r.status_code == 200, r.text
    assert r.json()["billed_items"] == 1

    after = next(m for m in (await client.get(
        "/api/pharmacy/medicines", headers=staff_h)).json() if m["id"] == 1)
    assert after["stock_quantity"] == before["stock_quantity"] - 2

    bill = (await client.get(f"/api/bills/{r.json()['bill_id']}",
                             headers=admin_h)).json()
    cats = [i["category"] for i in bill["items"]]
    assert "MEDICINE" in cats
    assert bill["total"] == 600 + 2 * 100       # consult + 2 × ₹100

    # audit trail recorded the OUT movement
    hist = (await client.get("/api/pharmacy/stock/history?medicine_id=1",
                             headers=staff_h)).json()
    assert hist[0]["txn_type"] == "OUT" and hist[0]["quantity"] == 2

    # double dispense is blocked
    again = await client.post(
        f"/api/pharmacy/prescriptions/{rx['id']}/dispense", headers=staff_h)
    assert again.status_code in (404, 409, 422)


async def test_insufficient_stock_blocks_dispense(client, admin_h, staff_h):
    c = await client.post("/api/consultations", headers=admin_h, json={
        "patient_id": 1, "department": "ORTHOPAEDICS",
        "chief_complaint": "post-op", "prescription_items": [
            {"medicine_id": 2, "dosage": "1", "frequency": "OD",
             "duration_days": 1, "quantity": 99}]})
    rx_id = c.json()["prescription"]["id"]
    r = await client.post(f"/api/pharmacy/prescriptions/{rx_id}/dispense",
                          headers=staff_h)
    assert r.status_code == 422
    assert "stock" in r.json()["error"]["message"].lower()
    # nothing was deducted
    m2 = next(m for m in (await client.get(
        "/api/pharmacy/medicines", headers=staff_h)).json() if m["id"] == 2)
    assert m2["stock_quantity"] == 3


async def test_stock_adjust_and_low_flag(client, staff_h):
    r = await client.post("/api/pharmacy/stock", headers=staff_h, json={
        "medicine_id": 2, "txn_type": "IN", "quantity": 20,
        "reference": "Invoice 88"})
    assert r.status_code == 200
    assert r.json()["stock_quantity"] == 23
    assert r.json()["low_stock"] is False

    out = await client.post("/api/pharmacy/stock", headers=staff_h, json={
        "medicine_id": 2, "txn_type": "OUT", "quantity": 21})
    assert out.json()["stock_quantity"] == 2
    assert out.json()["low_stock"] is True

    # OUT below zero is refused
    deny = await client.post("/api/pharmacy/stock", headers=staff_h, json={
        "medicine_id": 2, "txn_type": "OUT", "quantity": 500})
    assert deny.status_code == 422
