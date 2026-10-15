from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.database import get_db
from app.dependencies import current_user
from app.errors import NotFound
from app.models import Emergency, Hospital
from app.services import ambulance_service

router = APIRouter(prefix="/api/ambulances", tags=["Ambulance (view only)"])


@router.get("")
def list_ambulances(user=Depends(current_user), db=Depends(get_db)):
    rows = db.scalars(select(Emergency).where(
        Emergency.hospital_id == user.hospital_id, Emergency.ambulance_id.is_not(None),
        Emergency.status.in_(("INCOMING", "ACCEPTED", "ARRIVED"))).order_by(Emergency.id.desc()).limit(30)).all()
    return {"items": [{"emergency_id": e.emergency_id, "ambulance_id": e.ambulance_id, "patient_id": e.patient_id,
                       "ambulance_status": e.ambulance_status, "eta_minutes": e.eta_minutes,
                       "emergency_status": e.status, "is_simulated": bool(e.is_simulated)} for e in rows]}


@router.get("/{ambulance_id}")
def get_ambulance(ambulance_id: str, emergency_id: str = None, user=Depends(current_user), db=Depends(get_db)):
    """READ-ONLY view of the data the Control Room sent about this ambulance."""
    q = select(Emergency).where(Emergency.hospital_id == user.hospital_id, Emergency.ambulance_id == ambulance_id)
    if emergency_id:
        q = q.where(Emergency.emergency_id == emergency_id)
    emergencies = db.scalars(q.order_by(Emergency.id.desc())).all()
    if not emergencies:
        raise NotFound("Ambulance not found for this hospital.")
    active = [e for e in emergencies if e.status in ("INCOMING", "ACCEPTED", "ARRIVED")]
    chosen = (active or emergencies)[0]
    return ambulance_service.tracking_view(chosen, db.get(Hospital, user.hospital_id))
