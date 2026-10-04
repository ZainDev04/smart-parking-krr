"""Rules, integrity constraints and the knowledge base container.

The same KnowledgeBase object is handed to the forward chainer, the backward
chainer, the explanation module and the Prolog exporter, so every engine
works from exactly the same facts and rules.
"""

from __future__ import annotations

import itertools
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Optional

from .terms import (Atom, Literal, ParseError, Substitution, evaluate_builtin,
                    format_atom, is_ground, is_var, parse_atom, parse_clause,
                    substitute, unify)


@dataclass
class Rule:
    """A definite Horn clause  head :- body  (body may use 'not' in stratum 2)."""

    rid: str
    head: Atom
    body: tuple[Literal, ...]
    text: str
    natural: str = ""          # the rule in plain English
    explanation: str = ""      # why the rule exists / how to read it
    group: str = ""
    stratum: int = 0           # filled in by KnowledgeBase.stratify()

    @classmethod
    def parse(cls, rid: str, text: str, natural: str = "", explanation: str = "",
              group: str = "") -> "Rule":
        head, body = parse_clause(text)
        if head is None:
            raise ParseError(f"{rid}: a rule needs a head; use Constraint for denials")
        if not body:
            raise ParseError(f"{rid}: a rule needs a body; write facts as facts")
        rule = cls(rid, head, tuple(body), " ".join(text.split()), natural,
                   explanation, group)
        rule.check_safety()
        return rule

    # A rule is "safe" (range restricted) when every variable in the head, in a
    # comparison or under 'not' is bound by a positive literal that comes
    # earlier. Forward chaining can then only ever derive ground facts.
    def check_safety(self) -> None:
        bound: set[str] = set()
        for lit in self.body:
            if lit.kind == "atom":
                bound.update(lit.variables())
            else:
                missing = [v for v in lit.variables() if v not in bound]
                if missing:
                    raise ParseError(
                        f"{self.rid}: variable(s) {missing} in '{lit}' are not bound "
                        "by an earlier positive literal")
        missing = [v for v in self.head[1:] if is_var(v) and v not in bound]
        if missing:
            raise ParseError(f"{self.rid}: head variable(s) {missing} do not occur in the body")

    @property
    def uses_negation(self) -> bool:
        return any(lit.kind == "not" for lit in self.body)

    def variables(self) -> list[str]:
        seen: list[str] = []
        for term in itertools.chain(self.head[1:], *(l.atom[1:] for l in self.body)):
            if is_var(term) and term not in seen:
                seen.append(term)
        return seen

    def renamed(self, suffix: str) -> "Rule":
        """Copy of the rule with fresh variable names (standardising apart)."""
        mapping = {v: f"{v}_{suffix}" for v in self.variables()}
        head = substitute(self.head, mapping)
        body = tuple(lit.substitute(mapping) for lit in self.body)
        return Rule(self.rid, head, body, self.text, self.natural, self.explanation,
                    self.group, self.stratum)

    def body_text(self) -> str:
        return ", ".join(lit.to_text() for lit in self.body)

    def to_prolog(self) -> str:
        return f"{format_atom(self.head)} :- " + ", ".join(l.to_prolog() for l in self.body) + "."

    def to_fol(self) -> str:
        """Standard reading of a Horn rule as a universally quantified implication."""
        quantifiers = " ".join(f"∀{v.lower()}" for v in self.variables())
        body = " ∧ ".join(lit.to_fol() for lit in self.body)
        head = Literal.positive(self.head).to_fol()
        if len(self.body) > 1:
            body = f"({body})"
        return f"{quantifiers} ({body} → {head})" if quantifiers else f"{body} → {head}"

    def __str__(self) -> str:
        return f"{format_atom(self.head)} :- {self.body_text()}."


@dataclass
class Constraint:
    """A denial (goal) clause  :- body.  The body must never be satisfiable."""

    cid: str
    body: tuple[Literal, ...]
    text: str
    natural: str = ""

    @classmethod
    def parse(cls, cid: str, text: str, natural: str = "") -> "Constraint":
        head, body = parse_clause(text)
        if head is not None:
            raise ParseError(f"{cid}: a constraint has no head")
        return cls(cid, tuple(body), " ".join(text.split()), natural)

    def to_fol(self) -> str:
        variables: list[str] = []
        for lit in self.body:
            for v in lit.variables():
                if v not in variables:
                    variables.append(v)
        quantifiers = " ".join(f"∀{v.lower()}" for v in variables)
        body = " ∧ ".join(lit.to_fol() for lit in self.body)
        return f"{quantifiers} ¬({body})"


class KnowledgeBase:
    """Ground facts plus rules, with a predicate index for fast matching."""

    def __init__(self, facts: Iterable[Atom] = (), rules: Iterable[Rule] = (),
                 constraints: Iterable[Constraint] = ()):
        self._facts: dict[str, set[Atom]] = defaultdict(set)
        self.rules: list[Rule] = []
        self.constraints: list[Constraint] = list(constraints)
        for fact in facts:
            self.add_fact(fact)
        for rule in rules:
            self.rules.append(rule)
        self.stratify()

    # ----- facts ---------------------------------------------------------
    def add_fact(self, fact: Atom | str) -> bool:
        if isinstance(fact, str):
            fact = parse_atom(fact)
        if not is_ground(fact):
            raise ParseError(f"facts must be ground: {format_atom(fact)}")
        if fact in self._facts[fact[0]]:
            return False
        self._facts[fact[0]].add(fact)
        return True

    def remove_fact(self, fact: Atom | str) -> None:
        if isinstance(fact, str):
            fact = parse_atom(fact)
        self._facts[fact[0]].discard(fact)

    def facts_for(self, predicate: str) -> set[Atom]:
        return self._facts.get(predicate, set())

    @property
    def facts(self) -> set[Atom]:
        return {f for group in self._facts.values() for f in group}

    def __contains__(self, fact: Atom) -> bool:
        return fact in self._facts.get(fact[0], ())

    # ----- rules ---------------------------------------------------------
    def rules_for(self, predicate: str) -> list[Rule]:
        return [r for r in self.rules if r.head[0] == predicate]

    def rule(self, rid: str) -> Rule:
        for r in self.rules:
            if r.rid == rid:
                return r
        raise KeyError(rid)

    @property
    def derived_predicates(self) -> set[str]:
        return {r.head[0] for r in self.rules}

    @property
    def predicates(self) -> set[str]:
        preds = set(self._facts) | self.derived_predicates
        for r in self.rules:
            preds.update(l.predicate for l in r.body if l.kind != "builtin")
        return preds

    def copy(self) -> "KnowledgeBase":
        return KnowledgeBase(self.facts, self.rules, self.constraints)

    # ----- stratification ------------------------------------------------
    def stratify(self) -> dict[str, int]:
        """Assign each derived predicate to a stratum (layer).

        A predicate used under 'not' must be completely computed in a lower
        stratum before the rule that negates it may fire. This is the usual
        stratified negation-as-failure condition. Raises ParseError if the
        rules contain a cycle through negation.
        """
        strata = {p: 0 for p in self.predicates}
        limit = len(strata) + 1
        changed = True
        while changed:
            changed = False
            for rule in self.rules:
                head = rule.head[0]
                for lit in rule.body:
                    if lit.kind == "builtin":
                        continue
                    need = strata[lit.predicate] + (1 if lit.kind == "not" else 0)
                    if strata[head] < need:
                        strata[head] = need
                        changed = True
                        if need > limit:
                            raise ParseError("rules are not stratifiable "
                                             "(recursion through negation)")
        for rule in self.rules:
            rule.stratum = strata[rule.head[0]]
        self.strata = strata
        return strata


def match_body(body: tuple[Literal, ...] | list[Literal], kb: KnowledgeBase,
               subst: Optional[Substitution] = None,
               facts_override: Optional[dict[str, set[Atom]]] = None) -> Iterator[Substitution]:
    """Yield every substitution that makes all body literals true in kb's facts.

    Literals are joined left to right, which is why the rule bodies are
    written so that comparisons and 'not' come after the literals that bind
    their variables.
    """
    subst = {} if subst is None else subst
    if not body:
        yield subst
        return
    first, rest = body[0], body[1:]
    if first.kind == "builtin":
        if evaluate_builtin(first, subst):
            yield from match_body(rest, kb, subst, facts_override)
        return
    lookup = (facts_override.get(first.predicate, set()) if facts_override is not None
              else kb.facts_for(first.predicate))
    if first.kind == "not":
        target = substitute(first.atom, subst)
        if target not in lookup:
            yield from match_body(rest, kb, subst, facts_override)
        return
    pattern = substitute(first.atom, subst)
    for fact in list(lookup):
        extended = unify(pattern, fact, subst)
        if extended is not None:
            yield from match_body(rest, kb, extended, facts_override)


def check_constraints(kb: KnowledgeBase) -> list[tuple[Constraint, Substitution]]:
    """Return every (constraint, bindings) pair whose body is satisfied."""
    violations = []
    for constraint in kb.constraints:
        for subst in match_body(constraint.body, kb):
            violations.append((constraint, subst))
    return violations
