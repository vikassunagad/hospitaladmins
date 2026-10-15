import os
import tempfile

# Test settings must be set BEFORE the app is imported.
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "test.db").replace("\\", "/")
os.environ["CONTROL_ROOM_API_KEY"] = "test-key"
os.environ["MOCK_CONTROL_ROOM"] = "true"
os.environ["AUTO_ACCEPT"] = "true"
os.environ["PASSWORD_ITERATIONS"] = "1000"
for _number in range(1, 13):
    os.environ["HOSPITAL%d_USERNAME" % _number] = "hospital%d" % _number
    os.environ["HOSPITAL%d_PASSWORD" % _number] = "1234"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402,F401
from app.config import settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed_data import seed_all  # noqa: E402

KEY = {"X-API-Key": "test-key"}


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        seed_all(s)
    with SessionLocal() as s:
        yield s


@pytest.fixture()
def client(db):
    settings.AUTO_ACCEPT = True
    with TestClient(app) as c:
        yield c


def login(client, username="hospital1", password="1234"):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    client.cookies.clear()
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def emergency_body(eid="EM-1024", bed="ICU", hospital_id=None, **extra):
    body = {"control_room_emergency_id": eid, "patient_id": "P-" + eid[-3:], "patient_name": "Demo Patient",
            "emergency_type": "Accident", "severity": "CRITICAL", "ambulance_id": "AMB-07",
            "ambulance_status": "EN_ROUTE", "eta_minutes": 8, "required_bed_type": bed}
    if hospital_id:
        body["hospital_id"] = hospital_id
    body.update(extra)
    return body


def send(client, hospital_id="H001", eid="EM-1024", bed="ICU", **extra):
    return client.post("/api/integration/control-room/emergencies", headers=KEY,
                       json=emergency_body(eid, bed, hospital_id, **extra))


def capacity(client, headers):
    return client.get("/api/capacity", headers=headers).json()["capacity"]
