"""Description Logic: TBox, ABox and a small structural reasoner.

TBox (terminology): concept inclusions C ⊑ D, definitions A ≡ C and
disjointness. ABox (assertions): concept membership Student(ali) and role
assertions hasPermit(ali, p_ali).

Constructors used: ⊓ (and), ⊔ (or), ∃R.C (some), ∀R.C (only), R⁻ (inverse
role), ⊥ (nothing). The reasoner does:

* classification   compute every subsumption between named concepts,
                   including ones nobody wrote down (inferred)
* satisfiability   a concept whose definition needs two disjoint
                   concepts can have no instances
* realization      find every concept an individual belongs to,
                   including defined concepts such as AuthorizedStudent
* ∀-propagation    AccessibleSpace ⊑ ∀allocatedTo.BadgeHolder pushes
                   BadgeHolder onto whoever an accessible bay is given to
* consistency      an individual in two disjoint concepts is a clash

Subsumption is decided structurally (unfold definitions, compare the
conjuncts). This is complete for the EL part of the TBox (⊓, ∃) with an
acyclic TBox, which covers our axioms; ⊔ is handled soundly but not
completely, which is the price of keeping the check polynomial.

The DL works under the open-world assumption: a missing fact means
"unknown", not "false". The Horn rules work under the closed-world
assumption. explain_owa() shows the difference on real individuals.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable, Optional, Union

from ..frames.ontology import build_frames


# ---------------------------------------------------------------------------
# Concept expressions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Atomic:
    name: str

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class And:
    parts: tuple

    def __str__(self) -> str:
        return " ⊓ ".join(_wrap(p) for p in self.parts)


@dataclass(frozen=True)
class Or:
    parts: tuple

    def __str__(self) -> str:
        return " ⊔ ".join(_wrap(p) for p in self.parts)


@dataclass(frozen=True)
class Exists:
    role: str
    filler: "Concept"

    def __str__(self) -> str:
        return f"∃{self.role}.{_wrap(self.filler)}"


@dataclass(frozen=True)
class Forall:
    role: str
    filler: "Concept"

    def __str__(self) -> str:
        return f"∀{self.role}.{_wrap(self.filler)}"


Concept = Union[Atomic, And, Or, Exists, Forall]
BOTTOM = Atomic("⊥")


def _wrap(c: Concept) -> str:
    return f"({c})" if isinstance(c, (And, Or)) else str(c)


def A(name: str) -> Atomic:
    return Atomic(name)


def inverse(role: str) -> str:
    return role[:-1] if role.endswith("⁻") else role + "⁻"


# ---------------------------------------------------------------------------
# Axioms
# ---------------------------------------------------------------------------

@dataclass
class Axiom:
    aid: str
    kind: str                 # "subsumption", "equivalence", "disjoint"
    left: Concept
    right: Concept
    note: str = ""

    def __str__(self) -> str:
        if self.kind == "subsumption":
            return f"{self.left} ⊑ {self.right}"
        if self.kind == "equivalence":
            return f"{self.left} ≡ {self.right}"
        return f"{self.left} ⊓ {self.right} ⊑ ⊥"


def sub(aid, left, right, note=""):
    return Axiom(aid, "subsumption", left, right, note)


def equiv(aid, left, right, note=""):
    return Axiom(aid, "equivalence", left, right, note)


def disjoint(aid, left, right, note=""):
    return Axiom(aid, "disjoint", A(left), A(right), note)


TBOX: list[Axiom] = [
    # People
    sub("T01", A("Student"), A("Person"), "Every student is a person."),
    sub("T02", A("Employee"), A("Person"), "Every employee is a person."),
    sub("T03", A("Faculty"), A("Employee"), "Faculty members are employees."),
    sub("T04", A("Staff"), A("Employee"), "Staff members are employees."),
    sub("T05", A("Visitor"), A("Person"), "Every visitor is a person."),
    sub("T06", A("BadgeHolder"), A("Person"), "Accessibility badge holders are people."),
    sub("T07", A("NonBadgeHolder"), A("Person"), "People without a badge."),
    # Permits
    sub("T08", A("StudentPermit"), A("ParkingPermit"), "A student permit is a parking permit."),
    sub("T09", A("EmployeePermit"), A("ParkingPermit"), "An employee permit is a parking permit."),
    sub("T10", A("VisitorPass"), A("ParkingPermit"), "A visitor pass is a parking permit (in the test data, a one-day one)."),
    sub("T11", A("ValidPermit"), A("ParkingPermit"), "A valid permit is a parking permit."),
    # Spaces and places
    sub("T12", A("AccessibleSpace"), A("ParkingSpace"), "An accessible bay is a parking space."),
    sub("T13", A("EVChargingSpace"), A("ParkingSpace"), "An EV charging bay is a parking space."),
    sub("T14", A("MotorbikeSpace"), A("ParkingSpace"), "A motorbike bay is a parking space."),
    sub("T15", A("ParkingSpace"), Exists("locatedIn", A("ParkingZone")),
        "Every parking space lies in some parking zone (existential restriction)."),
    sub("T16", A("ParkingZone"), Exists("partOf", A("ParkingFacility")),
        "Every zone is part of some parking facility."),
    sub("T17", A("Reservation"), And((Exists("madeBy", A("Person")),
                                      Exists("forSpace", A("ParkingSpace")))),
        "Every reservation is made by some person and is for some parking space."),
    sub("T18", A("Vehicle"), Exists("owns⁻", A("Person")),
        "Every vehicle is owned by some person (owns⁻ is the inverse of owns)."),
    sub("T19", A("AccessibleSpace"), Forall("allocatedTo", A("BadgeHolder")),
        "An accessible bay may only be allocated to badge holders (universal restriction)."),
    sub("T20", A("MotorbikeSpace"), Forall("allocatedTo", Exists("owns", A("Motorbike"))),
        "A motorbike bay may only be allocated to someone who owns a motorbike."),
    sub("T21", A("Motorbike"), A("Vehicle"), "A motorbike is a vehicle."),
    sub("T22", A("ElectricCar"), A("Vehicle"), "An electric car is a vehicle."),
    sub("T23", A("Car"), A("Vehicle"), "A (petrol) car is a vehicle."),
    # Defined concepts (necessary and sufficient conditions)
    equiv("T24", A("ValidPermitHolder"), And((A("Person"), Exists("hasPermit", A("ValidPermit")))),
          "A valid-permit holder is exactly a person with at least one valid permit."),
    equiv("T25", A("AuthorizedStudent"),
          And((A("Student"), Exists("hasPermit", And((A("ValidPermit"), A("StudentPermit")))))),
          "An authorized student is a student holding a valid student permit."),
    equiv("T26", A("AuthorizedEmployee"),
          And((A("Employee"), Exists("hasPermit", And((A("ValidPermit"), A("EmployeePermit")))))),
          "An authorized employee is an employee holding a valid employee permit."),
    equiv("T27", A("AuthorizedVisitor"),
          And((A("Visitor"), Exists("hasPermit", And((A("ValidPermit"), A("VisitorPass")))))),
          "An authorized visitor is a visitor holding a valid visitor pass."),
    equiv("T28", A("AuthorizedDriver"),
          Or((A("AuthorizedStudent"), A("AuthorizedEmployee"), A("AuthorizedVisitor"))),
          "An authorized driver is an authorized student, employee or visitor "
          "(matches Horn rules R07-R11)."),
    # Disjointness
    disjoint("D01", "Student", "Employee", "Nobody is both a student and an employee."),
    disjoint("D02", "Student", "Visitor", "Nobody is both a student and a visitor."),
    disjoint("D03", "Employee", "Visitor", "Nobody is both an employee and a visitor."),
    disjoint("D04", "Faculty", "Staff", "Nobody is both faculty and staff."),
    disjoint("D05", "BadgeHolder", "NonBadgeHolder", "Either a badge holder or not, never both."),
    disjoint("D06", "StudentPermit", "EmployeePermit", "A permit has exactly one class."),
    disjoint("D07", "StudentPermit", "VisitorPass", ""),
    disjoint("D08", "EmployeePermit", "VisitorPass", ""),
    disjoint("D09", "AccessibleSpace", "EVChargingSpace", "A bay has exactly one type."),
    disjoint("D10", "AccessibleSpace", "MotorbikeSpace", ""),
    disjoint("D11", "EVChargingSpace", "MotorbikeSpace", ""),
    disjoint("D12", "Motorbike", "ElectricCar", "A vehicle has exactly one type."),
    disjoint("D13", "Motorbike", "Car", ""),
    disjoint("D14", "Car", "ElectricCar", ""),
    disjoint("D15", "Person", "Vehicle", "People and vehicles are different kinds of thing."),
    disjoint("D16", "Person", "ParkingSpace", ""),
    disjoint("D17", "ParkingSpace", "ParkingZone", "A bay is not a zone."),
]

ROLES = {
    "owns": "Person → Vehicle (Horn predicate owns/2)",
    "hasPermit": "Person → ParkingPermit (has_permit/2)",
    "locatedIn": "ParkingSpace → ParkingZone (located_in/2)",
    "partOf": "ParkingZone → ParkingFacility (part_of/2)",
    "madeBy": "Reservation → Person (reserved_by/2)",
    "forSpace": "Reservation → ParkingSpace (reserved_space/2)",
    "allocatedTo": "ParkingSpace → Person (allocate/2 read right to left)",
}

# Horn predicate -> (DL role, swap arguments?)
ROLE_FROM_PREDICATE = {"owns": ("owns", False), "has_permit": ("hasPermit", False),
                       "located_in": ("locatedIn", False), "part_of": ("partOf", False),
                       "reserved_by": ("madeBy", False), "reserved_space": ("forSpace", False),
                       "allocate": ("allocatedTo", True)}

# Horn fact pattern -> DL concept membership
CONCEPT_FROM_FACT = {
    ("permit_valid",): "ValidPermit",
    ("permit_class", "student_permit"): "StudentPermit",
    ("permit_class", "employee_permit"): "EmployeePermit",
    ("permit_class", "visitor_pass"): "VisitorPass",
    ("accessibility_badge", "yes"): "BadgeHolder",
    ("accessibility_badge", "no"): "NonBadgeHolder",
    ("vehicle_type", "car"): "Car",
    ("vehicle_type", "electric_car"): "ElectricCar",
    ("vehicle_type", "motorbike"): "Motorbike",
}


@dataclass
class ABox:
    concepts: dict[str, set[str]]           # individual -> asserted concept names
    roles: set[tuple[str, str, str]]        # (role, subject, object)

    def assertions(self) -> list[str]:
        out = [f"{c}({i})" for i in sorted(self.concepts) for c in sorted(self.concepts[i])]
        out += [f"{r}({a}, {b})" for r, a, b in sorted(self.roles)]
        return out


def build_abox(facts: Optional[Iterable[tuple]] = None) -> ABox:
    """ABox from the frames plus (optionally) facts from the Horn closure.

    Frames give each individual's most specific class (s_a3: AccessibleSpace).
    Facts add memberships the rules derived (ValidPermit) and any unary class
    fact such as faculty(ali), so a data error in the logic layer also reaches
    the DL layer.
    """
    fs = build_frames()
    predicate_to_class = {f.predicate: f.name for f in fs.classes() if f.predicate}
    concepts: dict[str, set[str]] = {}
    roles: set[tuple[str, str, str]] = set()
    for inst in fs.instances():
        concepts.setdefault(inst.name, set()).add(inst.isa)
    for fact in facts if facts is not None else fs.to_facts():
        pred, args = fact[0], fact[1:]
        if len(args) == 1 and pred in predicate_to_class:
            concepts.setdefault(args[0], set()).add(predicate_to_class[pred])
        if (pred,) in CONCEPT_FROM_FACT and len(args) == 1:
            concepts.setdefault(args[0], set()).add(CONCEPT_FROM_FACT[(pred,)])
        if len(args) == 2 and (pred, args[1]) in CONCEPT_FROM_FACT:
            concepts.setdefault(args[0], set()).add(CONCEPT_FROM_FACT[(pred, args[1])])
        if pred in ROLE_FROM_PREDICATE and len(args) == 2:
            role, swap = ROLE_FROM_PREDICATE[pred]
            a, b = (args[1], args[0]) if swap else args
            roles.add((role, a, b))
    # A class name can be implied by a more specific one; keep only the told ones.
    return ABox(concepts, roles)


# ---------------------------------------------------------------------------
# Reasoner
# ---------------------------------------------------------------------------

@dataclass
class Clash:
    individual: str
    first: str
    second: str
    axiom: str

    def __str__(self) -> str:
        return (f"{self.individual} is both {self.first} and {self.second}, "
                f"which {self.axiom} declares disjoint")


class DLReasoner:
    def __init__(self, tbox: list[Axiom] = TBOX):
        self.tbox = tbox
        self.definitions = {ax.left.name: ax.right for ax in tbox if ax.kind == "equivalence"}
        self.told: dict[str, list[Concept]] = {}
        for ax in tbox:
            if ax.kind == "subsumption" and isinstance(ax.left, Atomic):
                self.told.setdefault(ax.left.name, []).append(ax.right)
        self.disjoint_pairs = {(ax.left.name, ax.right.name): ax.aid
                               for ax in tbox if ax.kind == "disjoint"}

    # ----- concept names ----------------------------------------------
    def concept_names(self) -> list[str]:
        names: list[str] = []

        def visit(c):
            if isinstance(c, Atomic):
                if c.name not in names and c.name != "⊥":
                    names.append(c.name)
            elif isinstance(c, (And, Or)):
                for p in c.parts:
                    visit(p)
            else:
                visit(c.filler)

        for ax in self.tbox:
            visit(ax.left)
            visit(ax.right)
        return names

    # ----- expansion -----------------------------------------------------
    def expand(self, concept: Concept) -> frozenset:
        """All conjuncts implied by a concept: atomic names (with every told
        superclass) plus ∃ / ∀ / ⊔ parts."""
        out: set = set()
        stack = [concept]
        while stack:
            c = stack.pop()
            if c in out:
                continue
            if isinstance(c, Atomic):
                out.add(c)
                if c.name in self.definitions:
                    stack.append(self.definitions[c.name])
                stack.extend(self.told.get(c.name, []))
            elif isinstance(c, And):
                stack.extend(c.parts)
            else:
                out.add(c)
        return frozenset(out)

    def atomics(self, concept: Concept) -> set[str]:
        return {c.name for c in self.expand(concept) if isinstance(c, Atomic)}

    # ----- subsumption -----------------------------------------------------
    def subsumes(self, sub_c: Concept, sup_c: Concept) -> bool:
        """True if sub_c ⊑ sup_c follows from the TBox (structural test)."""
        if not self.satisfiable(sub_c):
            return True                       # ⊥ is subsumed by everything
        have = self.expand(sub_c)
        return self._covered(have, sup_c)

    def _covered(self, have: frozenset, need: Concept) -> bool:
        if isinstance(need, Atomic):
            if Atomic(need.name) in have:
                return True
            if need.name in self.definitions:
                return self._covered(have, self.definitions[need.name])
            return False
        if isinstance(need, And):
            return all(self._covered(have, p) for p in need.parts)
        if isinstance(need, Or):
            # sound but incomplete: one disjunct must be covered on its own
            if need in have:
                return True
            return any(self._covered(have, p) for p in need.parts)
        if isinstance(need, Exists):
            return any(isinstance(h, Exists) and h.role == need.role
                       and self.subsumes(h.filler, need.filler) for h in have)
        if isinstance(need, Forall):
            return any(isinstance(h, Forall) and h.role == need.role
                       and self.subsumes(h.filler, need.filler) for h in have)
        return False

    # ----- disjointness and satisfiability ---------------------------------
    def disjoint_axiom(self, a: str, b: str) -> Optional[str]:
        ups_a = self.atomics(Atomic(a))
        ups_b = self.atomics(Atomic(b))
        for x in ups_a:
            for y in ups_b:
                aid = self.disjoint_pairs.get((x, y)) or self.disjoint_pairs.get((y, x))
                if aid:
                    return aid
        return None

    def satisfiable(self, concept: Concept) -> bool:
        names = {c.name for c in self._expand_raw(concept) if isinstance(c, Atomic)}
        if "⊥" in names:
            return False
        for x, y in combinations(sorted(names), 2):
            if (x, y) in self.disjoint_pairs or (y, x) in self.disjoint_pairs:
                return False
        return True

    def _expand_raw(self, concept: Concept) -> frozenset:
        out: set = set()
        stack = [concept]
        while stack:
            c = stack.pop()
            if c in out:
                continue
            if isinstance(c, Atomic):
                out.add(c)
                if c.name in self.definitions:
                    stack.append(self.definitions[c.name])
                stack.extend(self.told.get(c.name, []))
            elif isinstance(c, And):
                stack.extend(c.parts)
        return frozenset(out)

    # ----- classification ----------------------------------------------------
    def classify(self) -> list[tuple[str, str, bool]]:
        """Every (sub, sup, inferred) with sub ⊑ sup between named concepts.

        inferred is True when the subsumption was not written as an axiom and
        is not just a chain of written atomic axioms, i.e. the reasoner had to
        compare definitions to find it.
        """
        names = self.concept_names()
        told_closure = {n: self._told_atomic_closure(n) for n in names}
        result = []
        for a in names:
            for b in names:
                if a != b and self.subsumes(Atomic(a), Atomic(b)):
                    result.append((a, b, b not in told_closure[a]))
        return result

    def _told_atomic_closure(self, name: str) -> set[str]:
        seen, stack = set(), [name]
        while stack:
            n = stack.pop()
            for sup in self.told.get(n, []):
                if isinstance(sup, Atomic) and sup.name not in seen:
                    seen.add(sup.name)
                    stack.append(sup.name)
        return seen

    def direct_parents(self) -> dict[str, list[str]]:
        """Hasse diagram of the classified hierarchy (for drawing)."""
        subs = {}
        for a, b, _ in self.classify():
            subs.setdefault(a, set()).add(b)
        parents = {}
        for a, sups in subs.items():
            parents[a] = sorted(b for b in sups
                                if not any(b in subs.get(c, set()) for c in sups if c != b))
        return parents

    # ----- ABox reasoning --------------------------------------------------
    def realize(self, abox: ABox) -> dict[str, set[str]]:
        """Every named concept each individual belongs to."""
        types: dict[str, set] = {i: set() for i in abox.concepts}
        for _, a, b in abox.roles:
            types.setdefault(a, set())
            types.setdefault(b, set())
        for ind, names in abox.concepts.items():
            for n in names:
                types[ind] |= self.expand(Atomic(n))
        defined = [n for n in self.concept_names() if n in self.definitions]
        changed = True
        while changed:
            changed = False
            # ∀-propagation: C ⊑ ∀R.D, C(a), R(a,b)  =>  D(b)
            for ind in list(types):
                for c in list(types[ind]):
                    if isinstance(c, Forall):
                        for filler in self._fillers(abox, ind, c.role):
                            new = self.expand(c.filler) - types[filler]
                            if new:
                                types[filler] |= new
                                changed = True
            # recognise defined concepts
            for ind in types:
                for name in defined:
                    if Atomic(name) not in types[ind] and self._instance(abox, types, ind,
                                                                         Atomic(name)):
                        types[ind] |= self.expand(Atomic(name))
                        changed = True
        return {i: {c.name for c in t if isinstance(c, Atomic)} for i, t in types.items()}

    def _fillers(self, abox: ABox, ind: str, role: str) -> list[str]:
        if role.endswith("⁻"):
            base = role[:-1]
            return [a for r, a, b in abox.roles if r == base and b == ind]
        return [b for r, a, b in abox.roles if r == role and a == ind]

    def _instance(self, abox: ABox, types, ind: str, concept: Concept) -> bool:
        if isinstance(concept, Atomic):
            if Atomic(concept.name) in types.get(ind, ()):
                return True
            if concept.name in self.definitions:
                return self._instance(abox, types, ind, self.definitions[concept.name])
            return False
        if isinstance(concept, And):
            return all(self._instance(abox, types, ind, p) for p in concept.parts)
        if isinstance(concept, Or):
            return any(self._instance(abox, types, ind, p) for p in concept.parts)
        if isinstance(concept, Exists):
            return any(self._instance(abox, types, j, concept.filler)
                       for j in self._fillers(abox, ind, concept.role))
        if isinstance(concept, Forall):
            # Under the open-world assumption ∀R.C can only be confirmed for
            # an individual already asserted to satisfy it.
            return concept in types.get(ind, ())
        return False

    def check_consistency(self, abox: ABox) -> list[Clash]:
        clashes = []
        for ind, names in self.realize(abox).items():
            for x, y in combinations(sorted(names), 2):
                aid = self.disjoint_pairs.get((x, y)) or self.disjoint_pairs.get((y, x))
                if aid:
                    clashes.append(Clash(ind, x, y, aid))
        return clashes

    def open_world_notes(self, abox: ABox) -> list[str]:
        """∃-restrictions with no known filler. Under OWA these are not errors."""
        notes = []
        realized = self.realize(abox)
        for ind, names in sorted(realized.items()):
            for name in sorted(names):
                for c in self.told.get(name, []):
                    parts = c.parts if isinstance(c, And) else (c,)
                    for p in parts:
                        if isinstance(p, Exists):
                            fillers = [j for j in self._fillers(abox, ind, p.role)
                                       if self._instance(abox, {k: {Atomic(n) for n in v}
                                                                for k, v in realized.items()},
                                                         j, p.filler)]
                            if not fillers:
                                notes.append(f"{ind} is a {name}, so some {p.role}-filler of type "
                                             f"{p.filler} must exist, but none is recorded. "
                                             "Under OWA this is unknown, not a contradiction.")
        return notes


def explain_owa(realized: dict[str, set[str]], individual: str, concept: str) -> str:
    """Contrast DL (open world) with Horn/Prolog (closed world) for one query."""
    if concept in realized.get(individual, set()):
        return f"DL: {concept}({individual}) is entailed."
    return (f"DL: {concept}({individual}) is not entailed, and neither is its negation; "
            f"the DL reasoner answers 'unknown'. The Horn engine, which assumes that "
            f"anything it cannot prove is false, answers 'no'.")
