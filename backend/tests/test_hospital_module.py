from concurrent.futures import ThreadPoolExecutor

from app.database import SessionLocal
from app.models import HospitalUser
from app.seed_data import HOSPITALS
from app.services import emergency_service
from tests.conftest import KEY, capacity, emergency_body, login, send


# ---------- authentication & isolation ----------------------------------------------------------------------

def test_12_hospitals_and_logins(client, db):
    assert len(HOSPITALS) == 12
    for n in range(1, 13):
        r = client.post("/api/auth/login", json={"username": "hospital%d" % n, "password": "1234"})
        assert r.status_code == 200
        assert r.json()["hospital"]["id"] == "H%03d" % n


def test_passwords_are_hashed(client, db):
    user = db.query(HospitalUser).filter_by(username="hospital1").one()
    assert "1234" not in user.password_hash and user.password_hash.startswith("pbkdf2_sha256$")


def test_wrong_password_and_no_token(client):
    assert client.post("/api/auth/login", json={"username": "hospital1", "password": "bad"}).status_code == 401
    assert client.get("/api/dashboard").status_code == 401


def test_hospital_isolation(client):
    h1, h2 = login(client, "hospital1"), login(client, "hospital2")
    send(client, "H002", "EM-2001", "GENERAL")
    assert client.get("/api/emergencies/EM-2001", headers=h2).status_code == 200
    assert client.get("/api/emergencies/EM-2001", headers=h1).status_code == 404       # H001 cannot see H002 data
    assert client.post("/api/emergencies/EM-2001/reject", headers=h1).status_code == 404
    assert all(e["hospital_id"] == "H001" for e in client.get("/api/emergencies", headers=h1).json()["items"])
    # a hospital user cannot send integration messages on behalf of another hospital
    r = client.post("/api/integration/control-room/emergencies", headers=h1, json=emergency_body("EM-9", "ICU", "H002"))
    assert r.status_code == 403


# ---------- capacity -------------------------------------------------------------------------------------

def test_capacity_formula_and_demo_numbers(client):
    h1 = login(client)
    cap = capacity(client, h1)
    assert cap["ICU"] == {"total": 5, "occupied": 2, "reserved": 0, "free": 3}
    for bed in ("GENERAL", "ICU", "EMERGENCY"):
        c = cap[bed]
        assert c["free"] == c["total"] - c["occupied"] - c["reserved"] >= 0


def test_capacity_update_rules(client):
    h1 = login(client)
    ok = client.put("/api/capacity", headers=h1, json={"bed_type": "ICU", "total": 6, "occupied": 2})
    assert ok.status_code == 200 and ok.json()["capacity"]["ICU"]["free"] == 4
    bad = client.put("/api/capacity", headers=h1, json={"bed_type": "ICU", "total": 2, "occupied": 3})
    assert bad.status_code == 409
    assert client.put("/api/capacity", headers=h1, json={"bed_type": "ICU", "total": -1, "occupied": 0}).status_code == 422


def test_reserved_beds_cannot_be_edited_away(client):
    h1 = login(client)
    send(client)  # reserves 1 ICU
    r = client.put("/api/capacity", headers=h1, json={"bed_type": "ICU", "total": 3, "occupied": 3})
    assert r.status_code == 409


# ---------- emergencies: accept / reject / duplicate -----------------------------------------------------------

def test_success_scenario_reserves_bed(client):
    h1 = login(client)
    r = send(client)
    assert r.status_code == 200 and r.json()["result"] == "ACCEPTED"
    assert capacity(client, h1)["ICU"] == {"total": 5, "occupied": 2, "reserved": 1, "free": 2}
    events = [x["event"] for x in client.get("/api/integration/reports", headers=h1).json()["items"]]
    for name in ("EMERGENCY_REQUEST", "BED_RESERVED", "EMERGENCY_ACCEPTED"):
        assert name in events


def test_duplicate_emergency_no_second_reservation(client):
    h1 = login(client)
    send(client)
    again = send(client)
    assert again.json()["duplicate"] is True
    assert capacity(client, h1)["ICU"]["reserved"] == 1
    assert len([e for e in client.get("/api/emergencies", headers=h1).json()["items"]
                if e["emergency_id"] == "EM-1024"]) == 1


def test_no_bed_means_no_confirmation_and_protected_reservation(client):
    h12 = login(client, "hospital12")                      # ICU free = 1
    assert capacity(client, h12)["ICU"]["free"] == 1
    a = send(client, "H012", "EM-3001")
    assert a.json()["result"] == "ACCEPTED"
    b = send(client, "H012", "EM-3002")                    # arrives later: must NOT take A's bed
    assert b.json()["result"] == "REJECTED_NO_SUITABLE_BED"
    assert b.json()["emergency"]["status"] == "REJECTED"
    assert capacity(client, h12)["ICU"] == {"total": 3, "occupied": 2, "reserved": 1, "free": 0}
    a_now = client.get("/api/emergencies/EM-3001", headers=h12).json()
    assert a_now["emergency"]["status"] == "ACCEPTED" and a_now["reservation"] == "ACTIVE"
    events = [x["event"] for x in client.get("/api/integration/reports", headers=h12).json()["items"]
              if x["emergency_id"] == "EM-3002"]
    assert "NO_SUITABLE_BED" in events and "BED_RESERVED" not in events
    alerts = client.get("/api/alerts", headers=h12).json()["items"]
    assert any(a["alert_type"] == "RESERVATION_FAILURE" for a in alerts)


def test_concurrent_requests_never_double_book(client):
    h12 = login(client, "hospital12")                      # exactly 1 free ICU bed

    def attempt(i):
        with SessionLocal() as s:
            body = emergency_body("EM-77%02d" % i, "ICU")
            e, _dup = emergency_service.receive_emergency(s, "H012", body, "TEST")
            return e.status

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))
    assert results.count("ACCEPTED") == 1 and results.count("REJECTED") == 7
    assert capacity(client, h12)["ICU"] == {"total": 3, "occupied": 2, "reserved": 1, "free": 0}


def test_manual_accept_reject_mode(client):
    from app.config import settings
    settings.AUTO_ACCEPT = False
    try:
        h1 = login(client)
        assert send(client, eid="EM-4001").json()["result"] == "INCOMING"
        assert capacity(client, h1)["ICU"]["reserved"] == 0
        assert client.post("/api/emergencies/EM-4001/accept", headers=h1).status_code == 200
        assert capacity(client, h1)["ICU"]["reserved"] == 1
        send(client, eid="EM-4002")
        r = client.post("/api/emergencies/EM-4002/reject", headers=h1, json={"reason": "Staff shortage"})
        assert r.json()["emergency"]["status"] == "REJECTED"
        assert client.post("/api/emergencies/EM-4002/accept", headers=h1).status_code == 409
    finally:
        settings.AUTO_ACCEPT = True


def test_cancel_releases_reservation(client):
    h1 = login(client)
    send(client)
    assert client.post("/api/emergencies/EM-1024/cancel", headers=h1).status_code == 200
    assert capacity(client, h1)["ICU"]["reserved"] == 0


# ---------- ambulance ------------------------------------------------------------------------------------------

def test_ambulance_status_rules_and_arrival(client):
    h1 = login(client)
    send(client)
    upd = lambda **kw: client.post("/api/integration/control-room/ambulance-update", headers=KEY,
                                   json={"hospital_id": "H001", "control_room_emergency_id": "EM-1024", **kw})
    assert upd(ambulance_status="NEAR_HOSPITAL", eta_minutes=2).status_code == 200
    assert upd(ambulance_status="EN_ROUTE").status_code == 409                      # cannot go backwards
    assert client.post("/api/emergencies/EM-1024/arrive", headers=h1).status_code == 409   # ambulance not there yet
    assert upd(ambulance_status="ARRIVED").status_code == 200
    assert any(a["alert_type"] == "AMBULANCE_ARRIVED" for a in client.get("/api/alerts", headers=h1).json()["items"])
    assert client.post("/api/emergencies/EM-1024/arrive", headers=h1).status_code == 200


def test_simulation_reaches_hospital(client):
    h1 = login(client)
    send(client)
    last = None
    for _ in range(80):
        r = client.post("/api/integration/mock/emergencies/EM-1024/simulate/step", headers=h1)
        if r.status_code != 200:
            break
        last = r.json()
        if last["status"] == "ARRIVED":
            break
    assert last["status"] == "ARRIVED" and last["eta_minutes"] == 0 and last["progress_percent"] == 100
    assert last["position"] == last["hospital"]["position"]
    assert last["is_simulated"] is True


# ---------- patient lifecycle ----------------------------------------------------------------------------------

def test_full_patient_lifecycle_moves_beds_correctly(client):
    h1 = login(client)
    send(client)
    base = capacity(client, h1)["ICU"]                                     # occupied 2, reserved 1
    assert client.post("/api/patients/P-024/admit", headers=h1).status_code == 409   # not arrived yet
    client.post("/api/integration/control-room/ambulance-update", headers=KEY,
                json={"hospital_id": "H001", "control_room_emergency_id": "EM-1024", "ambulance_status": "ARRIVED"})
    assert client.post("/api/emergencies/EM-1024/arrive", headers=h1).status_code == 200
    assert capacity(client, h1)["ICU"]["reserved"] == base["reserved"]    # still protected after arrival
    assert client.post("/api/patients/P-024/admit", headers=h1).status_code == 200
    assert capacity(client, h1)["ICU"] == {"total": 5, "occupied": 3, "reserved": 0, "free": 2}   # RESERVED -> OCCUPIED
    assert client.post("/api/patients/P-024/discharge", headers=h1).status_code == 409        # must be treated first
    assert client.post("/api/patients/P-024/treatment", headers=h1, json={"treatment_status": "ICU care"}).status_code == 200
    assert client.post("/api/patients/P-024/discharge", headers=h1).status_code == 200
    assert capacity(client, h1)["ICU"] == {"total": 5, "occupied": 2, "reserved": 0, "free": 3}   # OCCUPIED -> FREE
    events = [x["event"] for x in client.get("/api/integration/reports", headers=h1).json()["items"]]
    for name in ("PATIENT_ARRIVED", "PATIENT_ADMITTED", "PATIENT_UNDER_TREATMENT", "PATIENT_DISCHARGED",
                 "CAPACITY_UPDATED"):
        assert name in events


def test_rejected_emergency_cannot_be_admitted(client):
    h12 = login(client, "hospital12")
    send(client, "H012", "EM-5001")
    send(client, "H012", "EM-5002")                                        # rejected
    assert client.post("/api/emergencies/EM-5002/arrive", headers=h12).status_code == 409
    assert client.post("/api/patients/P-002/admit", headers=h12).status_code == 404   # no patient record exists


# ---------- auth for integration ---------------------------------------------------------------------------------

def test_integration_requires_key_or_login(client):
    r = client.post("/api/integration/control-room/emergencies", json=emergency_body("EM-8", "ICU", "H001"))
    assert r.status_code == 401
    r = client.post("/api/integration/control-room/emergencies", headers={"X-API-Key": "wrong"},
                    json=emergency_body("EM-8", "ICU", "H001"))
    assert r.status_code == 401


def test_dashboard_and_hospital_status(client):
    h1 = login(client)
    d = client.get("/api/dashboard", headers=h1).json()
    assert d["hospital"]["id"] == "H001" and d["cards"]["free"] == d["capacity"]["TOTAL"]["free"]
    assert d["ambulance"]["emergency_id"] == "EM-1003"          # seeded simulation-ready ambulance
