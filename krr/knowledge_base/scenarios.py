"""Scenarios: the per-run context added on top of the base knowledge base.

A scenario sets today's date, the current hour and the parking requests,
and can add or remove facts to set up an edge case. Every test case in the
report is a scenario with expected outcomes, and the unit tests check those
outcomes with both chaining engines.

requests(Person, Space, Time): Time is the gate timestamp as HHMM.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.kb import KnowledgeBase
from ..core.terms import Atom, parse_atom
from ..frames.ontology import TODAY
from .facts import base_facts
from .rules import CONSTRAINTS, RULES


@dataclass
class Expectation:
    goal: str            # ground atom, e.g. "allocate(ali, s_a1)"
    holds: bool          # expected truth value
    note: str = ""


@dataclass
class Scenario:
    key: str
    title: str
    description: str
    requests: list[tuple[str, str, int]] = field(default_factory=list)
    date: int = TODAY
    hour: int = 10
    add: list[str] = field(default_factory=list)       # extra facts
    remove: list[str] = field(default_factory=list)    # facts taken out
    expectations: list[Expectation] = field(default_factory=list)
    focus_goal: str = ""        # goal shown in the backward-chaining trace

    def context_facts(self) -> list[Atom]:
        facts = [("current_date", self.date), ("current_hour", self.hour)]
        facts += [("requests", p, s, t) for p, s, t in self.requests]
        facts += [parse_atom(f) for f in self.add]
        return facts

    def build_kb(self) -> KnowledgeBase:
        kb = KnowledgeBase(base_facts() + self.context_facts(), RULES, CONSTRAINTS)
        for fact in self.remove:
            kb.remove_fact(fact)
        return kb


E = Expectation

SCENARIOS: dict[str, Scenario] = {}


def _add(s: Scenario) -> Scenario:
    SCENARIOS[s.key] = s
    return s


MAIN = _add(Scenario(
    "morning_rush", "Main demo: morning rush at 10:00",
    "Eight drivers arrive between 08:00 and 09:20 on 2 Oct 2026. Three of them want the "
    "same student bay s_a1, two visitors want the visitor bay, a faculty member uses his "
    "reservation and a staff member on a motorbike asks for a car bay.",
    requests=[("ahmed", "s_e3", 800), ("fatima", "s_e1", 830), ("zara", "s_a1", 850),
              ("usman", "s_a1", 900), ("ali", "s_a1", 905), ("sara", "s_a1", 910),
              ("hina", "s_v1", 915), ("bilal", "s_v1", 920)],
    expectations=[
        E("allocate(ahmed, s_e3)", True, "reservation holder gets his reserved bay"),
        E("allocate(sara, s_a1)", True, "badge holder wins s_a1 on priority"),
        E("allocate(bilal, s_v1)", True, "visitor with a pass"),
        E("allocate(zara, s_a1)", False, "loses to sara (priority)"),
        E("allocate(ali, s_a1)", False, "loses to sara and zara"),
        E("allocate(usman, s_a1)", False, "expired permit"),
        E("allocate(hina, s_v1)", False, "no visitor pass"),
        E("allocate(fatima, s_e1)", False, "motorbike does not fit a car bay"),
    ],
    focus_goal="allocate(ahmed, s_e3)"))

TEST_CASES: list[Scenario] = [
    _add(Scenario(
        "tc01_valid_student", "TC1  Valid student, valid permit, free student bay",
        "Ali (student, permit valid until 30 Jun 2027) asks for the vacant bay s_a1 in the "
        "student zone.",
        requests=[("ali", "s_a1", 900)],
        expectations=[E("authorized_driver(ali)", True), E("eligible_for_space(ali, s_a1)", True),
                      E("can_allocate(ali, s_a1)", True), E("allocate(ali, s_a1)", True)],
        focus_goal="allocate(ali, s_a1)")),
    _add(Scenario(
        "tc02_expired_permit", "TC2  Expired permit",
        "Usman's student permit expired on 15 Sep 2026. Today is 2 Oct 2026.",
        requests=[("usman", "s_a1", 900)],
        expectations=[E("permit_valid(p_usman)", False), E("authorized_driver(usman)", False),
                      E("allocate(usman, s_a1)", False)],
        focus_goal="authorized_driver(usman)")),
    _add(Scenario(
        "tc03_visitor_no_pass", "TC3  Visitor without authorization",
        "Hina is a visitor with no visitor pass. Bilal, also a visitor, has a pass for today.",
        requests=[("hina", "s_v1", 915)],
        expectations=[E("authorized_driver(hina)", False), E("allocate(hina, s_v1)", False),
                      E("authorized_driver(bilal)", True)],
        focus_goal="authorized_driver(hina)")),
    _add(Scenario(
        "tc04_occupied", "TC4  Space already occupied",
        "Ali asks for s_a2, a student bay that is occupied.",
        requests=[("ali", "s_a2", 900)],
        expectations=[E("eligible_for_space(ali, s_a2)", True), E("space_free(s_a2)", False),
                      E("can_allocate(ali, s_a2)", False), E("allocate(ali, s_a2)", False)],
        focus_goal="can_allocate(ali, s_a2)")),
    _add(Scenario(
        "tc05_student_in_employee_zone", "TC5  Student requests an employee-only space",
        "Ali asks for s_e1 in the employee zone.",
        requests=[("ali", "s_e1", 900)],
        expectations=[E("authorized_driver(ali)", True), E("zone_access(ali, zone_e)", False),
                      E("allocate(ali, s_e1)", False)],
        focus_goal="can_allocate(ali, s_e1)")),
    _add(Scenario(
        "tc06_no_suitable_space", "TC6  Eligible driver, but no suitable space",
        "Fatima (staff) is authorized for the employee zone, but she rides a motorbike and "
        "the employee zone has no motorbike bay.",
        requests=[("fatima", "s_e1", 830)],
        expectations=[E("authorized_driver(fatima)", True), E("zone_access(fatima, zone_e)", True),
                      E("suitable_space(fatima, s_e1)", False),
                      E("allocate(fatima, s_e1)", False)],
        focus_goal="can_allocate(fatima, S)")),
    _add(Scenario(
        "tc07_conflict", "TC7  Three drivers request the same space",
        "Zara (08:50), Ali (09:05) and Sara (09:10, badge holder) all ask for s_a1. "
        "Sara has priority 3 and wins. Between Zara and Ali (both priority 1) the earlier "
        "request wins, so Ali also loses to Zara.",
        requests=[("zara", "s_a1", 850), ("ali", "s_a1", 905), ("sara", "s_a1", 910)],
        expectations=[E("allocate(sara, s_a1)", True), E("loses(zara, s_a1)", True),
                      E("loses(ali, s_a1)", True), E("allocate(ali, s_a1)", False),
                      E("allocate(zara, s_a1)", False)],
        focus_goal="allocate(ali, s_a1)")),
    _add(Scenario(
        "tc08_accessible_ineligible", "TC8  Accessible space requested by an ineligible driver",
        "Ali has no accessibility badge and asks for the accessible bay s_a3. "
        "Sara, who holds a badge, is eligible for the same bay.",
        requests=[("ali", "s_a3", 900)],
        expectations=[E("suitable_space(ali, s_a3)", True),
                      E("eligible_for_space(ali, s_a3)", False),
                      E("allocate(ali, s_a3)", False),
                      E("eligible_for_space(sara, s_a3)", True)],
        focus_goal="eligible_for_space(ali, s_a3)")),
    _add(Scenario(
        "tc09_double_booking", "TC9  Conflicting reservations",
        "Dr. Ahmed already holds reservation r2 for s_e3. A second reservation r3 for s_e1 "
        "on the same day is added, then he asks for s_e3.",
        requests=[("ahmed", "s_e3", 800)],
        add=["reservation(r3)", "reserved_by(r3, ahmed)", "reserved_space(r3, s_e1)",
             f"reservation_date(r3, {TODAY})"],
        expectations=[E("double_booked(ahmed)", True), E("can_allocate(ahmed, s_e3)", True),
                      E("allocate(ahmed, s_e3)", False)],
        focus_goal="allocate(ahmed, s_e3)")),
    _add(Scenario(
        "tc10_zone_closed", "TC10  Visitor zone closed at 19:00",
        "Bilal has a valid visitor pass but arrives at 19:00. The visitor zone is open 08:00-17:00.",
        requests=[("bilal", "s_v1", 1900)], hour=19,
        expectations=[E("authorized_driver(bilal)", True), E("zone_open(zone_v)", False),
                      E("allocate(bilal, s_v1)", False)],
        focus_goal="zone_access(bilal, zone_v)")),
    _add(Scenario(
        "tc11_reserved_by_other", "TC11  Reserved space requested by someone else",
        "s_a5 is reserved for Zara today. Ali asks for it.",
        requests=[("ali", "s_a5", 900)],
        expectations=[E("eligible_for_space(ali, s_a5)", True),
                      E("can_allocate(ali, s_a5)", False),
                      E("can_allocate(zara, s_a5)", True)],
        focus_goal="can_allocate(ali, s_a5)")),
    _add(Scenario(
        "tc12_inconsistent_abox", "TC12  Inconsistent data: a student recorded as faculty",
        "A data-entry error also records Ali as faculty. The Horn constraint IC4 and the "
        "DL disjointness axiom Student ⊓ Employee ⊑ ⊥ must both report it.",
        add=["faculty(ali)"],
        expectations=[E("employee(ali)", True), E("student(ali)", True)],
        focus_goal="employee(ali)")),
]


def get(key: str) -> Scenario:
    if key not in SCENARIOS:
        raise KeyError(f"unknown scenario {key!r}; choose from {', '.join(SCENARIOS)}")
    return SCENARIOS[key]
