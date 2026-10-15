"""Bed capacity + the core reservation rule.

Every change is ONE atomic SQL UPDATE with the safety condition inside the WHERE clause,
so two simultaneous requests can never take the same last bed.
"""
from sqlalchemy import select, update

from app.config import settings
from app.errors import Conflict, NotFound
from app.models import BED_TYPES, BedInventory, BedReservation, Hospital, now
from app.services import events
from app.services.reporting_service import client


def capacity_summary(db, hospital_id):
    rows = db.scalars(select(BedInventory).where(BedInventory.hospital_id == hospital_id)).all()
    out = {bt: {"total": 0, "occupied": 0, "reserved": 0, "free": 0} for bt in BED_TYPES}
    for r in rows:
        out[r.bed_type] = {"total": r.total, "occupied": r.occupied, "reserved": r.reserved,
                           "free": r.total - r.occupied - r.reserved}
    out["TOTAL"] = {k: sum(out[bt][k] for bt in BED_TYPES) for k in ("total", "occupied", "reserved", "free")}
    return out


def compute_status(summary):
    t = summary["TOTAL"]
    if t["total"] == 0 or t["free"] <= 0:
        return "UNAVAILABLE"
    load = (t["occupied"] + t["reserved"]) * 100.0 / t["total"]
    if load >= settings.CRITICAL_LOAD_THRESHOLD:
        return "CRITICAL_CAPACITY"
    if load >= settings.HIGH_LOAD_THRESHOLD:
        return "HIGH_LOAD"
    return "NORMAL"


def try_reserve(db, hospital_id, emergency_id, bed_type):
    """FREE -> RESERVED. Returns True only if a suitable bed really was free at this very moment."""
    result = db.execute(
        update(BedInventory)
        .where(BedInventory.hospital_id == hospital_id, BedInventory.bed_type == bed_type,
               BedInventory.total - BedInventory.occupied - BedInventory.reserved >= 1)
        .values(reserved=BedInventory.reserved + 1, updated_at=now()))
    if result.rowcount != 1:
        return False
    db.add(BedReservation(hospital_id=hospital_id, emergency_id=emergency_id, bed_type=bed_type, status="ACTIVE"))
    return True


def _active_reservation(db, hospital_id, emergency_id):
    return db.scalar(select(BedReservation).where(BedReservation.hospital_id == hospital_id,
                                                  BedReservation.emergency_id == emergency_id,
                                                  BedReservation.status == "ACTIVE"))


def release_reservation(db, hospital_id, emergency_id):
    """RESERVED -> FREE (only through a valid workflow such as CANCEL)."""
    res = _active_reservation(db, hospital_id, emergency_id)
    if not res:
        return False
    done = db.execute(update(BedInventory).where(
        BedInventory.hospital_id == hospital_id, BedInventory.bed_type == res.bed_type, BedInventory.reserved >= 1
    ).values(reserved=BedInventory.reserved - 1, updated_at=now()))
    if done.rowcount != 1:
        raise Conflict("Reservation counters are inconsistent.")
    res.status = "RELEASED"
    return True


def consume_reservation(db, hospital_id, emergency_id):
    """RESERVED -> OCCUPIED (patient admitted). Returns the bed type."""
    res = _active_reservation(db, hospital_id, emergency_id)
    if not res:
        raise Conflict("No active bed reservation for this emergency.", "NO_RESERVATION")
    done = db.execute(update(BedInventory).where(
        BedInventory.hospital_id == hospital_id, BedInventory.bed_type == res.bed_type, BedInventory.reserved >= 1
    ).values(reserved=BedInventory.reserved - 1, occupied=BedInventory.occupied + 1, updated_at=now()))
    if done.rowcount != 1:
        raise Conflict("Reservation counters are inconsistent.")
    res.status = "CONSUMED"
    return res.bed_type


def release_occupied(db, hospital_id, bed_type):
    """OCCUPIED -> FREE (patient discharged)."""
    done = db.execute(update(BedInventory).where(
        BedInventory.hospital_id == hospital_id, BedInventory.bed_type == bed_type, BedInventory.occupied >= 1
    ).values(occupied=BedInventory.occupied - 1, updated_at=now()))
    if done.rowcount != 1:
        raise Conflict("No occupied bed to release.")


def occupied_count(db, hospital_id, bed_type):
    return db.scalar(select(BedInventory.occupied).where(BedInventory.hospital_id == hospital_id,
                                                         BedInventory.bed_type == bed_type))


def update_capacity(db, hospital_id, bed_type, total, occupied, actor):
    """Manual capacity update by hospital staff. Reserved beds are protected: they cannot be edited here."""
    inv = db.scalar(select(BedInventory).where(BedInventory.hospital_id == hospital_id,
                                               BedInventory.bed_type == bed_type))
    if not inv:
        raise NotFound("Bed type not found.")
    old = {"total": inv.total, "occupied": inv.occupied}
    done = db.execute(update(BedInventory).where(
        BedInventory.hospital_id == hospital_id, BedInventory.bed_type == bed_type,
        BedInventory.reserved <= total - occupied
    ).values(total=total, occupied=occupied, updated_at=now()))
    if done.rowcount != 1:
        db.rollback()
        raise Conflict("Occupied + reserved beds cannot exceed total. Reserved beds for incoming emergencies "
                       "are protected.", "CAPACITY_CONFLICT")
    events.audit(db, hospital_id, "CAPACITY_UPDATED", actor=actor, details={"bed_type": bed_type, "old": old,
                                                                            "new": {"total": total,
                                                                                    "occupied": occupied}})
    after_capacity_change(db, hospital_id)
    db.commit()


def after_capacity_change(db, hospital_id, check_warnings=True):
    """Report capacity, refresh hospital status, raise capacity alerts. Call once per capacity change."""
    db.flush()
    summary = capacity_summary(db, hospital_id)
    client.send_capacity_update(db, hospital_id, summary)

    hospital = db.get(Hospital, hospital_id)
    new_status = compute_status(summary)
    if new_status != hospital.status:
        old_status, hospital.status = hospital.status, new_status
        events.audit(db, hospital_id, "HOSPITAL_STATUS_CHANGED", old_status=old_status, new_status=new_status)
        client.send_event(db, hospital_id, "HOSPITAL_STATUS_CHANGED",
                          payload={"old": old_status, "new": new_status})
        if new_status != "NORMAL":
            events.alert(db, hospital_id, new_status, "Hospital status is now %s." % new_status.replace("_", " "),
                         "critical" if new_status in ("CRITICAL_CAPACITY", "UNAVAILABLE") else "warning",
                         dedupe=True)
    if check_warnings:
        for bed_type in ("ICU", "EMERGENCY"):
            s = summary[bed_type]
            if s["total"] > 0 and s["free"] <= settings.CAPACITY_WARNING_FREE:
                events.alert(db, hospital_id, bed_type + "_CAPACITY_WARNING",
                             "%s beds almost full: %d free of %d." % (bed_type, s["free"], s["total"]),
                             "critical" if s["free"] == 0 else "warning", dedupe=True)
    return summary
