from datetime import date, timedelta

from tests.conftest import next_weekday


async def test_public_info_payload(client):
    r = await client.get("/api/public/info")
    assert r.status_code == 200
    info = r.json()
    assert info["hospital"]["registration_no"] == "VVCMC/C-H-202/2014"
    assert len(info["treatments"]) == 14
    assert len(info["facilities"]) == 15
    assert len(info["physiotherapy"]["exercises"]) == 12
    assert set(info["expert_consultation"]) == {"ORTHOPAEDICS", "OPHTHALMOLOGY"}


async def test_slots_shape_and_sunday(client):
    doctors = (await client.get("/api/public/doctors")).json()
    assert len(doctors) == 2
    doc = doctors[0]["id"]

    on = next_weekday()
    r = await client.get(f"/api/public/slots?doctor_id={doc}&on={on}")
    assert r.status_code == 200
    body = r.json()
    assert body["closed"] is False
    assert all({"slot", "available"} <= set(s) for s in body["slots"])

    # Sunday (if within the today/tomorrow window) is flagged closed;
    # otherwise requesting it is rejected as out of window.
    today = date.today()
    sunday = today + timedelta(days=(6 - today.weekday()) % 7)
    r = await client.get(f"/api/public/slots?doctor_id={doc}&on={sunday}")
    if sunday in (today, today + timedelta(days=1)):
        assert r.json()["closed"] is True
    else:
        assert r.status_code == 422

    # day after tomorrow is always out of window
    r = await client.get(
        f"/api/public/slots?doctor_id={doc}&on={today + timedelta(days=2)}")
    assert r.status_code == 422


async def test_guest_booking_conflict_and_track(client):
    doc = (await client.get("/api/public/doctors")).json()[0]["id"]
    on = next_weekday()
    slots = (await client.get(
        f"/api/public/slots?doctor_id={doc}&on={on}")).json()["slots"]
    free = [s["slot"] for s in slots if s["available"]]
    assert free, "test needs at least one open slot"
    slot = free[-1]

    payload = {"name": "Walkin Guest", "phone": "9812345678",
               "doctor_id": doc, "appointment_date": on, "slot": slot,
               "reason": "knee pain"}
    r = await client.post("/api/public/appointments", json=payload)
    assert r.status_code == 201, r.text
    appt = r.json()
    assert appt["code"].startswith("APT-")
    assert appt["status"] == "BOOKED"

    # same slot again → 409
    r2 = await client.post("/api/public/appointments",
                           json={**payload, "name": "Second Guest"})
    assert r2.status_code == 409

    # track with right and wrong phone
    ok = await client.get("/api/public/appointments/track",
                          params={"code": appt["code"], "phone": "9812345678"})
    assert ok.status_code == 200 and ok.json()["id"] == appt["id"]
    bad = await client.get("/api/public/appointments/track",
                           params={"code": appt["code"], "phone": "9800000000"})
    assert bad.status_code == 404


async def test_guest_booking_links_existing_patient(client, admin_h):
    """Booking with a phone we already know attaches the patient record."""
    doc = (await client.get("/api/public/doctors")).json()[0]["id"]
    on = next_weekday()
    slots = (await client.get(
        f"/api/public/slots?doctor_id={doc}&on={on}")).json()["slots"]
    slot = [s["slot"] for s in slots if s["available"]][0]
    r = await client.post("/api/public/appointments", json={
        "name": "Ramesh Sawant", "phone": "9890011001", "doctor_id": doc,
        "appointment_date": on, "slot": slot})
    assert r.status_code == 201
    assert r.json()["patient_id"] == 1


async def test_cancelled_slot_is_rebookable(client, admin_h, patient_h):
    """Regression: a CANCELLED row used to hold the (doctor, date, slot)
    unique key forever, so the slot showed as free but 409'd on rebooking."""
    doc = 1
    on = next_weekday()
    slots = (await client.get(
        f"/api/public/slots?doctor_id={doc}&on={on}")).json()["slots"]
    slot = [s["slot"] for s in slots if s["available"]][0]

    a = (await client.post("/api/appointments", headers=patient_h, json={
        "doctor_id": doc, "appointment_date": on, "slot": slot})).json()
    r = await client.patch(f"/api/appointments/{a['id']}/status",
                           headers=admin_h, json={"status": "CANCELLED"})
    assert r.status_code == 200

    # the slot must be free again…
    slots2 = (await client.get(
        f"/api/public/slots?doctor_id={doc}&on={on}")).json()["slots"]
    assert next(s for s in slots2 if s["slot"] == slot)["available"] is True

    # …and actually rebookable, by a guest this time
    r2 = await client.post("/api/public/appointments", json={
        "name": "Rebooker Guest", "phone": "9811100022",
        "doctor_id": doc, "appointment_date": on, "slot": slot})
    assert r2.status_code == 201, r2.text
    assert r2.json()["status"] == "BOOKED"
    assert r2.json()["code"] != a["code"]
