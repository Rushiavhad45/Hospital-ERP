import io


async def test_staff_creates_patient_and_duplicate_phone(client, staff_h):
    body = {"full_name": "Ganesh D. Patil", "sex": "MALE",
            "date_of_birth": "1955-11-08", "phone": "9890011999",
            "blood_group": "B-"}
    r = await client.post("/api/patients", headers=staff_h, json=body)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["patient_code"].startswith("P000")
    assert p["age"] >= 70
    assert p["has_login"] is False

    dup = await client.post("/api/patients", headers=staff_h, json=body)
    assert dup.status_code == 409


async def test_create_with_portal_login(client, staff_h):
    r = await client.post("/api/patients", headers=staff_h, json={
        "full_name": "New Portal User", "sex": "FEMALE",
        "date_of_birth": "1990-01-01", "phone": "9890012345",
        "create_login": True, "username": "newpat", "password": "Secret@123"})
    assert r.status_code == 201
    assert r.json()["has_login"] is True
    login = await client.post("/api/auth/login", json={
        "username": "newpat", "password": "Secret@123"})
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "PATIENT"


async def test_patient_ownership_isolation(client, patient_h, patient2_h):
    assert (await client.get("/api/patients/1",
                             headers=patient_h)).status_code == 200
    assert (await client.get("/api/patients/2",
                             headers=patient_h)).status_code == 403
    assert (await client.get("/api/patients/1",
                             headers=patient2_h)).status_code == 403
    # search endpoint is staff-only
    assert (await client.get("/api/patients?q=a",
                             headers=patient_h)).status_code == 403


async def test_document_upload_download_and_isolation(client, staff_h,
                                                      patient_h, patient2_h):
    png = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    files = {"file": ("xray.png", io.BytesIO(png), "image/png")}
    data = {"doc_type": "XRAY", "title": "Knee X-ray", "notes": "seed"}
    r = await client.post("/api/patients/1/documents", headers=staff_h,
                          files=files, data=data)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["doc_type"] == "XRAY"

    # a bad extension is rejected
    bad = await client.post(
        "/api/patients/1/documents", headers=staff_h,
        files={"file": ("evil.exe", io.BytesIO(b"MZ"), "application/x-dos")},
        data=data)
    assert bad.status_code == 422

    # owner can download inline; another patient cannot
    ok = await client.get(f"/api/documents/{doc['id']}/download",
                          headers=patient_h)
    assert ok.status_code == 200
    assert ok.headers["content-type"] == "image/png"
    assert "inline" in ok.headers.get("content-disposition", "")
    deny = await client.get(f"/api/documents/{doc['id']}/download",
                            headers=patient2_h)
    assert deny.status_code == 403
