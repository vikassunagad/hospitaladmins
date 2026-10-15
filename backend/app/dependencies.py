"""Who is calling? The hospital identity ALWAYS comes from here, never from the request body."""
import hmac

from fastapi import Depends, Request

from app.auth import read_token
from app.config import settings
from app.database import get_db
from app.errors import Forbidden, Invalid, NotFound, Unauthorized
from app.models import Hospital, HospitalUser


def current_user(request: Request, db=Depends(get_db)):
    token = None
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
    if not token:
        token = request.cookies.get(settings.COOKIE_NAME)
    user_id = read_token(token) if token else None
    user = db.get(HospitalUser, user_id) if user_id else None
    if not user or not user.is_active:
        raise Unauthorized("Please log in.")
    if user.role != "HOSPITAL_ADMIN":
        raise Forbidden("You are not authorized to use this module.")
    return user


class Caller:
    def __init__(self, source, user=None):
        self.source = source  # CONTROL_ROOM or MOCK_CONTROL_ROOM
        self.user = user


def control_room_caller(request: Request, db=Depends(get_db)):
    """Inbound integration calls: real Control Room (X-API-Key) or, in mock mode, a logged-in hospital user."""
    key = request.headers.get("x-api-key", "")
    if settings.CONTROL_ROOM_API_KEY and key and hmac.compare_digest(key, settings.CONTROL_ROOM_API_KEY):
        return Caller("CONTROL_ROOM")
    if settings.MOCK_CONTROL_ROOM:
        return Caller("MOCK_CONTROL_ROOM", current_user(request, db))
    raise Unauthorized("Invalid or missing API key.")


def resolve_hospital(db, caller, body_hospital_id):
    """A hospital user can only act for their own hospital. The real Control Room names the target hospital."""
    if caller.user is not None:
        if body_hospital_id and body_hospital_id != caller.user.hospital_id:
            raise Forbidden("You can only act for your own hospital.")
        hospital_id = caller.user.hospital_id
    else:
        if not body_hospital_id:
            raise Invalid("hospital_id is required.")
        hospital_id = body_hospital_id
    hospital = db.get(Hospital, hospital_id)
    if not hospital:
        raise NotFound("Hospital not found.")
    return hospital
