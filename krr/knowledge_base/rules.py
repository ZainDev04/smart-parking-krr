"""The rule base: every Horn clause the system reasons with.

This file is the single source of truth. The forward chainer, the backward
chainer, the explanation module, the Prolog export, the FOL listing and
the report all read RULES and CONSTRAINTS from here.

Notation (Prolog syntax):
    head :- b1, b2, ..., bn.     "head is true if b1 and b2 and ... bn are true"
    X, Owner, ...                variables (uppercase first letter)
    ali, s_a1, 20261002          constants
    E >= D, X \\= Y              built-in comparisons, evaluated, never stored
    not p(X)                     negation as failure, only in stratum 2 (R28)
"""

from __future__ import annotations

from ..core.kb import Constraint, Rule

_R = Rule.parse

RULES: list[Rule] = [
    # ----- A. Class hierarchy (the DL subsumption axioms as rules) -------
    _R("R01", "person(X) :- student(X).",
       "Every student is a person.",
       "Horn form of the DL axiom Student ⊑ Person.", "A. Class hierarchy"),
    _R("R02", "person(X) :- employee(X).",
       "Every employee is a person.",
       "Horn form of Employee ⊑ Person.", "A. Class hierarchy"),
    _R("R03", "person(X) :- visitor(X).",
       "Every visitor is a person.",
       "Horn form of Visitor ⊑ Person.", "A. Class hierarchy"),
    _R("R04", "employee(X) :- faculty(X).",
       "Every faculty member is an employee.",
       "Horn form of Faculty ⊑ Employee. Faculty and staff share the employee rules.",
       "A. Class hierarchy"),
    _R("R05", "employee(X) :- staff(X).",
       "Every staff member is an employee.",
       "Horn form of Staff ⊑ Employee.", "A. Class hierarchy"),

    # ----- B. Permits and authorization ---------------------------------
    _R("R06", "permit_valid(P) :- permit_status(P, active), permit_start(P, B), "
              "permit_expiry(P, E), current_date(D), B =< D, E >= D.",
       "A permit is valid if its status is active and today lies between its start date "
       "and its expiry date.",
       "Expired, not-yet-started or suspended permits never satisfy this rule, so they can "
       "never authorize parking. B =< D and E >= D are built-in comparisons on YYYYMMDD "
       "integers. A one-day visitor pass has B = E.",
       "B. Permits and authorization"),
    _R("R07", "permit_matches_role(X, P) :- has_permit(X, P), permit_class(P, student_permit), "
              "student(X).",
       "A student permit only counts when its holder is a student.",
       "Stops a permit being used by someone of the wrong category.",
       "B. Permits and authorization"),
    _R("R08", "permit_matches_role(X, P) :- has_permit(X, P), permit_class(P, employee_permit), "
              "employee(X).",
       "An employee permit only counts when its holder is faculty or staff.",
       "employee(X) is itself derived by R04 or R05.", "B. Permits and authorization"),
    _R("R09", "permit_matches_role(X, P) :- has_permit(X, P), permit_class(P, visitor_pass), "
              "visitor(X).",
       "A visitor needs a visitor pass; the pass is the visitor's authorization.",
       "A visitor with no pass has no has_permit fact, so this rule cannot fire for them.",
       "B. Permits and authorization"),
    _R("R10", "authorized(X, P) :- permit_matches_role(X, P), permit_valid(P).",
       "A person is authorized by a permit that matches their role and is valid.",
       "Joins the role check (R07-R09) with the validity check (R06).",
       "B. Permits and authorization"),
    _R("R11", "authorized_driver(X) :- authorized(X, P).",
       "Anyone authorized by at least one permit is an authorized driver.",
       "P occurs only in the body, so logically it is existential: "
       "∀x (∃p authorized(x, p) → authorized_driver(x)).",
       "B. Permits and authorization"),

    # ----- C. Zones and time ----------------------------------------------
    _R("R12", "zone_open(Z) :- zone_opens(Z, O), zone_closes(Z, C), current_hour(H), "
              "H >= O, H < C.",
       "A zone is open when the current hour is inside its opening hours.",
       "The time restriction of each zone. The visitor zone closes at 17:00.",
       "C. Zones and time"),
    _R("R13", "zone_access(X, Z) :- authorized(X, P), permit_class(P, C), grants(C, T), "
              "zone_type(Z, T), zone_open(Z).",
       "An authorized person may enter a zone if their permit class grants that zone type "
       "and the zone is open.",
       "Students reach only student zones, employees only employee zones, visitors only the "
       "visitor zone, as listed in the grants/2 policy table.",
       "C. Zones and time"),

    # ----- D. Space suitability and eligibility ---------------------------
    _R("R14", "suitable_space(X, S) :- zone_access(X, Z), located_in(S, Z), owns(X, V), "
              "vehicle_type(V, VT), space_type(S, ST), fits(VT, ST).",
       "A space suits a person if it is in a zone they may enter and their vehicle fits the bay.",
       "A motorbike never fits a car bay and a car never fits a motorbike bay (fits/2 table).",
       "D. Suitability and eligibility"),
    _R("R15", "eligible_for_space(X, S) :- suitable_space(X, S), space_type(S, T), open_type(T).",
       "A suitable standard, EV or motorbike bay needs nothing more.",
       "open_type/1 lists the bay types with no personal requirement.",
       "D. Suitability and eligibility"),
    _R("R16", "eligible_for_space(X, S) :- suitable_space(X, S), space_type(S, accessible), "
              "accessibility_badge(X, yes).",
       "An accessible bay is only for a person who holds an accessibility badge.",
       "Together R15 and R16 cover every bay type; an accessible bay has no rule that "
       "ignores the badge.", "D. Suitability and eligibility"),

    # ----- E. Availability and allocation ---------------------------------
    _R("R17", "space_free(S) :- space_status(S, vacant).",
       "A vacant space is free.",
       "Occupied and reserved spaces are not free.", "E. Availability and allocation"),
    _R("R18", "holds_reservation(X, S) :- reserved_by(R, X), reserved_space(R, S), "
              "reservation_date(R, D), current_date(D).",
       "A person holds a reservation for a space if they made a reservation for it for today.",
       "Reservation R is an object (reified relation) with three binary links.",
       "E. Availability and allocation"),
    _R("R19", "can_allocate(X, S) :- eligible_for_space(X, S), space_free(S).",
       "A free space can be allocated to any person eligible for it.",
       "Occupied spaces never satisfy space_free, so they are never allocated.",
       "E. Availability and allocation"),
    _R("R20", "can_allocate(X, S) :- eligible_for_space(X, S), space_status(S, reserved), "
              "holds_reservation(X, S).",
       "A reserved space can be allocated only to the person holding today's reservation.",
       "Nobody else can be allocated a reserved space because no rule allows it.",
       "E. Availability and allocation"),

    # ----- F. Priority ------------------------------------------------------
    _R("R21", "priority(X, 3) :- person(X), accessibility_badge(X, yes).",
       "Badge holders have priority 3 (highest).",
       "accessibility_badge has exactly one value per person (frame default 'no'), so the "
       "priority rules never give one person two levels.", "F. Priority"),
    _R("R22", "priority(X, 2) :- employee(X), accessibility_badge(X, no).",
       "Faculty and staff without a badge have priority 2.", "", "F. Priority"),
    _R("R23", "priority(X, 1) :- student(X), accessibility_badge(X, no).",
       "Students without a badge have priority 1.", "", "F. Priority"),
    _R("R24", "priority(X, 1) :- visitor(X), accessibility_badge(X, no).",
       "Visitors without a badge have priority 1.", "", "F. Priority"),

    # ----- G. Conflicts ------------------------------------------------------
    _R("R25", "loses(Y, S) :- requests(Y, S, TY), requests(X, S, TX), X \\= Y, "
              "can_allocate(X, S), priority(X, PX), priority(Y, PY), PX > PY.",
       "A requester loses a space to another eligible requester with higher priority.",
       "Only competitors who could actually get the space (can_allocate) count. "
       "An ineligible requester cannot block anyone.", "G. Conflicts"),
    _R("R26", "loses(Y, S) :- requests(Y, S, TY), requests(X, S, TX), X \\= Y, "
              "can_allocate(X, S), priority(X, P), priority(Y, P), TX < TY.",
       "With equal priority, the earlier request wins (first come, first served).",
       "Request times are unique gate timestamps, so equal priority and equal time "
       "cannot happen; constraint IC1 would report it if it did.", "G. Conflicts"),
    _R("R27", "double_booked(X) :- reserved_by(R1, X), reserved_by(R2, X), R1 \\= R2, "
              "reservation_date(R1, D), reservation_date(R2, D).",
       "A person holding two different reservations for the same day is double-booked.",
       "Detects the policy violation 'one person, one reservation per day'.",
       "G. Conflicts"),

    # ----- H. Final decision (stratum 2: negation as failure) -----------------
    _R("R28", "allocate(X, S) :- requests(X, S, T), can_allocate(X, S), not loses(X, S), "
              "not double_booked(X).",
       "Allocate the requested space if it can be allocated, the requester loses no conflict "
       "for it and is not double-booked.",
       "The only rule with 'not'. It runs after loses/2 and double_booked/1 are fully "
       "computed (stratified negation), so 'not' means 'cannot be derived'.",
       "H. Decision"),
]


# Denial clauses ("goal clauses" with an empty head). If a body is ever
# satisfied, the knowledge base is inconsistent and the system reports it.
CONSTRAINTS: list[Constraint] = [
    Constraint.parse("IC1", ":- allocate(X, S), allocate(Y, S), X \\= Y.",
                     "One space is never allocated to two people."),
    Constraint.parse("IC2", ":- allocate(X, S1), allocate(X, S2), S1 \\= S2.",
                     "One person is never allocated two spaces."),
    Constraint.parse("IC3", ":- allocate(X, S), space_status(S, occupied).",
                     "An occupied space is never allocated."),
    Constraint.parse("IC4", ":- student(X), employee(X).",
                     "Nobody is both a student and an employee (Student ⊓ Employee ⊑ ⊥)."),
    Constraint.parse("IC5", ":- student(X), visitor(X).",
                     "Nobody is both a student and a visitor."),
    Constraint.parse("IC6", ":- employee(X), visitor(X).",
                     "Nobody is both an employee and a visitor."),
    Constraint.parse("IC7", ":- faculty(X), staff(X).",
                     "Nobody is both faculty and staff."),
]


RULE_GROUPS = sorted({r.group for r in RULES})
