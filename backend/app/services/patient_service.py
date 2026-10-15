"""Patient workflow: ARRIVED -> ADMITTED -> UNDER_TREATMENT -> DISCHARGED (and the bed changes that go with it)."""
from sqlalchemy import select

from app.errors import Conflict, NotFound
from app.models import Patient, now
from app.services import emergency_service, events, reservation_service
from app.services.reporting_service import client


def list_patients(db, hospital_id, status=None, limit=200):
    q = select(Patient).where(Patient.hospital_id == hospital_id)
    if status:
        q = q.where(Patient.status == status)
    return db.scalars(q.order_by(Patient.id.desc()).limit(limit)).all()


def get_patient(db, hospital_id, patient_id):
    """If the same patient id appears in several emergencies, the newest one is used."""
    row = db.scalar(select(Patient).where(Patient.hospital_id == hospital_id, Patient.patient_id == patient_id)
                    .order_by(Patient.id.desc()))
    if not row:
        raise NotFound("Patient not found.")
    return row


def _move(db, patient, emergency, new_status, actor):
    old = patient.status
    patient.status = new_status
    patient.updated_at = now()
    emergency_service.set_status(db, emergency, new_status, actor)
    events.audit(db, patient.hospital_id, "PATIENT_" + new_status, emergency_id=patient.emergency_id,
                 patient_id=patient.patient_id, old_status=old, new_status=new_status, actor=actor)


def admit(db, hospital_id, patient_id, actor):
    patient = get_patient(db, hospital_id, patient_id)
    if patient.status != "ARRIVED":
        raise Conflict("Only an ARRIVED patient can be admitted (current: %s)." % patient.status,
                       "INVALID_TRANSITION")
    emergency = emergency_service.get_emergency(db, hospital_id, patient.emergency_id)
    bed_type = reservation_service.consume_reservation(db, hospital_id, emergency.emergency_id)  # RESERVED -> OCCUPIED
    patient.assigned_bed = "%s-%02d" % (bed_type, reservation_service.occupied_count(db, hospital_id, bed_type))
    _move(db, patient, emergency, "ADMITTED", actor)
    client.send_patient_status(db, hospital_id, patient, "PATIENT_ADMITTED")
    reservation_service.after_capacity_change(db, hospital_id, check_warnings=False)
    db.commit()
    return patient


def start_treatment(db, hospital_id, patient_id, actor, treatment_status, notes=None):
    patient = get_patient(db, hospital_id, patient_id)
    if patient.status != "ADMITTED":
        raise Conflict("Only an ADMITTED patient can start treatment (current: %s)." % patient.status,
                       "INVALID_TRANSITION")
    emergency = emergency_service.get_emergency(db, hospital_id, patient.emergency_id)
    patient.treatment_status = treatment_status
    if notes:
        patient.notes = notes
    _move(db, patient, emergency, "UNDER_TREATMENT", actor)
    client.send_patient_status(db, hospital_id, patient, "PATIENT_UNDER_TREATMENT")
    db.commit()
    return patient


def discharge(db, hospital_id, patient_id, actor, notes=None):
    patient = get_patient(db, hospital_id, patient_id)
    if patient.status != "UNDER_TREATMENT":
        raise Conflict("Only a patient UNDER_TREATMENT can be discharged (current: %s)." % patient.status,
                       "INVALID_TRANSITION")
    emergency = emergency_service.get_emergency(db, hospital_id, patient.emergency_id)
    reservation_service.release_occupied(db, hospital_id, patient.bed_type)  # OCCUPIED -> FREE
    patient.treatment_status = "Completed"
    if notes:
        patient.notes = notes
    _move(db, patient, emergency, "DISCHARGED", actor)
    client.send_patient_status(db, hospital_id, patient, "PATIENT_DISCHARGED")
    reservation_service.after_capacity_change(db, hospital_id, check_warnings=False)
    db.commit()
    return patient
