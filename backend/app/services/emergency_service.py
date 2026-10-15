"""Receiving, accepting, rejecting and tracking emergencies."""
import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.errors import Conflict, Invalid, NotFound
from app.models import Emergency, Hospital, Patient, now
from app.services import ambulance_service, events, reservation_service
from app.services.reporting_service import client, log_inbound

# Allowed emergency status changes. Anything else is refused with 409.
FLOW = {
    "INCOMING": {"ACCEPTED", "REJECTED", "CANCELLED"},
    "ACCEPTED": {"ARRIVED", "CANCELLED"},
    "ARRIVED": {"ADMITTED"},
    "ADMITTED": {"UNDER_TREATMENT"},
    "UNDER_TREATMENT": {"DISCHARGED"},
    "REJECTED": set(), "DISCHARGED": set(), "CANCELLED": set(),
}


def set_status(db, emergency, new, actor="SYSTEM", source="HOSPITAL"):
    old = emergency.status
    if new not in FLOW.get(old, set()):
        raise Conflict("Invalid status change: %s -> %s." % (old, new), "INVALID_TRANSITION")
    emergency.status = new
    events.audit(db, emergency.hospital_id, "EMERGENCY_STATUS_CHANGED", emergency_id=emergency.emergency_id,
                 old_status=old, new_status=new, actor=actor, source=source)


def get_emergency(db, hospital_id, emergency_id):
    row = db.scalar(select(Emergency).where(Emergency.hospital_id == hospital_id,
                                            Emergency.emergency_id == emergency_id))
    if not row:
        raise NotFound("Emergency not found.")
    return row


def list_emergencies(db, hospital_id, status=None, limit=200):
    q = select(Emergency).where(Emergency.hospital_id == hospital_id)
    if status:
        q = q.where(Emergency.status == status)
    return db.scalars(q.order_by(Emergency.id.desc()).limit(limit)).all()


def _find_by_cr_id(db, hospital_id, cr_id):
    return db.scalar(select(Emergency).where(Emergency.hospital_id == hospital_id,
                                             Emergency.control_room_emergency_id == cr_id))


def _build(hospital, data):
    cr_id = data["control_room_emergency_id"].strip()
    amb_id = data.get("ambulance_id")
    inc_lat, inc_lng = data.get("incident_latitude"), data.get("incident_longitude")
    amb_lat, amb_lng = data.get("ambulance_latitude"), data.get("ambulance_longitude")
    route, simulated = data.get("route"), False
    hospital_pos = [hospital.latitude, hospital.longitude]

    if route:
        if len(route) < 2 or any(len(p) != 2 for p in route):
            raise Invalid("route must be a list of at least two [lat, lng] points.")
        if inc_lat is None or inc_lng is None:
            inc_lat, inc_lng = route[0]
        if amb_lat is None or amb_lng is None:
            amb_lat, amb_lng = route[0]
    else:
        if inc_lat is None or inc_lng is None:
            inc_lat, inc_lng = hospital.latitude + 0.018, hospital.longitude - 0.022  # demo default (~3 km)
        if amb_id and amb_lat is not None and amb_lng is not None:
            route = [[inc_lat, inc_lng], hospital_pos]  # real position known, straight line to hospital
        elif amb_id:
            route = ambulance_service.build_demo_route((inc_lat, inc_lng), tuple(hospital_pos))
            simulated = True
            amb_lat, amb_lng = route[0]
    length = ambulance_service.route_length_km(route) if route else None
    distance = data.get("distance_km")
    if distance is None and length:
        distance = round(length, 2)
    eta = data.get("eta_minutes")
    if eta is None and amb_id:
        eta = 8
    return Emergency(
        emergency_id=cr_id, control_room_emergency_id=cr_id, patient_id=data["patient_id"].strip(),
        patient_name=data.get("patient_name") or "Demo Patient",
        hospital_id=hospital.id, emergency_type=data["emergency_type"], severity=data["severity"],
        incident_location=data.get("incident_location"), incident_latitude=inc_lat, incident_longitude=inc_lng,
        ambulance_id=amb_id, ambulance_status=(data.get("ambulance_status") or "ASSIGNED") if amb_id else None,
        ambulance_latitude=amb_lat, ambulance_longitude=amb_lng,
        ambulance_updated_at=now() if amb_id else None,
        eta_minutes=eta, eta_initial_minutes=eta, distance_km=distance, distance_initial_km=distance,
        route_json=json.dumps(route) if route else None, route_index=0, is_simulated=simulated,
        required_treatment=data.get("required_treatment"), required_bed_type=data["required_bed_type"],
        status="INCOMING")


def receive_emergency(db, hospital_id, data, source="CONTROL_ROOM"):
    """Control Room -> Hospital. Returns (emergency, duplicate_flag)."""
    hospital = db.get(Hospital, hospital_id)
    cr_id = data["control_room_emergency_id"].strip()

    existing = _find_by_cr_id(db, hospital_id, cr_id)
    if existing is None:
        try:
            emergency = _build(hospital, data)
            db.add(emergency)
            db.flush()
        except IntegrityError:  # same emergency inserted by a parallel request
            db.rollback()
            existing = _find_by_cr_id(db, hospital_id, cr_id)
            if existing is None:
                raise
    if existing is not None:
        events.audit(db, hospital_id, "DUPLICATE_EMERGENCY_IGNORED", emergency_id=existing.emergency_id,
                     source=source)
        log_inbound(db, hospital_id, "DUPLICATE_EMERGENCY_REQUEST", existing.emergency_id, {}, source)
        db.commit()
        return existing, True

    events.audit(db, hospital_id, "EMERGENCY_RECEIVED", emergency_id=emergency.emergency_id, new_status="INCOMING",
                 actor="CONTROL_ROOM", source=source)
    log_inbound(db, hospital_id, "EMERGENCY_REQUEST", emergency.emergency_id,
                {"patient_id": emergency.patient_id, "required_bed_type": emergency.required_bed_type,
                 "severity": emergency.severity, "ambulance_id": emergency.ambulance_id}, source)
    client.send_emergency_status(db, hospital_id, emergency, "EMERGENCY_RECEIVED")
    events.alert(db, hospital_id, "NEW_EMERGENCY",
                 "New %s emergency %s (%s bed needed)." % (emergency.severity, emergency.emergency_id,
                                                         emergency.required_bed_type),
                 "critical" if emergency.severity == "CRITICAL" else "warning", emergency.emergency_id)
    if settings.AUTO_ACCEPT:
        _reserve_and_decide(db, emergency, actor="SYSTEM")
    db.commit()
    return emergency, False


def _reserve_and_decide(db, emergency, actor):
    """The core rule. Returns True if accepted, False if there was no suitable bed."""
    hospital_id = emergency.hospital_id
    if reservation_service.try_reserve(db, hospital_id, emergency.emergency_id, emergency.required_bed_type):
        set_status(db, emergency, "ACCEPTED", actor)
        db.add(Patient(patient_id=emergency.patient_id, control_room_patient_id=emergency.patient_id,
                       name=emergency.patient_name or "Demo Patient", emergency_id=emergency.emergency_id,
                       hospital_id=hospital_id, emergency_type=emergency.emergency_type,
                       severity=emergency.severity, bed_type=emergency.required_bed_type, status="INCOMING"))
        events.audit(db, hospital_id, "BED_RESERVED", emergency_id=emergency.emergency_id, actor=actor,
                     details={"bed_type": emergency.required_bed_type})
        client.send_emergency_status(db, hospital_id, emergency, "BED_RESERVED")
        client.send_emergency_status(db, hospital_id, emergency, "EMERGENCY_ACCEPTED")
        reservation_service.after_capacity_change(db, hospital_id)
        return True
    # No suitable bed: never confirm, never touch an earlier reservation.
    emergency.rejection_reason = "NO_SUITABLE_BED"
    set_status(db, emergency, "REJECTED", actor)
    events.audit(db, hospital_id, "EMERGENCY_REJECTED", emergency_id=emergency.emergency_id, actor=actor,
                 details={"reason": "NO_SUITABLE_BED", "bed_type": emergency.required_bed_type})
    events.alert(db, hospital_id, "RESERVATION_FAILURE",
                 "No suitable %s bed for %s. Control Room was told to redirect." % (emergency.required_bed_type,
                                                                                    emergency.emergency_id),
                 "critical", emergency.emergency_id)
    reason = {"reason": "NO_SUITABLE_BED", "bed_type": emergency.required_bed_type}
    client.send_emergency_status(db, hospital_id, emergency, "NO_SUITABLE_BED", reason)
    client.send_emergency_status(db, hospital_id, emergency, "EMERGENCY_REJECTED", reason)
    return False


def _patient_of(db, emergency):
    return db.scalar(select(Patient).where(Patient.hospital_id == emergency.hospital_id,
                                           Patient.emergency_id == emergency.emergency_id))


def accept_emergency(db, hospital_id, emergency_id, actor):
    emergency = get_emergency(db, hospital_id, emergency_id)
    if emergency.status != "INCOMING":
        raise Conflict("Only INCOMING emergencies can be accepted (current: %s)." % emergency.status,
                       "INVALID_TRANSITION")
    ok = _reserve_and_decide(db, emergency, actor)
    db.commit()
    if not ok:
        raise Conflict("No suitable %s bed is free right now. The emergency was NOT confirmed and "
                       "NO_SUITABLE_BED was reported to the Control Room." % emergency.required_bed_type,
                       "NO_SUITABLE_BED")
    return emergency


def reject_emergency(db, hospital_id, emergency_id, actor, reason=None):
    emergency = get_emergency(db, hospital_id, emergency_id)
    set_status(db, emergency, "REJECTED", actor)
    emergency.rejection_reason = (reason or "REJECTED_BY_HOSPITAL")[:200]
    events.audit(db, hospital_id, "EMERGENCY_REJECTED", emergency_id=emergency.emergency_id, actor=actor,
                 details={"reason": emergency.rejection_reason})
    client.send_emergency_status(db, hospital_id, emergency, "EMERGENCY_REJECTED",
                                 {"reason": emergency.rejection_reason})
    db.commit()
    return emergency


def cancel_emergency(db, hospital_id, emergency_id, actor, source="HOSPITAL"):
    """Valid workflow for releasing a protected reservation."""
    emergency = get_emergency(db, hospital_id, emergency_id)
    set_status(db, emergency, "CANCELLED", actor, source)
    if reservation_service.release_reservation(db, hospital_id, emergency.emergency_id):
        events.audit(db, hospital_id, "BED_RELEASED", emergency_id=emergency.emergency_id, actor=actor)
        reservation_service.after_capacity_change(db, hospital_id, check_warnings=False)
    client.send_emergency_status(db, hospital_id, emergency, "EMERGENCY_CANCELLED")
    db.commit()
    return emergency


def mark_patient_arrived(db, hospital_id, emergency_id, actor):
    emergency = get_emergency(db, hospital_id, emergency_id)
    if emergency.status != "ACCEPTED":
        raise Conflict("Patient can only arrive for an ACCEPTED emergency (current: %s)." % emergency.status,
                       "INVALID_TRANSITION")
    if emergency.ambulance_id and emergency.ambulance_status != "ARRIVED":
        raise Conflict("The ambulance has not arrived yet (status: %s)." % emergency.ambulance_status,
                       "AMBULANCE_NOT_ARRIVED")
    set_status(db, emergency, "ARRIVED", actor)
    patient = _patient_of(db, emergency)
    if patient:
        patient.status = "ARRIVED"
        patient.arrival_time = now()
        events.audit(db, hospital_id, "PATIENT_ARRIVED", emergency_id=emergency.emergency_id,
                     patient_id=patient.patient_id, old_status="INCOMING", new_status="ARRIVED", actor=actor)
        client.send_patient_status(db, hospital_id, patient, "PATIENT_ARRIVED")
    db.commit()
    return emergency


def update_ambulance(db, hospital_id, cr_emergency_id, data, source, actor):
    emergency = _find_by_cr_id(db, hospital_id, cr_emergency_id.strip())
    if not emergency:
        raise NotFound("Emergency not found.")
    ambulance_service.apply_update(db, emergency, data, source, actor)
    db.commit()
    return emergency
