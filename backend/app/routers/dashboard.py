from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.config import settings
from app.database import get_db
from app.dependencies import current_user
from app.models import Alert, AuditLog, Emergency, Hospital, now
from app.schemas import alert_dict, audit_dict, emergency_dict, hospital_dict, iso, patient_dict
from app.services import ambulance_service, patient_service, reservation_service

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("")
def dashboard(user=Depends(current_user), db=Depends(get_db)):
    hid = user.hospital_id
    hospital = db.get(Hospital, hid)
    cap = reservation_service.capacity_summary(db, hid)
    emergencies = db.scalars(select(Emergency).where(Emergency.hospital_id == hid)
                             .order_by(Emergency.id.desc()).limit(8)).all()
    active_amb = db.scalar(select(Emergency).where(
        Emergency.hospital_id == hid, Emergency.ambulance_id.is_not(None),
        Emergency.status.in_(("INCOMING", "ACCEPTED"))).order_by(Emergency.id.desc()))
    alerts = db.scalars(select(Alert).where(Alert.hospital_id == hid, Alert.is_read.is_(False))
                        .order_by(Alert.id.desc()).limit(6)).all()
    unread = db.scalar(select(func.count()).select_from(Alert).where(Alert.hospital_id == hid,
                                                                    Alert.is_read.is_(False)))
    timeline = db.scalars(select(AuditLog).where(AuditLog.hospital_id == hid)
                          .order_by(AuditLog.id.desc()).limit(10)).all()
    total = cap["TOTAL"]
    return {
        "hospital": hospital_dict(hospital), "mock_mode": settings.MOCK_CONTROL_ROOM, "capacity": cap,
        "cards": {"total": total["total"], "occupied": total["occupied"], "reserved": total["reserved"],
                  "free": total["free"], "icu_free": cap["ICU"]["free"], "emergency_free": cap["EMERGENCY"]["free"]},
        "emergencies": [emergency_dict(e) for e in emergencies],
        "patients": [patient_dict(p) for p in patient_service.list_patients(db, hid, limit=8)],
        "alerts": [alert_dict(a) for a in alerts], "unread_alerts": unread,
        "timeline": [audit_dict(a) for a in timeline],
        "ambulance": ambulance_service.tracking_view(active_amb, hospital) if active_amb else None,
        "updated_at": iso(now()),
    }
