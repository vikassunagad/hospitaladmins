"""Small helpers that write audit-log rows and alerts."""
import json

from sqlalchemy import select

from app.models import Alert, AuditLog


def audit(db, hospital_id, event_type, emergency_id=None, patient_id=None, old_status=None, new_status=None,
          actor="SYSTEM", source="HOSPITAL", details=None):
    if details is not None and not isinstance(details, str):
        details = json.dumps(details, default=str)
    db.add(AuditLog(hospital_id=hospital_id, emergency_id=emergency_id, patient_id=patient_id,
                    event_type=event_type, old_status=old_status, new_status=new_status,
                    actor=actor, source=source, details=details))


def alert(db, hospital_id, alert_type, message, severity="info", emergency_id=None, dedupe=False):
    """dedupe=True: do not create a second alert while an unread one of the same type exists."""
    if dedupe:
        existing = db.scalar(select(Alert.id).where(Alert.hospital_id == hospital_id,
                                                    Alert.alert_type == alert_type,
                                                    Alert.is_read.is_(False)).limit(1))
        if existing:
            return None
    row = Alert(hospital_id=hospital_id, alert_type=alert_type, message=message, severity=severity,
                emergency_id=emergency_id)
    db.add(row)
    return row
