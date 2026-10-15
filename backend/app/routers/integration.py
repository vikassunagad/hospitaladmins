"""Control Room <-> Hospital messages. This is the ONLY door to the outside world."""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.dependencies import control_room_caller, current_user, resolve_hospital
from app.errors import Conflict
from app.models import Hospital, OutboundReport
from app.schemas import (AmbulanceUpdateIn, CancelIn, EmergencyIn, SampleIn, emergency_dict, report_dict)
from app.services import ambulance_service, emergency_service, mock_control_room, reservation_service

router = APIRouter(prefix="/api/integration", tags=["Control Room Integration"])


def _inbound_result(emergency, duplicate):
    if duplicate:
        result = "DUPLICATE"
    elif emergency.status == "REJECTED":
        result = "REJECTED_" + (emergency.rejection_reason or "REJECTED")
    else:
        result = emergency.status
    return {"result": result, "duplicate": duplicate, "emergency": emergency_dict(emergency)}


@router.post("/control-room/emergencies")
def receive_emergency(body: EmergencyIn, caller=Depends(control_room_caller), db=Depends(get_db)):
    hospital = resolve_hospital(db, caller, body.hospital_id)
    emergency, duplicate = emergency_service.receive_emergency(db, hospital.id, body.model_dump(), caller.source)
    return _inbound_result(emergency, duplicate)


@router.post("/control-room/ambulance-update")
def ambulance_update(body: AmbulanceUpdateIn, caller=Depends(control_room_caller), db=Depends(get_db)):
    hospital = resolve_hospital(db, caller, body.hospital_id)
    emergency = emergency_service.update_ambulance(db, hospital.id, body.control_room_emergency_id,
                                                   body.model_dump(), caller.source, caller.source)
    return {"result": "OK", "ambulance": ambulance_service.tracking_view(emergency, hospital)}


@router.post("/control-room/cancel")
def cancel(body: CancelIn, caller=Depends(control_room_caller), db=Depends(get_db)):
    hospital = resolve_hospital(db, caller, body.hospital_id)
    emergency = emergency_service.get_emergency(db, hospital.id, body.control_room_emergency_id)
    emergency = emergency_service.cancel_emergency(db, hospital.id, emergency.emergency_id, caller.source,
                                                   caller.source)
    return {"result": "CANCELLED", "emergency": emergency_dict(emergency)}


@router.get("/reports")
def reports(direction: str = None, user=Depends(current_user), db=Depends(get_db)):
    q = select(OutboundReport).where(OutboundReport.hospital_id == user.hospital_id)
    if direction in ("IN", "OUT"):
        q = q.where(OutboundReport.direction == direction)
    rows = db.scalars(q.order_by(OutboundReport.id.desc()).limit(300)).all()
    return {"items": [report_dict(r) for r in rows], "mock_mode": settings.MOCK_CONTROL_ROOM}


# ---- Mock Control Room helpers (only when MOCK_CONTROL_ROOM=true) ---------------------------------------------

def _mock_only():
    if not settings.MOCK_CONTROL_ROOM:
        raise Conflict("Mock Control Room is switched off (MOCK_CONTROL_ROOM=false).", "MOCK_DISABLED")


@router.post("/mock/sample-emergency")
def mock_sample_emergency(body: SampleIn = SampleIn(), user=Depends(current_user), db=Depends(get_db)):
    """Pretend to be the Control Room and send this hospital a sample emergency."""
    _mock_only()
    payload = mock_control_room.sample_payload(db, user.hospital_id, body.bed_type, body.severity)
    emergency, duplicate = emergency_service.receive_emergency(db, user.hospital_id, payload, "MOCK_CONTROL_ROOM")
    return _inbound_result(emergency, duplicate)


@router.post("/mock/emergencies/{emergency_id}/simulate/step")
def mock_step(emergency_id: str, user=Depends(current_user), db=Depends(get_db)):
    _mock_only()
    emergency = emergency_service.get_emergency(db, user.hospital_id, emergency_id)
    ambulance_service.simulate_step(db, emergency)
    db.commit()
    return ambulance_service.tracking_view(emergency, db.get(Hospital, user.hospital_id))


@router.post("/mock/emergencies/{emergency_id}/simulate/reset")
def mock_reset(emergency_id: str, user=Depends(current_user), db=Depends(get_db)):
    _mock_only()
    emergency = emergency_service.get_emergency(db, user.hospital_id, emergency_id)
    ambulance_service.simulate_reset(db, emergency)
    db.commit()
    return ambulance_service.tracking_view(emergency, db.get(Hospital, user.hospital_id))
