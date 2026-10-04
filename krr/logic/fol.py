"""First-order logic: formulas, their meaning, and a finite model checker.

Two sets of FOL formulas exist in the project:

1. Every Horn rule R01-R28 has an FOL reading, produced by Rule.to_fol():
       head :- b1, ..., bn.    becomes    ∀x1...∀xk ((b1 ∧ ... ∧ bn) → head)
2. The statements below (F01-F12) use FOL features that Horn clauses lack
   or only partly have: ∃ in the conclusion, ∨ in the conclusion, equality,
   classical negation. They state facts about the domain the rules must
   respect.

The model checker evaluates a formula over the finite model produced by
forward chaining (domain = every constant in the closure). It shows, for
example, that the closure satisfies the safety property F07 "accessible
bays only go to badge holders", which no single rule states directly.
Checking a formula in one finite model is easy. Deciding whether a formula
follows from the rules in every model (FOL entailment) is undecidable in
general, which is the tractability problem the report discusses. Even
here, a quantifier over the whole domain multiplies the work by the domain
size, so nested quantifiers are restricted to values that occur in a
guarding atom (guarded quantification).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Union


# ----- formula syntax --------------------------------------------------------

@dataclass(frozen=True)
class Pred:
    name: str
    args: tuple

    def __str__(self) -> str:
        return f"{self.name}({', '.join(map(str, self.args))})" if self.args else self.name


@dataclass(frozen=True)
class Eq:
    left: str
    right: str

    def __str__(self) -> str:
        return f"{self.left} = {self.right}"


@dataclass(frozen=True)
class Cmp:
    op: str          # ">=", "=<", ">" or "<"
    left: str
    right: str

    def __str__(self) -> str:
        return f"{self.left} {dict([('>=', '≥'), ('=<', '≤'), ('>', '>'), ('<', '<')])[self.op]} {self.right}"


@dataclass(frozen=True)
class Not:
    body: "Formula"

    def __str__(self) -> str:
        return f"¬{_wrap(self.body)}"


@dataclass(frozen=True)
class AndF:
    parts: tuple

    def __str__(self) -> str:
        return " ∧ ".join(_wrap(p) for p in self.parts)


@dataclass(frozen=True)
class OrF:
    parts: tuple

    def __str__(self) -> str:
        return " ∨ ".join(_wrap(p) for p in self.parts)


@dataclass(frozen=True)
class Implies:
    left: "Formula"
    right: "Formula"

    def __str__(self) -> str:
        return f"{_wrap(self.left)} → {_wrap(self.right)}"


@dataclass(frozen=True)
class ForAll:
    var: str
    body: "Formula"

    def __str__(self) -> str:
        return f"∀{self.var} {_wrap_q(self.body)}"


@dataclass(frozen=True)
class Exists:
    var: str
    body: "Formula"

    def __str__(self) -> str:
        return f"∃{self.var} {_wrap_q(self.body)}"


Formula = Union[Pred, Eq, Cmp, Not, AndF, OrF, Implies, ForAll, Exists]


def _wrap(f) -> str:
    return f"({f})" if isinstance(f, (AndF, OrF, Implies)) else str(f)


def _wrap_q(f) -> str:
    return str(f) if isinstance(f, (ForAll, Exists, Pred, Not)) else f"({f})"


def P(name: str, *args: str) -> Pred:
    return Pred(name, tuple(args))


def forall(vars_: str, body) -> Formula:
    for v in reversed(vars_.split()):
        body = ForAll(v, body)
    return body


def exists(vars_: str, body) -> Formula:
    for v in reversed(vars_.split()):
        body = Exists(v, body)
    return body


# ----- model checking ----------------------------------------------------------

class Model:
    """A finite Herbrand-style model: a set of ground atoms and their constants."""

    def __init__(self, facts: Iterable[tuple]):
        self.facts = set(facts)
        self.domain = sorted({t for f in self.facts for t in f[1:]}, key=str)
        self.by_name: dict[str, list[tuple]] = {}
        for f in self.facts:
            self.by_name.setdefault(f[0], []).append(f)

    def _range(self, var: str, body) -> list:
        """Values worth trying for a quantified variable (guarded quantification).

        In ∀x (p(x) ∧ ... → φ) any x that is not in a p-fact makes the
        antecedent false, so the implication is true for it and it can be
        skipped. The same holds for ∃x (p(x) ∧ ...). The answer is identical
        to trying the whole domain; it only avoids useless work.
        """
        while isinstance(body, (ForAll, Exists)):
            body = body.body
        if isinstance(body, Implies):
            guards = _conjuncts(body.left)
        elif isinstance(body, Not) and isinstance(body.body, AndF):
            guards = list(body.body.parts)
        else:
            guards = _conjuncts(body)
        for g in guards:
            if isinstance(g, Pred) and var in g.args:
                i = g.args.index(var) + 1
                return sorted({f[i] for f in self.by_name.get(g.name, [])}, key=str)
        return self.domain

    def holds(self, formula: Formula, env: dict | None = None) -> bool:
        env = env or {}

        def val(t):
            return env.get(t, t)

        f = formula
        if isinstance(f, Pred):
            return (f.name, *(_const(val(a)) for a in f.args)) in self.facts
        if isinstance(f, Eq):
            return val(f.left) == val(f.right)
        if isinstance(f, Cmp):
            a, b = _const(val(f.left)), _const(val(f.right))
            if not (isinstance(a, int) and isinstance(b, int)):
                return False
            return {">=": a >= b, "=<": a <= b, ">": a > b, "<": a < b}[f.op]
        if isinstance(f, Not):
            return not self.holds(f.body, env)
        if isinstance(f, AndF):
            return all(self.holds(p, env) for p in f.parts)
        if isinstance(f, OrF):
            return any(self.holds(p, env) for p in f.parts)
        if isinstance(f, Implies):
            return (not self.holds(f.left, env)) or self.holds(f.right, env)
        if isinstance(f, ForAll):
            return all(self.holds(f.body, {**env, f.var: d}) for d in self._range(f.var, f.body))
        if isinstance(f, Exists):
            return any(self.holds(f.body, {**env, f.var: d}) for d in self._range(f.var, f.body))
        raise TypeError(f"not a formula: {f!r}")

    def counterexample(self, formula: Formula) -> dict | None:
        """For ∀x1..xn φ, return one assignment that falsifies φ (if any)."""
        vars_, body = [], formula
        while isinstance(body, ForAll):
            vars_.append(body.var)
            body = body.body

        def search(i, env):
            if i == len(vars_):
                return None if self.holds(body, env) else dict(env)
            for d in self.domain:
                found = search(i + 1, {**env, vars_[i]: d})
                if found:
                    return found
            return None

        return search(0, {})


def _conjuncts(f) -> list:
    return list(f.parts) if isinstance(f, AndF) else [f]


def _const(term):
    if isinstance(term, str) and term.lstrip("-").isdigit():
        return int(term)
    return term


# ----- FOL statements of the domain --------------------------------------------

@dataclass
class Statement:
    sid: str
    formula: Formula
    english: str
    horn: str           # how (or whether) it is captured in the Horn KB

    @property
    def text(self) -> str:
        return str(self.formula)


STATEMENTS: list[Statement] = [
    Statement("F01",
              forall("s", Implies(P("parking_space", "s"),
                                  exists("z", AndF((P("parking_zone", "z"),
                                                    P("located_in", "s", "z")))))),
              "Every parking space lies in some parking zone.",
              "Not Horn: ∃ in the conclusion. Mirrors DL axiom T15."),
    Statement("F02",
              forall("s z1 z2", Implies(AndF((P("located_in", "s", "z1"),
                                              P("located_in", "s", "z2"))),
                                        Eq("z1", "z2"))),
              "A space lies in at most one zone (located_in is functional).",
              "Not Horn without equality; enforced by the frame facet cardinality=single."),
    Statement("F03",
              forall("x", Implies(P("person", "x"),
                                  OrF((P("student", "x"), P("employee", "x"),
                                       P("visitor", "x"))))),
              "Every person is a student, an employee or a visitor.",
              "Not Horn: three positive literals in the conclusion (covering axiom)."),
    Statement("F04",
              forall("x", Not(AndF((P("student", "x"), P("employee", "x"))))),
              "Nobody is both a student and an employee.",
              "Horn denial clause IC4; DL axiom D01."),
    Statement("F05",
              forall("x y s", Implies(AndF((P("allocate", "x", "s"), P("allocate", "y", "s"))),
                                      Eq("x", "y"))),
              "A space is allocated to at most one person.",
              "Horn denial clause IC1 (uses ≠ instead of =)."),
    Statement("F06",
              forall("x s", Implies(P("allocate", "x", "s"),
                                    Not(P("space_status", "s", "occupied")))),
              "An occupied space is never allocated.",
              "Horn denial clause IC3."),
    Statement("F07",
              forall("x s", Implies(AndF((P("allocate", "x", "s"),
                                          P("space_type", "s", "accessible"))),
                                    P("accessibility_badge", "x", "yes"))),
              "Whoever is allocated an accessible bay holds a badge.",
              "Consequence of R16 and R28 (a safety property, checked on the model). "
              "Same meaning as DL axiom T19."),
    Statement("F08",
              forall("x", Implies(P("authorized_driver", "x"),
                                  exists("p", AndF((P("has_permit", "x", "p"),
                                                    P("permit_valid", "p")))))),
              "Every authorized driver holds at least one valid permit.",
              "Follows from R06-R11; the ∃ cannot be written as a Horn conclusion."),
    Statement("F09",
              exists("s", AndF((P("located_in", "s", "zone_a"), P("space_free", "s")))),
              "There is at least one free space in the student zone.",
              "An existential query; backward chaining answers it with "
              "?- located_in(S, zone_a), space_free(S)."),
    Statement("F10",
              forall("x", Implies(AndF((P("visitor", "x"),
                                        Not(exists("p", P("has_permit", "x", "p"))))),
                                  Not(P("authorized_driver", "x")))),
              "A visitor with no permit or pass is not an authorized driver.",
              "Not derivable in classical FOL from R01-R28 alone; true under the "
              "closed-world assumption the Horn engine uses (negation as failure)."),
    Statement("F11",
              forall("x s", Implies(P("allocate", "x", "s"),
                                    exists("t", P("requests", "x", "s", "t")))),
              "Every allocation answers a request.",
              "Follows from R28, whose body starts with requests(X, S, T)."),
    Statement("F12",
              forall("p", Implies(P("permit_valid", "p"),
                                  exists("b e d", AndF((P("permit_start", "p", "b"),
                                                        P("permit_expiry", "p", "e"),
                                                        P("current_date", "d"),
                                                        Cmp("=<", "b", "d"),
                                                        Cmp(">=", "e", "d")))))),
              "A valid permit is in force today: it has started and has not expired.",
              "The 'only if' half of R06 (Clark completion of permit_valid)."),
]


def check_statements(facts: Iterable[tuple]) -> list[tuple[Statement, bool, dict | None]]:
    """Evaluate every statement on the model given by the facts."""
    model = Model(facts)
    out = []
    for st in STATEMENTS:
        ok = model.holds(st.formula)
        out.append((st, ok, None if ok else model.counterexample(st.formula)))
    return out
