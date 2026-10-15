from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.database import get_db
from app.dependencies import current_user
from app.models import AuditLog, BedReservation, Hospital
from app.schemas import RejectIn, audit_dict, emergency_dict, patient_dict
from app.services import ambulance_service, emergency_service

router = APIRouter(prefix="/api/emergencies", tags=["Emergencies"])


@router.get("")
def list_emergencies(status: str = None, user=Depends(current_user), db=Depends(get_db)):
    rows = emergency_service.list_emergencies(db, user.hospital_id, status)
    return {"items": [emergency_dict(r) for r in rows]}


@router.get("/{emergency_id}")
def emergency_detail(emergency_id: str, user=Depends(current_user), db=Depends(get_db)):
    e = emergency_service.get_emergency(db, user.hospital_id, emergency_id)  # scoped to the logged-in hospital
    patient = emergency_service._patient_of(db, e)
    reservation = db.scalar(select(BedReservation).where(BedReservation.hospital_id == user.hospital_id,
                                                         BedReservation.emergency_id == e.emergency_id))
    timeline = db.scalars(select(AuditLog).where(AuditLog.hospital_id == user.hospital_id,
                                                 AuditLog.emergency_id == e.emergency_id)
                          .order_by(AuditLog.id.desc()).limit(40)).all()
    hospital = db.get(Hospital, user.hospital_id)
    return {"emergency": emergency_dict(e), "patient": patient_dict(patient) if patient else None,
            "reservation": reservation.status if reservation else None,
            "ambulance": ambulance_service.tracking_view(e, hospital) if e.ambulance_id else None,
            "timeline": [audit_dict(a) for a in timeline]}


@router.post("/{emergency_id}/accept")
def accept(emergency_id: str, user=Depends(current_user), db=Depends(get_db)):
    e = emergency_service.accept_emergency(db, user.hospital_id, emergency_id, user.username)
    return {"result": "ACCEPTED", "emergency": emergency_dict(e)}


@router.post("/{emergency_id}/reject")
def reject(emergency_id: str, body: RejectIn = RejectIn(), user=Depends(current_user), db=Depends(get_db)):
    e = emergency_service.reject_emergency(db, user.hospital_id, emergency_id, user.username, body.reason)
    return {"result": "REJECTED", "emergency": emergency_dict(e)}


@router.post("/{emergency_id}/arrive")
def arrive(emergency_id: str, user=Depends(current_user), db=Depends(get_db)):
    e = emergency_service.mark_patient_arrived(db, user.hospital_id, emergency_id, user.username)
    return {"result": "ARRIVED", "emergency": emergency_dict(e)}


@router.post("/{emergency_id}/cancel")
def cancel(emergency_id: str, user=Depends(current_user), db=Depends(get_db)):
    e = emergency_service.cancel_emergency(db, user.hospital_id, emergency_id, user.username)
    return {"result": "CANCELLED", "emergency": emergency_dict(e)}
