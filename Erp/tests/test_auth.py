from tests.conftest import PW


async def test_login_ok_and_me(client):
    r = await client.post("/api/auth/login",
                          json={"username": "sameer", "password": PW})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["role"] == "SUPER_ADMIN"
    assert "access_token" in body
    # cookie is also set for browser flows
    assert "access_token" in r.headers.get("set-cookie", "")

    me = await client.get("/api/auth/me", headers={
        "Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["username"] == "sameer"
    assert me.json()["staff_id"] is not None


async def test_login_wrong_password(client):
    r = await client.post("/api/auth/login",
                          json={"username": "sameer", "password": "nope-nope1"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_unauthenticated_rejected(client):
    r = await client.get("/api/patients")
    assert r.status_code == 401


async def test_role_guards(client, patient_h, staff_h):
    # patient cannot reach staff/admin surfaces
    for path in ("/api/staff", "/api/rooms", "/api/dashboard/daily-report",
                 "/api/pharmacy/medicines", "/api/reminders"):
        assert (await client.get(path, headers=patient_h)).status_code == 403

    # staff cannot reach admin-only surfaces
    r = await client.get("/api/dashboard/daily-report", headers=staff_h)
    assert r.status_code == 403
    r = await client.post("/api/consultations", headers=staff_h, json={
        "patient_id": 1, "department": "ORTHOPAEDICS",
        "chief_complaint": "knee pain"})
    assert r.status_code == 403


async def test_change_password_flow(client, patient_h):
    bad = await client.post("/api/auth/change-password", headers=patient_h,
                            json={"current_password": "wrong-wrong1",
                                  "new_password": "Fresh@12345"})
    assert bad.status_code == 401
    ok = await client.post("/api/auth/change-password", headers=patient_h,
                           json={"current_password": PW,
                                 "new_password": "Fresh@12345"})
    assert ok.status_code == 200
    relog = await client.post("/api/auth/login", json={
        "username": "pat1", "password": "Fresh@12345"})
    assert relog.status_code == 200


async def test_cookie_only_browser_flow(client):
    """The UI never stores tokens in JS — the httpOnly cookie must carry
    the whole session (regression for the /login redirect loop)."""
    # signed-out probe: plain 401, no redirect side effects
    r = await client.get("/api/auth/me")
    assert r.status_code == 401

    r = await client.post("/api/auth/login",
                          json={"username": "sameer", "password": PW})
    assert r.status_code == 200
    assert "httponly" in r.headers.get("set-cookie", "").lower()

    # httpx keeps the cookie jar — no Authorization header from here on
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "sameer"

    bills = await client.get("/api/bills")
    assert bills.status_code == 200

    out = await client.post("/api/auth/logout")
    assert out.status_code == 200
    after = await client.get("/api/auth/me")
    assert after.status_code == 401
