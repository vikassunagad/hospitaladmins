"""ControlRoomClient - the ONLY way this module talks to the outside world.

MOCK_CONTROL_ROOM=true  -> outgoing messages are just stored in the database (Integration Log).
MOCK_CONTROL_ROOM=false -> messages are also POSTed to CONTROL_ROOM_BASE_URL with HTTPX.
"""
import json

import httpx

from app.config import settings
from app.models import OutboundReport, now
from app.services import events


def _dump(obj):
    return json.dumps(obj, default=str)


def log_inbound(db, hospital_id, event, emergency_id=None, payload=None, source="CONTROL_ROOM"):
    """Record a message that arrived FROM the Control Room."""
    db.add(OutboundReport(hospital_id=hospital_id, direction="IN", event=event, emergency_id=emergency_id,
                          status="RECEIVED", payload=_dump({"source": source, "data": payload or {}})))


class ControlRoomClient:
    def send_event(self, db, hospital_id, event, emergency_id=None, payload=None):
        body = {"hospital_id": hospital_id, "event": event, "emergency_id": emergency_id,
                "payload": payload or {}, "sent_at": str(now())}
        row = OutboundReport(hospital_id=hospital_id, direction="OUT", event=event, emergency_id=emergency_id,
                             status="MOCK_STORED", payload=_dump(body))
        if not settings.MOCK_CONTROL_ROOM:
            try:
                headers = {"X-API-Key": settings.CONTROL_ROOM_API_KEY}
                response = httpx.post(settings.CONTROL_ROOM_BASE_URL + "/api/hospital-events",
                                      content=_dump(body), headers={**headers, "Content-Type": "application/json"},
                                      timeout=3.0)
                row.status = "SENT" if response.is_success else "FAILED"
                if not response.is_success:
                    row.error = "HTTP %s" % response.status_code
            except Exception as exc:  # network problems must never break hospital workflow
                row.status = "FAILED"
                row.error = str(exc)[:290]
        db.add(row)
        events.audit(db, hospital_id, "REPORT_SENT", emergency_id=emergency_id, details={"event": event,
                                                                                         "status": row.status})
        return row

    def send_capacity_update(self, db, hospital_id, summary):
        return self.send_event(db, hospital_id, "CAPACITY_UPDATED", payload={"capacity": summary})

    def send_emergency_status(self, db, hospital_id, emergency, event, extra=None):
        payload = {"status": emergency.status, "patient_id": emergency.patient_id,
                   "ambulance_id": emergency.ambulance_id, "required_bed_type": emergency.required_bed_type}
        payload.update(extra or {})
        return self.send_event(db, hospital_id, event, emergency.emergency_id, payload)

    def send_patient_status(self, db, hospital_id, patient, event):
        return self.send_event(db, hospital_id, event, patient.emergency_id,
                               {"patient_id": patient.patient_id, "status": patient.status,
                                "assigned_bed": patient.assigned_bed})


client = ControlRoomClient()
