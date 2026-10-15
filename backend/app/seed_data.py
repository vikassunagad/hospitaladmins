"""Demo data: 12 hospitals, 12 users, capacity, sample emergencies. DEMO DATA - not real hospital information.
Running it again never creates duplicates and never overwrites capacity you changed."""
import json
from datetime import timedelta

from sqlalchemy import select

from app.auth import hash_password, verify_password
from app.config import settings
from app.models import (Alert, BedInventory, BedReservation, Emergency, Hospital, HospitalUser, Patient, now)
from app.services import ambulance_service, reservation_service

# id, name, approx. demo latitude, approx. demo longitude (Vijayapura area, NOT surveyed locations)
HOSPITALS = [
    ("H001", "Shifa Multi-specialty Hospital", 16.8272, 75.7147),
    ("H002", "DR BIDARI'S ASHWINI HOSPITAL", 16.8195, 75.7068),
    ("H003", "Mulwad Multi-speciality Hospital", 16.8348, 75.7211),
    ("H004", "Dr.Gachinmahal Multi-Speciality Hospital", 16.8410, 75.7005),
    ("H005", "Anjutagi Hospital Vijayapur", 16.8226, 75.7302),
    ("H006", "Vasudev Hospital", 16.8487, 75.7149),
    ("H007", "Soukhyada Hospital, Vijayapura", 16.8130, 75.7192),
    ("H008", "Kembhavi Eye Hospital & Dental Care", 16.8302, 75.6961),
    ("H009", "Endigeri Hospital", 16.8379, 75.7352),
    ("H010", "Shri Amoghsiddheshwar Super Speciality Hospital", 16.8085, 75.7410),
    ("H011", "Bhagavati Hospital", 16.8451, 75.7262),
    ("H012", "KOTI HOSPITAL", 16.8243, 75.6905),
]

# DEMO capacity per hospital: (total, occupied) for GENERAL, ICU, EMERGENCY
CAPACITY = {
    "H001": ((40, 22), (5, 2), (8, 3)),    # ICU free = 3  (required success demo)
    "H002": ((30, 18), (4, 3), (6, 2)),
    "H003": ((50, 31), (8, 5), (10, 4)),
    "H004": ((35, 20), (6, 4), (5, 2)),
    "H005": ((20, 12), (2, 1), (4, 1)),
    "H006": ((25, 20), (3, 3), (4, 3)),    # ICU full
    "H007": ((28, 14), (4, 1), (5, 0)),
    "H008": ((20, 6), (0, 0), (2, 0)),     # eye hospital: no ICU
    "H009": ((22, 17), (2, 2), (3, 2)),    # ICU full
    "H010": ((120, 85), (20, 15), (25, 18)),
    "H011": ((30, 10), (5, 2), (6, 1)),
    "H012": ((18, 9), (3, 2), (4, 1)),     # ICU free = 1  (required failure demo)
}
BED_ORDER = ("GENERAL", "ICU", "EMERGENCY")


def _ago(minutes):
    return now() - timedelta(minutes=minutes)


def _seed_h001_samples(db):
    """Sample emergencies for H001 that match its capacity numbers (EM-1024 is left free for the live demo)."""
    if db.scalar(select(Emergency.id).where(Emergency.hospital_id == "H001", Emergency.emergency_id == "EM-1001")):
        return
    h = db.get(Hospital, "H001")

    def em(eid, pid, etype, sev, bed, status, minutes, **extra):
        e = Emergency(emergency_id=eid, control_room_emergency_id=eid, patient_id=pid, patient_name="Demo " + pid,
                      hospital_id="H001", emergency_type=etype, severity=sev, required_bed_type=bed, status=status,
                      incident_location="DEMO location, Vijayapura", received_at=_ago(minutes),
                      created_at=_ago(minutes), **extra)
        db.add(e)
        return e

    def patient(pid, eid, etype, sev, bed, status, minutes, bed_label=None, treatment=None):
        db.add(Patient(patient_id=pid, control_room_patient_id=pid, name="Demo " + pid, emergency_id=eid,
                       hospital_id="H001", emergency_type=etype, severity=sev, bed_type=bed, status=status,
                       arrival_time=_ago(minutes - 5), assigned_bed=bed_label, treatment_status=treatment,
                       created_at=_ago(minutes)))

    # EM-1001: already discharged (its bed is free again)
    em("EM-1001", "P-401", "Fall Injury", "MODERATE", "EMERGENCY", "DISCHARGED", 600)
    patient("P-401", "EM-1001", "Fall Injury", "MODERATE", "EMERGENCY", "DISCHARGED", 600, "EMERGENCY-01", "Completed")
    db.add(BedReservation(hospital_id="H001", emergency_id="EM-1001", bed_type="EMERGENCY", status="CONSUMED"))
    # EM-1002: under treatment in ICU (counted inside ICU occupied = 2)
    em("EM-1002", "P-402", "Cardiac Arrest", "CRITICAL", "ICU", "UNDER_TREATMENT", 240)
    patient("P-402", "EM-1002", "Cardiac Arrest", "CRITICAL", "ICU", "UNDER_TREATMENT", 240, "ICU-02", "On monitoring")
    db.add(BedReservation(hospital_id="H001", emergency_id="EM-1002", bed_type="ICU", status="CONSUMED"))
    # EM-1003: accepted, GENERAL bed reserved, ambulance on the way (simulation-ready)
    inc = (h.latitude + 0.016, h.longitude + 0.02)
    route = ambulance_service.build_demo_route(inc, (h.latitude, h.longitude))
    length = round(ambulance_service.route_length_km(route), 2)
    em("EM-1003", "P-403", "Fracture", "HIGH", "GENERAL", "ACCEPTED", 12,
       incident_latitude=inc[0], incident_longitude=inc[1], ambulance_id="AMB-03", ambulance_status="ASSIGNED",
       ambulance_latitude=route[0][0], ambulance_longitude=route[0][1], ambulance_updated_at=_ago(11),
       eta_minutes=9, eta_initial_minutes=9, distance_km=length, distance_initial_km=length,
       route_json=json.dumps(route), is_simulated=True, required_treatment="Orthopaedic care")
    patient("P-403", "EM-1003", "Fracture", "HIGH", "GENERAL", "INCOMING", 12)
    db.add(BedReservation(hospital_id="H001", emergency_id="EM-1003", bed_type="GENERAL", status="ACTIVE"))
    inv = db.scalar(select(BedInventory).where(BedInventory.hospital_id == "H001", BedInventory.bed_type == "GENERAL"))
    inv.reserved = 1
    db.add(Alert(hospital_id="H001", alert_type="NEW_EMERGENCY", severity="warning", emergency_id="EM-1003",
                 message="New HIGH emergency EM-1003 (GENERAL bed needed).", created_at=_ago(12)))


def seed_all(db):
    for hid, name, lat, lng in HOSPITALS:
        if not db.get(Hospital, hid):
            db.add(Hospital(id=hid, name=name, latitude=lat, longitude=lng))
    db.flush()
    for number, (hid, _name, _lat, _lng) in enumerate(HOSPITALS, start=1):
        username, password = settings.HOSPITAL_CREDENTIALS[number]
        user = db.scalar(select(HospitalUser).where(HospitalUser.hospital_id == hid))
        if user is None:
            db.add(HospitalUser(username=username, password_hash=hash_password(password), role="HOSPITAL_ADMIN",
                                hospital_id=hid, is_active=True))
        else:
            user.username = username
            if not verify_password(password, user.password_hash):
                user.password_hash = hash_password(password)
        for bed_type, (total, occupied) in zip(BED_ORDER, CAPACITY[hid]):
            if not db.scalar(select(BedInventory.id).where(BedInventory.hospital_id == hid,
                                                           BedInventory.bed_type == bed_type)):
                db.add(BedInventory(hospital_id=hid, bed_type=bed_type, total=total, occupied=occupied, reserved=0))
        if not db.scalar(select(Alert.id).where(Alert.hospital_id == hid, Alert.alert_type == "CONTROL_ROOM_MESSAGE")):
            db.add(Alert(hospital_id=hid, alert_type="CONTROL_ROOM_MESSAGE", severity="info",
                         message="DEMO DATA loaded. Capacity values are sample numbers, not real availability."))
    db.flush()
    _seed_h001_samples(db)
    db.flush()
    for hid, *_ in HOSPITALS:
        db.get(Hospital, hid).status = reservation_service.compute_status(
            reservation_service.capacity_summary(db, hid))
    db.commit()
