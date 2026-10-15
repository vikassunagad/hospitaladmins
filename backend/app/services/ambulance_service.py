"""Ambulance updates, demo-route simulation, and tracking data."""
import math

from app.config import settings
from app.errors import Conflict
from app.models import now
from app.services import events
from app.services.reporting_service import client

EARTH_RADIUS_KM = 6371.0
DEMO_ROUTE_SEGMENTS = 20
NEAR_HOSPITAL_FRACTION = 0.2
AMBULANCE_STATUS_ORDER = ("ASSIGNED", "EN_ROUTE", "NEAR_HOSPITAL", "ARRIVED")


def _distance_km(start, end):
    """Return the great-circle distance between two (latitude, longitude) points."""
    lat1, lon1 = map(math.radians, start)
    lat2, lon2 = map(math.radians, end)
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, value)))


def route_length_km(route):
    """Return the total length of a route represented by latitude/longitude points."""
    return sum(_distance_km(start, end) for start, end in zip(route, route[1:]))


def build_demo_route(start, destination):
    """Build a deterministic straight-line route for the demo ambulance."""
    start_lat, start_lng = start
    end_lat, end_lng = destination
    return [
        [
            start_lat + (end_lat - start_lat) * index / DEMO_ROUTE_SEGMENTS,
            start_lng + (end_lng - start_lng) * index / DEMO_ROUTE_SEGMENTS,
        ]
        for index in range(DEMO_ROUTE_SEGMENTS + 1)
    ]


def apply_update(db, emergency, data, source, actor):
    """Apply a Control Room ambulance update and record its status transition."""
    if not emergency.ambulance_id:
        raise Conflict("Cannot update an emergency without an assigned ambulance.")

    previous_status = emergency.ambulance_status or "ASSIGNED"
    status = data.get("ambulance_status") or previous_status
    if previous_status not in AMBULANCE_STATUS_ORDER or status not in AMBULANCE_STATUS_ORDER:
        raise Conflict("Cannot update ambulance: status is invalid.")
    if AMBULANCE_STATUS_ORDER.index(status) < AMBULANCE_STATUS_ORDER.index(previous_status):
        raise Conflict(
            "Ambulance status cannot move backwards (%s -> %s)." % (previous_status, status),
            "INVALID_AMBULANCE_TRANSITION",
        )

    for field, attribute in (
        ("latitude", "ambulance_latitude"),
        ("longitude", "ambulance_longitude"),
        ("eta_minutes", "eta_minutes"),
        ("distance_km", "distance_km"),
    ):
        value = data.get(field)
        if value is not None:
            setattr(emergency, attribute, value)

    emergency.ambulance_status = status
    if status == "ARRIVED":
        emergency.eta_minutes = 0
        emergency.distance_km = 0
        route = emergency.route() or []
        if route:
            emergency.ambulance_latitude, emergency.ambulance_longitude = route[-1]

    emergency.ambulance_updated_at = now()
    details = {
        "ambulance_status": status,
        "latitude": emergency.ambulance_latitude,
        "longitude": emergency.ambulance_longitude,
        "eta_minutes": emergency.eta_minutes,
        "distance_km": emergency.distance_km,
    }
    events.audit(
        db,
        emergency.hospital_id,
        "AMBULANCE_STATUS_UPDATED",
        emergency_id=emergency.emergency_id,
        old_status=previous_status if status != previous_status else None,
        new_status=status if status != previous_status else None,
        actor=actor,
        source=source,
        details=details,
    )
    client.send_event(
        db,
        emergency.hospital_id,
        "AMBULANCE_UPDATE",
        emergency.emergency_id,
        details,
    )
    if status == "ARRIVED" and previous_status != "ARRIVED":
        events.alert(
            db,
            emergency.hospital_id,
            "AMBULANCE_ARRIVED",
            "Ambulance %s has arrived for emergency %s."
            % (emergency.ambulance_id, emergency.emergency_id),
            "info",
            emergency.emergency_id,
        )
        client.send_event(
            db,
            emergency.hospital_id,
            "AMBULANCE_ARRIVED",
            emergency.emergency_id,
            details,
        )


def _require_demo(emergency):
    if not settings.MOCK_CONTROL_ROOM:
        raise Conflict("Mock Control Room is switched off (MOCK_CONTROL_ROOM=false).", "MOCK_DISABLED")
    if not emergency.is_simulated:
        raise Conflict("Ambulance simulation is only available for simulated ambulances.")
    if emergency.status not in ("INCOMING", "ACCEPTED"):
        raise Conflict("Ambulance simulation is only available for active emergencies.")


def simulate_step(db, emergency):
    """Advance a simulated ambulance by one point along its demo route."""
    _require_demo(emergency)
    route = emergency.route() or []
    if len(route) < 2:
        raise Conflict("Cannot advance ambulance simulation: route is empty or incomplete.")
    if emergency.ambulance_status == "ARRIVED":
        raise Conflict("Cannot advance ambulance simulation: ambulance has already arrived.")

    last_index = len(route) - 1
    index = min(max(emergency.route_index or 0, 0) + 1, last_index)
    fraction = (last_index - index) / last_index
    remaining_km = route_length_km(route[index:])
    if index == last_index:
        status = "ARRIVED"
    elif fraction <= NEAR_HOSPITAL_FRACTION:
        status = "NEAR_HOSPITAL"
    else:
        status = "EN_ROUTE"

    emergency.route_index = index
    initial_eta = emergency.eta_initial_minutes or 8
    apply_update(
        db,
        emergency,
        {
            "ambulance_status": status,
            "latitude": route[index][0],
            "longitude": route[index][1],
            "eta_minutes": max(0, math.ceil(initial_eta * fraction)),
            "distance_km": round(remaining_km, 2),
        },
        source="MOCK_CONTROL_ROOM",
        actor="DEMO_SIMULATION",
    )


def simulate_reset(db, emergency):
    """Reset a simulated ambulance to the beginning of its demo route."""
    _require_demo(emergency)
    route = emergency.route() or []
    if len(route) < 2:
        raise Conflict("Cannot reset ambulance simulation: route is empty or incomplete.")

    emergency.route_index = 0
    emergency.ambulance_status = "ASSIGNED"
    emergency.ambulance_latitude, emergency.ambulance_longitude = route[0]
    emergency.eta_minutes = emergency.eta_initial_minutes
    emergency.distance_km = emergency.distance_initial_km
    emergency.ambulance_updated_at = now()

    events.audit(
        db,
        emergency.hospital_id,
        "DEMO_SIMULATION_RESET",
        emergency_id=emergency.emergency_id,
        actor="DEMO_SIMULATION",
        source="MOCK_CONTROL_ROOM",
    )


def tracking_view(emergency, hospital):
    """Return ambulance tracking data for the hospital map and dashboard."""
    route = emergency.route() or []

    position = None
    if (
        emergency.ambulance_latitude is not None
        and emergency.ambulance_longitude is not None
    ):
        position = [
            emergency.ambulance_latitude,
            emergency.ambulance_longitude,
        ]

    incident = None
    if (
        emergency.incident_latitude is not None
        and emergency.incident_longitude is not None
    ):
        incident = [
            emergency.incident_latitude,
            emergency.incident_longitude,
        ]

    total_km = route_length_km(route)
    route_index = max(0, min(emergency.route_index or 0, max(len(route) - 1, 0)))
    remaining_km = route_length_km(route[route_index:]) if len(route) >= 2 else 0.0

    status = emergency.ambulance_status or "ASSIGNED"
    status_messages = {
        "ASSIGNED": "Ambulance assigned and preparing to move",
        "EN_ROUTE": "Ambulance is travelling to the destination",
        "NEAR_HOSPITAL": "Ambulance is approaching the hospital",
        "ARRIVED": "Ambulance has arrived at the hospital",
    }
    next_steps = {
        "ASSIGNED": "Await movement update",
        "EN_ROUTE": "Monitor route and estimated arrival",
        "NEAR_HOSPITAL": "Prepare the receiving team",
        "ARRIVED": "Confirm arrival and update patient workflow",
    }

    demo_available = bool(
        settings.MOCK_CONTROL_ROOM
        and emergency.is_simulated
        and emergency.status in ("INCOMING", "ACCEPTED")
        and status != "ARRIVED"
    )

    return {
        "emergency_id": emergency.emergency_id,
        "patient_id": emergency.patient_id,
        "ambulance_id": emergency.ambulance_id,
        "status": status,
        "status_message": status_messages.get(status, "Awaiting status update"),
        "next_step": next_steps.get(status, "Check with Control Room"),
        "eta_minutes": emergency.eta_minutes,
        "distance_km": emergency.distance_km,
        "remaining_distance_km": round(remaining_km, 2),
        "route_total_km": round(total_km, 2),
        "progress_percent": emergency.progress_percent(),
        "last_updated": str(
            emergency.ambulance_updated_at or emergency.updated_at
        ),
        "position": position,
        "incident": incident,
        "incident_location": emergency.incident_location,
        "hospital": {
            "id": hospital.id,
            "name": hospital.name,
            "position": [hospital.latitude, hospital.longitude],
        },
        "route": route,
        "is_simulated": bool(emergency.is_simulated),
        "demo_available": demo_available,
        "mode_label": (
            "DEMO / SIMULATED AMBULANCE TRACKING"
            if emergency.is_simulated
            else "Location received from Control Room"
        ),
        "emergency_status": emergency.status,
    }
