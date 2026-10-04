"""Ground facts of the knowledge base.

Facts come from three places:

1. Instance frames (people, vehicles, permits, zones, spaces, reservations).
   They are translated by FrameSystem.to_facts(), so the frame layer and the
   logic layer can never disagree about an individual.
2. Policy facts below: tables the parking office publishes (which permit
   opens which zone type, which vehicle fits which bay).
3. Context facts that change per run: today's date, the current hour and
   the parking requests. These live in scenarios.py.
"""

from __future__ import annotations

from ..core.terms import Atom, format_atom
from ..frames.ontology import build_frames

POLICY_FACTS: list[Atom] = [
    # grants(PermitClass, ZoneType): a permit class opens a zone type
    ("grants", "student_permit", "student_zone"),
    ("grants", "employee_permit", "employee_zone"),
    ("grants", "visitor_pass", "visitor_zone"),
    # fits(VehicleType, SpaceType): physical compatibility of vehicle and bay
    ("fits", "car", "standard"),
    ("fits", "car", "accessible"),
    ("fits", "electric_car", "standard"),
    ("fits", "electric_car", "ev_charging"),
    ("fits", "electric_car", "accessible"),
    ("fits", "motorbike", "motorbike"),
    # open_type(SpaceType): bay types with no extra personal requirement
    ("open_type", "standard"),
    ("open_type", "ev_charging"),
    ("open_type", "motorbike"),
]


def frame_facts() -> list[Atom]:
    return build_frames().to_facts()


def base_facts() -> list[Atom]:
    """Frame facts plus policy facts, without any per-run context."""
    return frame_facts() + POLICY_FACTS


# Groups used when the facts are listed in the CLI, UI and report.
FACT_GROUPS = [
    ("People and roles", ("person", "student", "employee", "faculty", "staff", "visitor",
                          "accessibility_badge")),
    ("Vehicles and ownership", ("vehicle", "owns", "vehicle_type")),
    ("Permits", ("permit", "has_permit", "permit_class", "permit_status", "permit_start", "permit_expiry")),
    ("Facility and zones", ("parking_facility", "parking_zone", "part_of", "zone_type",
                            "zone_opens", "zone_closes")),
    ("Parking spaces", ("parking_space", "located_in", "space_type", "space_status")),
    ("Reservations", ("reservation", "reserved_by", "reserved_space", "reservation_date")),
    ("Policy tables", ("grants", "fits", "open_type")),
    ("Context (per scenario)", ("current_date", "current_hour", "requests")),
]


def grouped(facts) -> list[tuple[str, list[str]]]:
    """Sort facts into FACT_GROUPS for display. Unknown predicates go last."""
    out, used = [], set()
    for title, preds in FACT_GROUPS:
        rows = sorted((f for f in facts if f[0] in preds),
                      key=lambda f: (preds.index(f[0]), [str(t) for t in f[1:]]))
        if rows:
            out.append((title, [format_atom(f) + "." for f in rows]))
        used.update(preds)
    rest = sorted((f for f in facts if f[0] not in used), key=str)
    if rest:
        out.append(("Other", [format_atom(f) + "." for f in rest]))
    return out
