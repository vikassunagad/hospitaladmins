# 🏥 Hospital Module — Central Emergency Control Room (College Project)

The **Hospital Module** is the hospital-side part of a centralized emergency Control Room system for Vijayapura.
It receives emergency, patient and ambulance information **through the Control Room**, checks real-time bed capacity,
safely reserves beds, manages the patient workflow, lets the hospital **view** the incoming ambulance on a map, and
reports everything back to the Control Room.

> All hospitals, capacities, patients and ambulance movement in this project are **DEMO DATA / SIMULATED**.
> Nothing here is real hospital availability, real patient data or real GPS tracking.
> This is a workflow-management prototype, not a clinical system.

## 1. Problem statement
During an emergency the Control Room must choose a hospital quickly, but only the hospital knows its *real-time* free
beds. Two emergencies must never be promised the same last ICU bed. This module is the hospital's authoritative
capacity checker and bed-reservation system.

## 2. Responsibility of the Hospital Module
Does: receive emergencies · receive ambulance info · final real-time capacity check · reserve beds safely ·
accept/reject · manage patients · **view** ambulance movement · report to Control Room.

Does NOT: choose hospitals system-wide · calculate/control ambulance routes · talk to the Response Team.

## 3. Architecture & communication rule
```
              🎛️ CONTROL ROOM  (main project)
                     │  REST / JSON
                     ▼
   🏥 HOSPITAL MODULE:  FastAPI → services → SQLAlchemy → SQLite
                        + browser pages (HTML / CSS / vanilla JS / Leaflet map)
```
Hospital ⇄ Control Room only. Hospital → Response Team / other modules is **never** done. All outgoing messages go
through `ControlRoomClient` (`backend/app/services/reporting_service.py`).

## 4. Core bed-reservation rule
*Once an emergency bed is confirmed for an earlier incoming patient, that reservation is protected. Every new emergency
request re-checks real-time suitable-bed availability. If no suitable bed is available, the module does not confirm the
request and reports `NO_SUITABLE_BED` to the Control Room, which can redirect to another hospital.*

How it is enforced (`services/reservation_service.py`):
* One atomic SQL statement: `UPDATE bed_inventory SET reserved = reserved + 1 WHERE ... AND total - occupied - reserved >= 1`.
  If 0 rows change → no bed → emergency `REJECTED`, nothing reserved.
* Every database transaction starts with `BEGIN IMMEDIATE`, so simultaneous requests run one after another.
* Database CHECK constraints make `occupied + reserved > total` impossible.
* Duplicate emergency ids (`UNIQUE(hospital_id, control_room_emergency_id)`) never create a second reservation.
* Bed lifecycle: `FREE → RESERVED` (accepted) → `OCCUPIED` (admitted) → `FREE` (discharged). Cancel releases `RESERVED → FREE`.

## 5. Ambulance view
The hospital only **displays** data received from the Control Room: ambulance id, status
(`ASSIGNED → EN_ROUTE → NEAR_HOSPITAL → ARRIVED`), ETA, distance, position and route.
In mock mode a **DEMO / SIMULATED** ambulance moves along a predefined route. Buttons: START SIMULATION · PAUSE · RESET.
The map uses Leaflet + OpenStreetMap (needs internet for map tiles; offline you get a simple schematic map instead).

## 6. Setup on Windows (VS Code)
Needs **Python 3.10+** (check: `py --version`). Open the `hospital-module` folder in VS Code → Terminal → New Terminal.

**Easy way:** double-click `setup.bat` once, then `run.bat`.

**Manual way:**
```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
copy .env.example .env
cd backend
..\.venv\Scripts\python.exe seed.py
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```
Open **http://127.0.0.1:8000** · API docs **http://127.0.0.1:8000/docs**

Seed (safe to repeat, never duplicates): `..\.venv\Scripts\python.exe seed.py` · start from scratch: `seed.py --reset`.
(The app also seeds automatically when it starts.)

## 7. Demo logins (DEMO accounts, passwords are stored hashed)
Hospital usernames and passwords are configured individually as `HOSPITAL1_USERNAME` / `HOSPITAL1_PASSWORD`
through `HOSPITAL12_USERNAME` / `HOSPITAL12_PASSWORD` in `.env`. Each password should be unique. After changing
credentials, restart the app or run the seed script; existing demo accounts are synchronized from `.env`.

| Login | Hospital | Notes (DEMO capacity) |
|---|---|---|
| hospital1 | H001 Shifa Multi-specialty Hospital | ICU 5 total / 2 occupied / 0 reserved / 3 free (success demo) |
| hospital12 | H012 KOTI HOSPITAL | ICU 3 total / 2 occupied → **1 free** (failure demo) |
| hospital6, hospital9 | H006, H009 | ICU full (always NO_SUITABLE_BED for ICU) |
| hospital8 | H008 Kembhavi Eye Hospital | no ICU |

## 8. Settings (`.env`)
| Key | Meaning |
|---|---|
| `MOCK_CONTROL_ROOM=true` | no real Control Room needed; outgoing reports are stored locally |
| `AUTO_ACCEPT=true` | bed is reserved automatically when an emergency arrives; `false` = staff press Accept |
| `CONTROL_ROOM_BASE_URL`, `CONTROL_ROOM_API_KEY` | used for the real Control Room (key also protects inbound calls) |
| `HIGH_LOAD_THRESHOLD`, `CRITICAL_LOAD_THRESHOLD` | hospital status limits (80 / 90 %) |

## 9. Live demo script
**A. Success (login with the HOSPITAL1 credentials from `.env`)**
1. Dashboard → choose **ICU bed** → **Simulate Control Room request** → `EM-1024`, `P-501`, `AMB-07` arrives.
2. Bed is reserved automatically: ICU reserved 0 → 1, free 3 → 2. Emergency is `ACCEPTED`.
3. Open the emergency (**View**) → map shows incident 📍, hospital 🏥, route and 🚑.
4. Press **START SIMULATION**: the ambulance moves, ETA drops, `EN_ROUTE → NEAR_HOSPITAL → ARRIVED`.
5. Press **Patient arrived** → Patients page: **Admit** (RESERVED → OCCUPIED) → **Start treatment** → **Discharge** (OCCUPIED → FREE).
6. **Integration** page shows every IN/OUT message with the Control Room.

**B. Failure / no double booking (login with the HOSPITAL12 credentials from `.env`, ICU free = 1)**
1. Simulate an **ICU** request → accepted, ICU free = 0.
2. Simulate a second **ICU** request → `REJECTED`, reason `NO_SUITABLE_BED`; the first reservation is untouched.
3. Integration page shows `NO_SUITABLE_BED` sent to the Control Room; Alerts shows `RESERVATION FAILURE`.

## 10. API summary (see `/docs` for everything)
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/login`, `/api/auth/logout` · GET `/api/auth/me` | login / logout |
| GET | `/api/dashboard` | dashboard data |
| GET / PUT | `/api/capacity` | read / update capacity |
| GET | `/api/emergencies`, `/api/emergencies/{id}` | list / details |
| POST | `/api/emergencies/{id}/accept · reject · arrive · cancel` | workflow |
| GET | `/api/patients`, `/api/patients/{id}` | patients |
| POST | `/api/patients/{id}/admit · treatment · discharge` | patient flow |
| GET | `/api/alerts` · POST `/api/alerts/read-all` | alerts |
| GET | `/api/ambulances`, `/api/ambulances/{ambulance_id}` | read-only ambulance view |
| POST | `/api/integration/control-room/emergencies` | **Control Room → Hospital**: new emergency |
| POST | `/api/integration/control-room/ambulance-update` | **Control Room → Hospital**: ambulance status/position |
| POST | `/api/integration/control-room/cancel` | **Control Room → Hospital**: cancel |
| GET | `/api/integration/reports` | integration log |

Errors: 401 unauthorized · 403 not authorized · 404 not found · 409 conflict (no bed, duplicate state, invalid status change) · 422 invalid input · 500 unexpected (no stack trace shown).

**Hospital isolation:** the hospital id always comes from the login token, never from the browser.

### Control Room integration (real mode)
Set `MOCK_CONTROL_ROOM=false`, `CONTROL_ROOM_BASE_URL`, `CONTROL_ROOM_API_KEY`. The Control Room calls the
`/api/integration/control-room/...` endpoints with header `X-API-Key` and names the target `hospital_id` in the body.
Example:
```json
POST /api/integration/control-room/emergencies
{"hospital_id":"H001","control_room_emergency_id":"EM-1024","patient_id":"P-501","emergency_type":"Accident",
 "severity":"CRITICAL","ambulance_id":"AMB-07","ambulance_status":"EN_ROUTE","eta_minutes":8,"required_bed_type":"ICU"}
```
The response contains `result` (`ACCEPTED`, `REJECTED_NO_SUITABLE_BED`, `DUPLICATE`, ...). Optional `route`
(`[[lat,lng],...]`) and `ambulance_latitude/longitude` make the map show real data instead of the simulation.
Hospital → Control Room reports are POSTed to `{CONTROL_ROOM_BASE_URL}/api/hospital-events` with events:
`EMERGENCY_RECEIVED, BED_RESERVED, EMERGENCY_ACCEPTED, EMERGENCY_REJECTED, NO_SUITABLE_BED, AMBULANCE_ARRIVED,
PATIENT_ARRIVED, PATIENT_ADMITTED, PATIENT_UNDER_TREATMENT, PATIENT_DISCHARGED, CAPACITY_UPDATED,
HOSPITAL_STATUS_CHANGED`. (Change the path in `reporting_service.py` to match your Control Room team's API.)

## 11. Database (SQLite file `hospital.db` in the project folder)
`hospitals`, `hospital_users`, `bed_inventory`, `emergencies`, `patients`, `bed_reservations`, `alerts`,
`audit_logs`, `outbound_reports` (the integration log, IN and OUT). Primary/foreign keys, unique and CHECK constraints.

## 12. Folder structure
```
hospital-module/
├── backend/
│   ├── app/
│   │   ├── main.py  config.py  database.py  models.py  schemas.py  auth.py  dependencies.py  errors.py  seed_data.py
│   │   ├── services/  reservation_service · emergency_service · patient_service · ambulance_service
│   │   │              reporting_service (ControlRoomClient) · mock_control_room · events
│   │   ├── routers/   auth · dashboard · capacity · emergencies · patients · alerts · ambulances · integration
│   │   ├── templates/ login · dashboard · capacity · emergencies · emergency-details · patients
│   │   │              alerts · ambulance-tracking · profile · integration-log  (.html)
│   │   └── static/    css/style.css · js/*.js
│   ├── seed.py  requirements.txt  pytest.ini
│   └── tests/
├── .env  .env.example  .gitignore  setup.bat  run.bat  README.md
```

## 13. Testing
```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -v
```
Covers: login, password hashing, hospital isolation, duplicate emergencies, capacity formula, protected reservation,
no-bed rejection, concurrent reservations (8 threads, 1 bed), accept/reject, ambulance status rules, simulation,
admission/discharge bed changes, reporting and mock integration.

## 14. No AI dependency
The finished project is ordinary Python/JavaScript. It does not call ChatGPT, Claude, Gemini or any AI service.

## 15. Future scope
Real Control Room connection and retry queue for failed reports · real GPS feed · WebSockets instead of polling ·
PostgreSQL · role-based staff accounts (doctor, nurse) · bed-level (not just count) management · multi-language UI.
