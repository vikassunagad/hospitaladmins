"""Mock Control Room: builds believable incoming requests so the module runs on its own."""
import re

from sqlalchemy import select

from app.models import Emergency

AMBULANCES = ["AMB-07", "AMB-03", "AMB-11", "AMB-05", "AMB-09"]
TYPES = {"ICU": ("Road Accident", "Cardiac Arrest", "Stroke"),
         "EMERGENCY": ("Burn Injury", "Fall Injury", "Poisoning"),
         "GENERAL": ("Fracture", "High Fever", "Dehydration")}


def sample_payload(db, hospital_id, bed_type="ICU", severity="CRITICAL"):
    ids = db.scalars(select(Emergency.emergency_id).where(Emergency.hospital_id == hospital_id)).all()
    numbers = [int(m.group(1)) for m in (re.fullmatch(r"EM-(\d+)", i) for i in ids) if m]
    n = max([1023] + [x for x in numbers if x >= 1023]) + 1
    k = n - 1024
    return {
        "control_room_emergency_id": "EM-%d" % n,
        "patient_id": "P-%d" % (501 + k),
        "patient_name": "Demo Patient %d" % (501 + k),
        "emergency_type": TYPES[bed_type][k % 3],
        "severity": severity,
        "incident_location": "Near Gol Gumbaz Road, Vijayapura (DEMO)",
        "ambulance_id": AMBULANCES[k % len(AMBULANCES)],
        "ambulance_status": "EN_ROUTE",
        "eta_minutes": 8,
        "required_treatment": "Critical care" if bed_type == "ICU" else "Emergency care",
        "required_bed_type": bed_type,
    }
