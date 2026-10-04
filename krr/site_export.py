"""JSON export of a run, shared by tools/build_site.py and the website.

The website runs this same module in the browser (Pyodide) when a visitor
moves the scenario clock, so the page and the build use one copy of the code.
"""

from __future__ import annotations

import dataclasses
import datetime
import re

from .knowledge_base.scenarios import MAIN
from .reasoning.explain import why_not
from .system import run


def proof_json(node) -> dict:
    return {"t": node.text, "how": node.how, "c": [proof_json(c) for c in node.children]}


def reason_json(r) -> dict:
    return {"goal": r.goal, "rule": r.rule, "detail": r.detail,
            "c": [reason_json(c) for c in r.children]}


def requests_json(r) -> list[dict]:
    kb = r.kb
    out = []
    for o in r.outcomes():
        t = next(f[3] for f in kb.facts_for("requests") if f[1] == o.person and f[2] == o.space)
        goal = f"allocate({o.person}, {o.space})"
        item = {"driver": o.person, "space": o.space, "time": t, "goal": goal,
                "allocated": o.allocated, "reasons": o.reasons}
        res = r.prove(goal)
        if res.success:
            item["proof"] = proof_json(res.proofs[0])
            item["steps"] = res.steps
        else:
            item["whyNot"] = reason_json(why_not(kb, goal))
        out.append(item)
    return out


def run_summary(r, date: int, hour: int) -> dict:
    """What the replay needs besides the decisions: the clock and the size of each cycle."""
    return {"date": date, "hour": hour, "facts": len(r.forward.initial),
            "derived": len(r.forward.derived), "fired": [c.fired for c in r.forward.cycles]}


ROLES = ("student", "faculty", "staff", "visitor")
VEHICLES = ("car", "electric_car", "motorbike")
PERMITS = ("valid", "expired", "not_started", "none")
PERMIT_CLASS = {"student": "student_permit", "faculty": "employee_permit",
                "staff": "employee_permit", "visitor": "visitor_pass"}
NAME = re.compile(r"[a-z][a-z0-9_]{1,15}")


def _shift_date(date: int, days: int) -> int:
    d = datetime.date(date // 10000, date // 100 % 100, date % 100) + datetime.timedelta(days=days)
    return d.year * 10000 + d.month * 100 + d.day


def driver_facts(d: dict, date: int, taken: set[str]) -> list[str]:
    """Facts for a driver added on the website, in the same shape the frames
    produce for the built-in drivers (see ali, fatima and bilal in facts.txt)."""
    name = str(d.get("name", "")).strip().lower()
    if not NAME.fullmatch(name):
        raise ValueError(f"name {name!r}: use 2-16 lower-case letters, digits or _ , starting with a letter")
    if name in taken:
        raise ValueError(f"name {name!r} is already used in the knowledge base")
    role, vehicle, permit = d.get("role"), d.get("vehicle"), d.get("permit")
    if role not in ROLES or vehicle not in VEHICLES or permit not in PERMITS:
        raise ValueError(f"unknown role, vehicle or permit for {name}")
    space, time = str(d.get("space", "")), int(d.get("time", -1))
    if space not in taken or not space.startswith("s_"):
        raise ValueError(f"unknown bay {space!r}")
    if not (0 <= time <= 2359 and time % 100 < 60):
        raise ValueError(f"time {time} is not HHMM")
    veh, pm = f"veh_{name}", f"pm_{name}"
    facts = [f"{role}({name})", f"accessibility_badge({name}, {'yes' if d.get('badge') else 'no'})",
             f"owns({name}, {veh})", f"vehicle({veh})", f"vehicle_type({veh}, {vehicle})",
             f"requests({name}, {space}, {time})"]
    if permit != "none":
        start, expiry = {"valid": (_shift_date(date, -30), _shift_date(date, 180)),
                         "expired": (_shift_date(date, -365), _shift_date(date, -1)),
                         "not_started": (_shift_date(date, 1), _shift_date(date, 365))}[permit]
        facts += [f"has_permit({name}, {pm})", f"permit({pm})",
                  f"permit_class({pm}, {PERMIT_CLASS[role]})", f"permit_status({pm}, active)",
                  f"permit_start({pm}, {start})", f"permit_expiry({pm}, {expiry})"]
    return facts


def morning_rush_at(date: int, hour: int, extra: list[dict] | None = None) -> dict:
    """The main scenario decided at another date (YYYYMMDD) and hour (0-23),
    optionally with extra drivers added on the website.

    The requests keep their order and spacing and arrive in the two hours
    before the decision. For a decision at 00:00 or 01:00 they arrive from
    22:00 the evening before, so the timestamps never wrap past midnight.
    Added drivers keep the arrival time they were given.
    """
    if not (0 <= hour <= 23):
        raise ValueError(f"hour must be 0-23, got {hour}")
    first = MAIN.requests[0][2]
    start = (hour - 2) * 100 if hour >= 2 else 2200
    shift = start - first
    sc = dataclasses.replace(MAIN, date=date, hour=hour,
                             requests=[(p, s, t + shift) for p, s, t in MAIN.requests])
    if extra:
        if len(extra) > 4:
            raise ValueError("at most 4 added drivers")
        taken = {str(t) for f in sc.build_kb().facts for t in f[1:]}
        added: list[str] = []
        for d in extra:
            facts = driver_facts(d, date, taken)
            name = str(d["name"]).strip().lower()
            taken.update((name, f"veh_{name}", f"pm_{name}"))
            added += facts
        sc = dataclasses.replace(sc, add=list(sc.add) + added)
    r = run(sc)
    return {"run": run_summary(r, date, hour), "requests": requests_json(r)}
