"""ResQGrid AI tools: emergency incident management with in-memory data so the demo runs anywhere.

Replace the synthetic data with real CAD (Computer-Aided Dispatch) API calls for production.
Keep a clear one-line docstring on each tool: the model reads it.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from strands import tool

# ── synthetic incident data ───────────────────────────────────────────────────
INCIDENTS: dict[str, dict] = {
    "INC-001": {
        "type": "fire",
        "description": "Three-storey residential building on fire, upper floors involved, occupants reported trapped",
        "location": "42 Harbour View Road, Sector 7",
        "reported_by": "neighbour via 911",
        "status": "active",
        "severity": "critical",
        "resources_dispatched": [],
        "log": [],
    },
    "INC-002": {
        "type": "medical",
        "description": "Multiple casualties reported at a highway pile-up, at least four vehicles, unknown number of injured",
        "location": "NH-48 km 112, near Greenfield overpass",
        "reported_by": "motorist via 911",
        "status": "active",
        "severity": "serious",
        "resources_dispatched": [],
        "log": [],
    },
    "INC-003": {
        "type": "hazmat",
        "description": "Chemical tanker overturned, unknown substance leaking, strong smell reported by bystanders",
        "location": "Industrial Corridor, Route 9 near Wharf Gate",
        "reported_by": "truck driver via radio",
        "status": "active",
        "severity": "serious",
        "resources_dispatched": [],
        "log": [],
    },
    "INC-004": {
        "type": "search_rescue",
        "description": "Two hikers overdue, last known position on the north trail, weather deteriorating",
        "location": "Ridgecrest Nature Reserve, North Trail marker 14",
        "reported_by": "family member",
        "status": "active",
        "severity": "moderate",
        "resources_dispatched": [],
        "log": [],
    },
    "INC-005": {
        "type": "infrastructure",
        "description": "Reported crack on bridge deck, traffic slowed, structural integrity unknown",
        "location": "Eastbrook Bridge, connecting Sector 3 and Sector 5",
        "reported_by": "road maintenance crew",
        "status": "active",
        "severity": "moderate",
        "resources_dispatched": [],
        "log": [],
    },
    "INC-006": {
        "type": "medical",
        "description": "Caller reports chest pain, patient is conscious and stable",
        "location": "Flat 8, Sunrise Apartments, Park Street",
        "reported_by": "patient via 911",
        "status": "active",
        "severity": "minor",
        "resources_dispatched": [],
        "log": [],
    },
}

# ── synthetic resource inventory ─────────────────────────────────────────────
RESOURCES: dict[str, dict] = {
    "fire_engine":    {"available": 4, "total": 6, "location": "Station Alpha"},
    "ambulance":      {"available": 7, "total": 10, "location": "Central Medical"},
    "hazmat_unit":    {"available": 2, "total": 2, "location": "Station Delta"},
    "rescue_team":    {"available": 3, "total": 4, "location": "Station Bravo"},
    "police_unit":    {"available": 8, "total": 12, "location": "District HQ"},
    "aerial_unit":    {"available": 1, "total": 1, "location": "Helipad North"},
    "structural_eng": {"available": 2, "total": 3, "location": "Public Works Depot"},
}

# ── dispatch log (append-only) ────────────────────────────────────────────────
DISPATCH_LOG: list[dict] = []


# ── tools ─────────────────────────────────────────────────────────────────────

@tool
def get_incident_report(incident_id: str) -> dict:
    """Retrieve the full report for an incident by its ID (e.g. INC-001)."""
    inc = INCIDENTS.get(incident_id.strip().upper())
    if not inc:
        return {"error": f"No incident found with ID {incident_id}. Known IDs: {list(INCIDENTS.keys())}"}
    return {"incident_id": incident_id.upper(), **inc}


@tool
def check_available_resources(resource_type: str, location: str = "") -> dict:
    """Check how many units of a resource type are available for dispatch right now."""
    key = resource_type.strip().lower().replace(" ", "_").replace("-", "_")
    res = RESOURCES.get(key)
    if not res:
        return {
            "error": f"Unknown resource type '{resource_type}'.",
            "known_types": list(RESOURCES.keys()),
        }
    return {
        "resource_type": key,
        "available": res["available"],
        "total": res["total"],
        "staging_location": res["location"],
        "requested_for": location or "not specified",
    }


@tool
def dispatch_resources(incident_id: str, resource_type: str, unit_count: int) -> dict:
    """Dispatch emergency resources to an active incident (irreversible; requires human approval for low-severity incidents)."""
    inc_id = incident_id.strip().upper()
    inc = INCIDENTS.get(inc_id)
    if not inc:
        return {"error": f"No incident found with ID {inc_id}."}

    key = resource_type.strip().lower().replace(" ", "_").replace("-", "_")
    res = RESOURCES.get(key)
    if not res:
        return {
            "error": f"Unknown resource type '{resource_type}'.",
            "known_types": list(RESOURCES.keys()),
        }

    if unit_count <= 0:
        return {"error": "unit_count must be a positive integer."}

    if res["available"] < unit_count:
        return {
            "error": f"Only {res['available']} {key} unit(s) available; {unit_count} requested.",
            "available": res["available"],
        }

    # Commit the dispatch.
    res["available"] -= unit_count
    dispatch_id = f"DSP-{uuid.uuid4().hex[:6].upper()}"
    record = {
        "dispatch_id":    dispatch_id,
        "incident_id":    inc_id,
        "resource_type":  key,
        "unit_count":     unit_count,
        "timestamp":      datetime.utcnow().isoformat() + "Z",
    }
    DISPATCH_LOG.append(record)
    inc["resources_dispatched"].append(record)
    inc["log"].append(f"Dispatched {unit_count}x {key} ({dispatch_id})")

    return {
        "dispatched":      True,
        "dispatch_id":     dispatch_id,
        "incident_id":     inc_id,
        "resource_type":   key,
        "unit_count":      unit_count,
        "remaining_units": res["available"],
    }


@tool
def log_incident_update(incident_id: str, status: str, notes: str) -> dict:
    """Log a status update or field note for an active incident."""
    inc_id = incident_id.strip().upper()
    inc = INCIDENTS.get(inc_id)
    if not inc:
        return {"error": f"No incident found with ID {inc_id}."}

    valid_statuses = {"active", "contained", "resolved", "monitoring", "escalated"}
    if status.lower() not in valid_statuses:
        return {"error": f"Invalid status '{status}'. Use one of: {sorted(valid_statuses)}"}

    inc["status"] = status.lower()
    entry = f"[{datetime.utcnow().isoformat()}Z] {status.upper()}: {notes}"
    inc["log"].append(entry)

    return {
        "incident_id": inc_id,
        "status":      inc["status"],
        "log_entry":   entry,
    }


TOOLS = [get_incident_report, check_available_resources, dispatch_resources, log_incident_update]
