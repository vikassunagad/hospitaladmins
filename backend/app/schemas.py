"""Request bodies (Pydantic) and helpers that turn database rows into JSON dictionaries."""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

BedType = Literal["GENERAL", "ICU", "EMERGENCY"]
Severity = Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
AmbulanceStatus = Literal["ASSIGNED", "EN_ROUTE", "NEAR_HOSPITAL", "ARRIVED"]


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=100)


class CapacityIn(BaseModel):
    bed_type: BedType
    total: int = Field(ge=0, le=5000)
    occupied: int = Field(ge=0, le=5000)


class EmergencyIn(BaseModel):
    hospital_id: Optional[str] = None  # only used by the real Control Room
    control_room_emergency_id: str = Field(min_length=1, max_length=40)
    patient_id: str = Field(min_length=1, max_length=40)
    patient_name: Optional[str] = Field(default="Demo Patient", max_length=100)
    emergency_type: str = Field(min_length=1, max_length=60)
    severity: Severity
    incident_location: Optional[str] = Field(default=None, max_length=200)
    incident_latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    incident_longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    ambulance_id: Optional[str] = Field(default=None, max_length=30)
    ambulance_status: AmbulanceStatus = "ASSIGNED"
    ambulance_latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    ambulance_longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    eta_minutes: Optional[int] = Field(default=None, ge=0, le=600)
    distance_km: Optional[float] = Field(default=None, ge=0)
    required_treatment: Optional[str] = Field(default=None, max_length=200)
    required_bed_type: BedType
    route: Optional[List[List[float]]] = None
    sent_at: Optional[str] = None


class AmbulanceUpdateIn(BaseModel):
    hospital_id: Optional[str] = None
    control_room_emergency_id: str = Field(min_length=1, max_length=40)
    ambulance_status: Optional[AmbulanceStatus] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    eta_minutes: Optional[int] = Field(default=None, ge=0, le=600)
    distance_km: Optional[float] = Field(default=None, ge=0)


class CancelIn(BaseModel):
    hospital_id: Optional[str] = None
    control_room_emergency_id: str = Field(min_length=1, max_length=40)


class RejectIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=200)


class TreatmentIn(BaseModel):
    treatment_status: str = Field(min_length=1, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=1000)


class DischargeIn(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=1000)


class SampleIn(BaseModel):
    bed_type: BedType = "ICU"
    severity: Severity = "CRITICAL"


def iso(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


def emergency_dict(e):
    return {
        "emergency_id": e.emergency_id, "control_room_emergency_id": e.control_room_emergency_id,
        "patient_id": e.patient_id, "patient_name": e.patient_name, "hospital_id": e.hospital_id,
        "emergency_type": e.emergency_type, "severity": e.severity, "incident_location": e.incident_location,
        "ambulance_id": e.ambulance_id, "ambulance_status": e.ambulance_status,
        "ambulance_latitude": e.ambulance_latitude, "ambulance_longitude": e.ambulance_longitude,
        "eta_minutes": e.eta_minutes, "distance_km": e.distance_km, "progress_percent": e.progress_percent(),
        "is_simulated": bool(e.is_simulated), "required_treatment": e.required_treatment,
        "required_bed_type": e.required_bed_type, "status": e.status, "rejection_reason": e.rejection_reason,
        "received_at": iso(e.received_at), "created_at": iso(e.created_at), "updated_at": iso(e.updated_at),
    }


def patient_dict(p):
    return {
        "patient_id": p.patient_id, "control_room_patient_id": p.control_room_patient_id, "name": p.name,
        "emergency_id": p.emergency_id, "hospital_id": p.hospital_id, "emergency_type": p.emergency_type,
        "severity": p.severity, "bed_type": p.bed_type, "arrival_time": iso(p.arrival_time),
        "assigned_bed": p.assigned_bed, "status": p.status, "treatment_status": p.treatment_status,
        "notes": p.notes, "created_at": iso(p.created_at), "updated_at": iso(p.updated_at),
    }


def alert_dict(a):
    return {"id": a.id, "alert_type": a.alert_type, "message": a.message, "severity": a.severity,
            "emergency_id": a.emergency_id, "is_read": a.is_read, "created_at": iso(a.created_at)}


def audit_dict(a):
    return {"event_id": a.id, "event_type": a.event_type, "emergency_id": a.emergency_id,
            "patient_id": a.patient_id, "old_status": a.old_status, "new_status": a.new_status,
            "actor": a.actor, "source": a.source, "details": a.details, "timestamp": iso(a.timestamp)}


def report_dict(r):
    return {"id": r.id, "time": iso(r.created_at), "direction": r.direction, "event": r.event,
            "emergency_id": r.emergency_id, "status": r.status, "payload": r.payload, "error": r.error}


def hospital_dict(h):
    return {"id": h.id, "name": h.name, "status": h.status, "latitude": h.latitude, "longitude": h.longitude}
