"""Forward chaining (data-driven inference).

Algorithm, one stratum at a time (stratum 0 first, then stratum 1):

    repeat                                   # one repetition = one cycle
        conflict set := every (rule, bindings) whose body is true in the
                        facts known at the start of the cycle
        fire every instance whose conclusion is new; add the conclusions
    until a cycle adds nothing               # fixpoint reached

Instances whose conclusion is already known are not fired again
(refraction), which is what guarantees termination. Facts derived in a
cycle become usable in the next cycle, so the trace shows the inference
spreading outward from the initial facts level by level.

Rules of stratum 1 (R28 with 'not') only start once stratum 0 has reached
its fixpoint, so 'not loses(X, S)' is checked against a complete set of
loses/2 facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.kb import KnowledgeBase, Rule, check_constraints, match_body
from ..core.terms import (Atom, Substitution, binding_text, format_atom, parse_query,
                          substitute)


@dataclass
class Firing:
    step: int
    cycle: int
    stratum: int
    rule: Rule
    bindings: Substitution
    premises: list[str]
    derived: Atom

    def text(self) -> str:
        return (f"Step {self.step}: {self.rule.rid} fires with "
                f"{binding_text(self.bindings, self.rule.variables())}\n"
                f"    because {' AND '.join(self.premises)}\n"
                f"    derive  {format_atom(self.derived)}")


@dataclass
class Cycle:
    number: int
    stratum: int
    conflict_set: int          # rule instances whose bodies matched
    fired: int                 # instances that produced a new fact
    rules_fired: list[str]


@dataclass
class ForwardResult:
    initial: frozenset
    facts: set
    firings: list[Firing] = field(default_factory=list)
    cycles: list[Cycle] = field(default_factory=list)
    violations: list = field(default_factory=list)

    @property
    def derived(self) -> set:
        return self.facts - self.initial

    def holds(self, goal: str | Atom) -> bool:
        from ..core.terms import parse_atom
        atom = parse_atom(goal) if isinstance(goal, str) else goal
        return atom in self.facts

    def query(self, pattern: str) -> list[Substitution]:
        """All bindings for a (possibly non-ground) goal in the closure."""
        kb = KnowledgeBase(self.facts)
        return list(match_body(parse_query(pattern), kb))

    def derived_by_predicate(self) -> dict[str, list[Atom]]:
        out: dict[str, list[Atom]] = {}
        for f in sorted(self.derived, key=lambda a: (a[0], [str(t) for t in a[1:]])):
            out.setdefault(f[0], []).append(f)
        return out

    def firing_for(self, atom: Atom) -> Firing | None:
        for f in self.firings:
            if f.derived == atom:
                return f
        return None


def forward_chain(kb: KnowledgeBase, max_cycles: int = 1000) -> ForwardResult:
    """Compute the closure of kb under its rules and record a full trace."""
    work = kb.copy()
    result = ForwardResult(frozenset(work.facts), set())
    step = 0
    cycle_no = 0
    for stratum in sorted({r.stratum for r in work.rules}):
        rules = [r for r in work.rules if r.stratum == stratum]
        while True:
            cycle_no += 1
            if cycle_no > max_cycles:
                raise RuntimeError("forward chaining did not reach a fixpoint")
            # Match against a snapshot so that a cycle only uses facts known
            # when it started. New facts are added together at the end.
            snapshot = {p: set(work.facts_for(p)) for p in work.predicates}
            conflict_set = 0
            new_this_cycle: dict[Atom, Firing] = {}
            for rule in rules:
                for subst in match_body(rule.body, work, {}, snapshot):
                    conflict_set += 1
                    head = substitute(rule.head, subst)
                    if head in work or head in new_this_cycle:
                        continue           # refraction: nothing new to add
                    step += 1
                    premises = [lit.substitute(subst).to_text() for lit in rule.body]
                    new_this_cycle[head] = Firing(step, cycle_no, stratum, rule,
                                                  subst, premises, head)
            for head, firing in new_this_cycle.items():
                work.add_fact(head)
                result.firings.append(firing)
            fired_rules = sorted({f.rule.rid for f in new_this_cycle.values()})
            result.cycles.append(Cycle(cycle_no, stratum, conflict_set,
                                       len(new_this_cycle), fired_rules))
            if not new_this_cycle:
                break
    result.facts = work.facts
    result.violations = check_constraints(work)
    return result


def format_trace(result: ForwardResult, show_initial: bool = True,
                 only_rules: set[str] | None = None) -> str:
    """Printable step-by-step trace sheet."""
    from ..knowledge_base.facts import grouped

    lines = ["FORWARD CHAINING TRACE", "=" * 60]
    if show_initial:
        lines.append(f"Initial facts (working memory): {len(result.initial)}")
        for title, rows in grouped(result.initial):
            lines.append(f"  [{title}]")
            for i in range(0, len(rows), 3):
                lines.append("    " + "   ".join(rows[i:i + 3]))
        lines.append("")
    by_cycle: dict[int, list[Firing]] = {}
    for f in result.firings:
        by_cycle.setdefault(f.cycle, []).append(f)
    for cyc in result.cycles:
        header = (f"Cycle {cyc.number} (stratum {cyc.stratum}): conflict set = "
                  f"{cyc.conflict_set} matched rule instances, {cyc.fired} new fact(s)")
        lines.append(header)
        lines.append("-" * len(header))
        firings = by_cycle.get(cyc.number, [])
        if not firings:
            lines.append("    No rule instance produces a new fact. Fixpoint reached"
                         + (" for this stratum." if cyc.stratum == 0 else "."))
        for f in firings:
            if only_rules is None or f.rule.rid in only_rules:
                lines.append(f.text())
        lines.append("")
    lines.append(f"Closure: {len(result.facts)} facts "
                 f"({len(result.initial)} initial + {len(result.derived)} derived) "
                 f"after {len(result.cycles)} cycles.")
    if result.violations:
        lines.append("Integrity constraint violations:")
        for c, s in result.violations:
            lines.append(f"    {c.cid}: {c.natural}  {binding_text(s, s.keys())}")
    else:
        lines.append("Integrity constraints IC1-IC7: no violations.")
    return "\n".join(lines)


def support(result: ForwardResult, target: Atom | str) -> list[Firing]:
    """The firings a derived fact depends on, in the order they happened.

    Walking back from the target through the premises of each firing gives
    the part of the full trace that matters for one conclusion, which is
    what a trace sheet for a single decision should show.
    """
    from ..core.terms import parse_atom
    target = parse_atom(target) if isinstance(target, str) else target
    by_fact = {f.derived: f for f in result.firings}
    needed: dict[int, Firing] = {}
    stack = [target]
    while stack:
        atom = stack.pop()
        firing = by_fact.get(atom)
        if firing is None or firing.step in needed:
            continue
        needed[firing.step] = firing
        for lit in firing.rule.body:
            if lit.kind == "atom":
                stack.append(substitute(lit.atom, firing.bindings))
    return [needed[k] for k in sorted(needed)]


def format_support(result: ForwardResult, target: str) -> str:
    firings = support(result, target)
    initial_used = sorted({p for f in firings for p, lit in zip(f.premises, f.rule.body)
                           if lit.kind == "atom" and _is_initial(result, p)})
    lines = [f"Forward chaining trace for {target}", "=" * 60,
             "Initial facts used:"]
    for i in range(0, len(initial_used), 3):
        lines.append("    " + "   ".join(initial_used[i:i + 3]))
    lines.append("")
    current = None
    for f in firings:
        if f.cycle != current:
            current = f.cycle
            lines.append(f"Cycle {f.cycle} (stratum {f.stratum})")
        lines.append(f.text())
    lines.append("")
    lines.append(f"{len(firings)} rule firings lead to {target}.")
    return "\n".join(lines)


def _is_initial(result: ForwardResult, text: str) -> bool:
    from ..core.terms import parse_atom
    return parse_atom(text) in result.initial
