from fastapi import APIRouter, Depends, Response
from sqlalchemy import select

from app.auth import create_token, verify_password
from app.config import settings
from app.database import get_db
from app.dependencies import current_user
from app.errors import Unauthorized
from app.models import Hospital, HospitalUser
from app.schemas import LoginIn, hospital_dict
from app.services import events

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _me(db, user):
    hospital = db.get(Hospital, user.hospital_id)
    return {"user": {"username": user.username, "role": user.role}, "hospital": hospital_dict(hospital),
            "config": {"mock_control_room": settings.MOCK_CONTROL_ROOM, "auto_accept": settings.AUTO_ACCEPT,
                       "high_load_threshold": settings.HIGH_LOAD_THRESHOLD,
                       "critical_load_threshold": settings.CRITICAL_LOAD_THRESHOLD}}


@router.post("/login")
def login(body: LoginIn, response: Response, db=Depends(get_db)):
    user = db.scalar(select(HospitalUser).where(HospitalUser.username == body.username))
    # Same message for "no such user" and "wrong password" so usernames cannot be guessed.
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise Unauthorized("Invalid username or password.")
    events.audit(db, user.hospital_id, "LOGIN", actor=user.username)
    db.commit()
    token = create_token(user.id)
    response.set_cookie(settings.COOKIE_NAME, token, httponly=True, samesite="lax",
                        max_age=settings.SESSION_HOURS * 3600)
    result = _me(db, user)
    result["token"] = token
    return result


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(settings.COOKIE_NAME)
    return {"ok": True}


@router.get("/me")
def me(user=Depends(current_user), db=Depends(get_db)):
    return _me(db, user)
