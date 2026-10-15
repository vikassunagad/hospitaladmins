"""Database tables."""
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import (Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

BED_TYPES = ("GENERAL", "ICU", "EMERGENCY")
EMERGENCY_STATUSES = ("INCOMING", "ACCEPTED", "REJECTED", "ARRIVED", "ADMITTED", "UNDER_TREATMENT", "DISCHARGED",
                      "CANCELLED")
PATIENT_STATUSES = ("INCOMING", "ARRIVED", "ADMITTED", "UNDER_TREATMENT", "DISCHARGED")
AMBULANCE_STATUSES = ("ASSIGNED", "EN_ROUTE", "NEAR_HOSPITAL", "ARRIVED")


def now():
    return datetime.now().replace(microsecond=0)


def _in(column, values):
    return "%s IN (%s)" % (column, ",".join("'%s'" % v for v in values))


class Hospital(Base):
    __tablename__ = "hospitals"
    id: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default="NORMAL")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (CheckConstraint(_in("status", ("NORMAL", "HIGH_LOAD", "CRITICAL_CAPACITY", "UNAVAILABLE")),
                                      name="ck_hospital_status"),)


class HospitalUser(Base):
    __tablename__ = "hospital_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(30), default="HOSPITAL_ADMIN")
    hospital_id: Mapped[str] = mapped_column(ForeignKey("hospitals.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class BedInventory(Base):
    __tablename__ = "bed_inventory"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hospital_id: Mapped[str] = mapped_column(ForeignKey("hospitals.id"), index=True)
    bed_type: Mapped[str] = mapped_column(String(20))
    total: Mapped[int] = mapped_column(Integer, default=0)
    occupied: Mapped[int] = mapped_column(Integer, default=0)
    reserved: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    __table_args__ = (
        UniqueConstraint("hospital_id", "bed_type", name="uq_bed_hospital_type"),
        CheckConstraint("total >= 0 AND occupied >= 0 AND reserved >= 0", name="ck_bed_non_negative"),
        # The database itself refuses: occupied + reserved > total  (so free can never be < 0)
        CheckConstraint("occupied + reserved <= total", name="ck_bed_capacity"),
        CheckConstraint(_in("bed_type", BED_TYPES), name="ck_bed_type"),
    )


class Emergency(Base):
    __tablename__ = "emergencies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    emergency_id: Mapped[str] = mapped_column(String(40))
    control_room_emergency_id: Mapped[str] = mapped_column(String(40))
    patient_id: Mapped[str] = mapped_column(String(40))
    patient_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    hospital_id: Mapped[str] = mapped_column(ForeignKey("hospitals.id"))
    emergency_type: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(20))
    incident_location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    incident_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    incident_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ambulance_id: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    ambulance_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    ambulance_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ambulance_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ambulance_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    eta_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    eta_initial_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    distance_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    distance_initial_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    route_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    route_index: Mapped[int] = mapped_column(Integer, default=0)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    required_treatment: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    required_bed_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="INCOMING")
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    __table_args__ = (
        UniqueConstraint("hospital_id", "control_room_emergency_id", name="uq_em_hospital_crid"),
        UniqueConstraint("hospital_id", "emergency_id", name="uq_em_hospital_eid"),
        Index("ix_em_hospital_status", "hospital_id", "status"),
        CheckConstraint(_in("status", EMERGENCY_STATUSES), name="ck_em_status"),
        CheckConstraint(_in("required_bed_type", BED_TYPES), name="ck_em_bed_type"),
    )

    def route(self):
        return json.loads(self.route_json) if self.route_json else []

    def progress_percent(self):
        if self.ambulance_status == "ARRIVED":
            return 100
        if self.is_simulated:
            r = self.route()
            return round(self.route_index * 100 / (len(r) - 1)) if len(r) > 1 else 0
        if self.distance_initial_km and self.distance_km is not None:
            return max(0, min(100, round(100 - self.distance_km * 100 / self.distance_initial_km)))
        return 0


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[str] = mapped_column(String(40), index=True)
    control_room_patient_id: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(100), default="Demo Patient")
    emergency_id: Mapped[str] = mapped_column(String(40))
    hospital_id: Mapped[str] = mapped_column(ForeignKey("hospitals.id"), index=True)
    emergency_type: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(20))
    bed_type: Mapped[str] = mapped_column(String(20))
    arrival_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assigned_bed: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="INCOMING")
    treatment_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    __table_args__ = (
        UniqueConstraint("hospital_id", "emergency_id", name="uq_patient_hospital_emergency"),
        CheckConstraint(_in("status", PATIENT_STATUSES), name="ck_patient_status"),
    )


class BedReservation(Base):
    __tablename__ = "bed_reservations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hospital_id: Mapped[str] = mapped_column(ForeignKey("hospitals.id"), index=True)
    emergency_id: Mapped[str] = mapped_column(String(40))
    bed_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")  # ACTIVE / CONSUMED / RELEASED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    __table_args__ = (
        UniqueConstraint("hospital_id", "emergency_id", name="uq_res_hospital_emergency"),
        CheckConstraint(_in("status", ("ACTIVE", "CONSUMED", "RELEASED")), name="ck_res_status"),
    )


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hospital_id: Mapped[str] = mapped_column(ForeignKey("hospitals.id"), index=True)
    alert_type: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(String(300))
    severity: Mapped[str] = mapped_column(String(20), default="info")  # info / warning / critical
    emergency_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # event_id
    hospital_id: Mapped[Optional[str]] = mapped_column(String(10), index=True, nullable=True)
    emergency_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    patient_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50))
    old_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    actor: Mapped[str] = mapped_column(String(60), default="SYSTEM")
    source: Mapped[str] = mapped_column(String(30), default="HOSPITAL")
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=now)


class OutboundReport(Base):
    """Integration log: every message to (OUT) or from (IN) the Control Room."""
    __tablename__ = "outbound_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hospital_id: Mapped[str] = mapped_column(ForeignKey("hospitals.id"), index=True)
    direction: Mapped[str] = mapped_column(String(3))  # IN / OUT
    event: Mapped[str] = mapped_column(String(50))
    emergency_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20))  # RECEIVED / MOCK_STORED / SENT / FAILED
    payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
