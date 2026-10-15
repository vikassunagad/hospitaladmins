from fastapi import APIRouter, Depends

from app.config import settings
from app.database import get_db
from app.dependencies import current_user
from app.models import Hospital
from app.schemas import CapacityIn
from app.services import reservation_service

router = APIRouter(prefix="/api/capacity", tags=["Capacity"])


def _payload(db, hospital_id):
    summary = reservation_service.capacity_summary(db, hospital_id)
    return {"capacity": summary, "status": db.get(Hospital, hospital_id).status,
            "thresholds": {"high_load": settings.HIGH_LOAD_THRESHOLD,
                           "critical": settings.CRITICAL_LOAD_THRESHOLD}}


@router.get("")
def get_capacity(user=Depends(current_user), db=Depends(get_db)):
    return _payload(db, user.hospital_id)


@router.put("")
def put_capacity(body: CapacityIn, user=Depends(current_user), db=Depends(get_db)):
    reservation_service.update_capacity(db, user.hospital_id, body.bed_type, body.total, body.occupied,
                                        user.username)
    return _payload(db, user.hospital_id)
