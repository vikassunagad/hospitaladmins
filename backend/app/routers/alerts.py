from fastapi import APIRouter, Depends
from sqlalchemy import func, select, update

from app.database import get_db
from app.dependencies import current_user
from app.errors import NotFound
from app.models import Alert
from app.schemas import alert_dict

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get("")
def list_alerts(unread: bool = False, user=Depends(current_user), db=Depends(get_db)):
    q = select(Alert).where(Alert.hospital_id == user.hospital_id)
    if unread:
        q = q.where(Alert.is_read.is_(False))
    rows = db.scalars(q.order_by(Alert.id.desc()).limit(200)).all()
    count = db.scalar(select(func.count()).select_from(Alert).where(Alert.hospital_id == user.hospital_id,
                                                                    Alert.is_read.is_(False)))
    return {"items": [alert_dict(a) for a in rows], "unread": count}


@router.post("/read-all")
def read_all(user=Depends(current_user), db=Depends(get_db)):
    db.execute(update(Alert).where(Alert.hospital_id == user.hospital_id).values(is_read=True))
    db.commit()
    return {"ok": True}


@router.post("/{alert_id}/read")
def read_one(alert_id: int, user=Depends(current_user), db=Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if not alert or alert.hospital_id != user.hospital_id:
        raise NotFound("Alert not found.")
    alert.is_read = True
    db.commit()
    return {"ok": True}
