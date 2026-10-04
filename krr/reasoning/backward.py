"""Backward chaining (goal-driven inference, SLD resolution).

To prove a goal G:
    1. If G is a built-in comparison, evaluate it.
    2. If G is 'not A', try to prove A. G succeeds only if A fails
       (negation as failure, only used on ground goals).
    3. Otherwise try every stored fact that unifies with G (success leaf).
    4. Then try every rule whose head unifies with G. Rename the rule's
       variables first (standardising apart), unify, and prove the body
       literals left to right as new subgoals, depth first.
    5. If nothing works, G fails and the search backtracks.

Each step is logged, so the trace shows which rule was chosen, which
subgoals it created, which facts closed them and where the search failed
and backtracked. A loop check refuses a subgoal that is a variant of one of
its own ancestors, so the search always terminates.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Iterator, Optional

from ..core.kb import KnowledgeBase
from ..core.terms import (Atom, Literal, ReasoningError, Substitution, binding_text,
                          evaluate_builtin, format_atom, is_ground, is_var, is_variant,
                          parse_query, resolve, substitute, unify)


@dataclass
class ProofNode:
    """One node of a proof tree: a proved literal and how it was proved."""
    text: str
    how: str                        # "fact", a rule id, "built-in" or "negation as failure"
    children: list["ProofNode"] = field(default_factory=list)

    def render(self, prefix: str = "", last: bool = True, root: bool = True) -> list[str]:
        label = f"{self.text}   [{self.how}]"
        if root:
            lines = [label]
            child_prefix = ""
        else:
            lines = [prefix + ("└── " if last else "├── ") + label]
            child_prefix = prefix + ("    " if last else "│   ")
        for i, child in enumerate(self.children):
            lines += child.render(child_prefix, i == len(self.children) - 1, False)
        return lines

    def facts_used(self) -> list[str]:
        if self.how == "fact":
            return [self.text]
        return [f for c in self.children for f in c.facts_used()]

    def rules_used(self) -> list[str]:
        own = [self.how] if self.how.startswith("R") else []
        return own + [r for c in self.children for r in c.rules_used()]


@dataclass
class TraceEvent:
    depth: int
    kind: str          # GOAL, FACT, RULE, BUILTIN, NOT, PROVED, FAIL, LOOP, LIMIT
    text: str


@dataclass
class BackwardResult:
    query: str
    success: bool
    answers: list[dict]
    proofs: list[ProofNode]
    trace: list[TraceEvent]
    steps: int

    def format_trace(self, max_lines: Optional[int] = None) -> str:
        lines = []
        for i, ev in enumerate(self.trace, 1):
            lines.append(f"{i:>4}  {'    ' * ev.depth}{ev.kind:<7} {ev.text}")
        if max_lines is not None and len(lines) > max_lines:
            hidden = len(lines) - max_lines
            lines = lines[:max_lines] + [f"      ... {hidden} more lines"]
        return "\n".join(lines)

    def summary(self) -> str:
        if not self.success:
            return f"{self.query}: FAILED. No proof exists from the facts and rules."
        if self.answers and any(self.answers):
            shown = "; ".join(", ".join(f"{k}={v}" for k, v in a.items()) for a in self.answers)
            return f"{self.query}: PROVED. Answers: {shown}"
        return f"{self.query}: PROVED."


class BackwardChainer:
    def __init__(self, kb: KnowledgeBase, max_depth: int = 40, record: bool = True):
        self.kb = kb
        self.max_depth = max_depth
        self.record = record
        self._counter = itertools.count(1)
        self.trace: list[TraceEvent] = []
        self.steps = 0

    # ----- public API ----------------------------------------------------
    def prove(self, query: str, all_answers: Optional[bool] = None) -> BackwardResult:
        """Prove a query. Ground queries stop at the first proof (like Prolog's
        once/1); queries with variables collect every distinct answer."""
        goals = parse_query(query)
        query_vars = []
        for lit in goals:
            for v in lit.variables():
                if v not in query_vars:
                    query_vars.append(v)
        if all_answers is None:
            all_answers = bool(query_vars)
        self.trace, self.steps = [], 0
        self._counter = itertools.count(1)
        answers, proofs, seen = [], [], set()
        for subst, nodes in self._solve_body(tuple(goals), {}, 0, ()):
            answer = {v: resolve(v, subst) for v in query_vars}
            key = tuple(sorted(answer.items()))
            if key in seen:
                continue
            seen.add(key)
            answers.append(answer)
            proofs.append(nodes[0] if len(nodes) == 1 else ProofNode(query, "conjunction", nodes))
            if not all_answers:
                break
        return BackwardResult(query, bool(answers), answers, proofs, self.trace, self.steps)

    def solutions(self, literal: Literal, subst: Substitution) -> Iterator[Substitution]:
        """Quiet solver used by the explanation module."""
        saved = self.record
        self.record = False
        try:
            for s, _ in self._solve_literal(literal, subst, 0, ()):
                yield s
        finally:
            self.record = saved

    # ----- search --------------------------------------------------------
    def _log(self, depth: int, kind: str, text: str) -> None:
        self.steps += 1
        if self.record:
            self.trace.append(TraceEvent(depth, kind, text))

    def _solve_body(self, body: tuple[Literal, ...], subst: Substitution, depth: int,
                    ancestors: tuple[Atom, ...]) -> Iterator[tuple[Substitution, list[ProofNode]]]:
        if not body:
            yield subst, []
            return
        first, rest = body[0], body[1:]
        for s1, node in self._solve_literal(first, subst, depth, ancestors):
            for s2, nodes in self._solve_body(rest, s1, depth, ancestors):
                yield s2, [node] + nodes

    def _solve_literal(self, lit: Literal, subst: Substitution, depth: int,
                       ancestors: tuple[Atom, ...]) -> Iterator[tuple[Substitution, ProofNode]]:
        if lit.kind == "builtin":
            shown = lit.substitute(subst).to_text()
            ok = evaluate_builtin(lit, subst)
            self._log(depth, "BUILTIN", f"{shown}  is {'true' if ok else 'false'}")
            if ok:
                yield subst, ProofNode(shown, "built-in")
            return

        if lit.kind == "not":
            target = substitute(lit.atom, subst)
            if not is_ground(target):
                raise ReasoningError(f"'not {format_atom(target)}' reached with unbound variables")
            self._log(depth, "NOT", f"try to prove {format_atom(target)}; "
                                    "'not' succeeds only if this fails")
            proved = next(self._solve_literal(Literal.positive(target), subst, depth + 1,
                                              ancestors), None)
            if proved is None:
                self._log(depth, "PROVED", f"not {format_atom(target)}  "
                                           "(the goal could not be proved)")
                yield subst, ProofNode(f"not {format_atom(target)}", "negation as failure")
            else:
                self._log(depth, "FAIL", f"not {format_atom(target)}  "
                                         "(the goal was proved, so 'not' fails)")
            return

        goal = substitute(lit.atom, subst)
        goal_text = format_atom(goal)
        self._log(depth, "GOAL", goal_text)

        if depth > self.max_depth:
            self._log(depth, "LIMIT", f"depth limit {self.max_depth} reached")
            return
        if any(is_variant(goal, a) for a in ancestors):
            self._log(depth, "LOOP", f"{goal_text} repeats an ancestor goal; skipped")
            return

        found = False
        # 1. stored facts
        for fact in sorted(self.kb.facts_for(goal[0]), key=lambda f: [str(t) for t in f]):
            s2 = unify(goal, fact, subst)
            if s2 is None:
                continue
            found = True
            self._log(depth, "FACT", f"{format_atom(fact)}  matches the stored fact")
            yield s2, ProofNode(format_atom(fact), "fact")

        # 2. rules whose head unifies with the goal
        for rule in self.kb.rules_for(goal[0]):
            renamed = rule.renamed(str(next(self._counter)))
            s2 = unify(goal, renamed.head, subst)
            if s2 is None:
                continue
            subgoals = ", ".join(l.substitute(s2).to_text() for l in renamed.body)
            self._log(depth, "RULE", f"try {rule.rid}: {rule.text}")
            self._log(depth, "", f"subgoals: {subgoals}")
            for s3, children in self._solve_body(renamed.body, s2, depth + 1,
                                                 ancestors + (goal,)):
                found = True
                proved = format_atom(substitute(goal, s3))
                self._log(depth, "PROVED", f"{proved}  by {rule.rid}")
                yield s3, ProofNode(proved, rule.rid, children)

        if not found:
            self._log(depth, "FAIL", f"{goal_text}  (no fact matches and no rule succeeds)")


def prove(kb: KnowledgeBase, query: str, all_answers: Optional[bool] = None) -> BackwardResult:
    return BackwardChainer(kb).prove(query, all_answers)
