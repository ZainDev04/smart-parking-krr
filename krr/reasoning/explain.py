"""'Why not?' explanations for goals that cannot be proved.

When a request is denied, the useful answer is the reason. Backward
chaining gives it almost for free: for every rule that could conclude the
goal, find how far the body can be proved, and report the first literal
that blocks it. If that literal is itself a derived predicate, explain it
the same way, one level deeper.

Example output:
    allocate(usman, s_a1) cannot be proved
      R28 blocked at can_allocate(usman, s_a1)
        R19 blocked at eligible_for_space(usman, s_a1)
          ...
            R06 blocked at 20260915 >= 20261002 (false)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.kb import KnowledgeBase
from ..core.terms import (Literal, evaluate_builtin, format_atom, parse_atom, substitute,
                          unify)
from .backward import BackwardChainer


@dataclass
class Reason:
    goal: str
    verdict: str                 # "holds", "fails"
    detail: str = ""
    rule: str = ""
    children: list["Reason"] = field(default_factory=list)
    parent: str = ""             # the goal this rule was trying to prove

    def render(self, indent: int = 0) -> list[str]:
        pad = "  " * indent
        if self.rule:
            head = f"{pad}{self.rule} blocked at {self.goal}"
        else:
            head = f"{pad}{self.goal}"
        if self.detail:
            head += f"  ({self.detail})"
        lines = [head]
        for child in self.children:
            lines += child.render(indent + 1)
        return lines

    def leaves(self) -> list["Reason"]:
        if not self.children:
            return [self]
        return [leaf for c in self.children for leaf in c.leaves()]


class Explainer:
    def __init__(self, kb: KnowledgeBase, max_depth: int = 8, budget: int = 5000):
        self.kb = kb
        self.bc = BackwardChainer(kb, record=False)
        self.max_depth = max_depth
        self.budget = budget
        self._explained: set[str] = set()

    def why_not(self, goal: str) -> Reason:
        atom = parse_atom(goal)
        if next(self.bc.solutions(Literal.positive(atom), {}), None) is not None:
            return Reason(format_atom(atom), "holds", "this goal is provable")
        reason = self._explain_atom(atom, 0)
        reason.detail = reason.detail or "cannot be proved"
        return reason

    def _explain_atom(self, atom, depth: int) -> Reason:
        text = format_atom(atom)
        rules = [r for r in self.kb.rules_for(atom[0]) if unify(atom, r.head) is not None]
        if not rules:
            if atom[0] in self.kb.derived_predicates:
                return Reason(text, "fails", "no rule can conclude this pattern")
            return Reason(text, "fails", "no such fact is stored")
        if text in self._explained:
            return Reason(text, "fails", "explained above")
        self._explained.add(text)
        node = Reason(text, "fails", "")
        if depth >= self.max_depth:
            node.detail = "explanation depth limit"
            return node
        for rule in rules:
            node.children.append(self._explain_rule(atom, rule, depth))
        return node

    def _explain_rule(self, atom, rule, depth: int) -> Reason:
        renamed = rule.renamed(f"w{depth}")
        start = unify(atom, renamed.head)
        best = {"index": 0, "subst": start}
        explored = [0]

        def dfs(i: int, subst) -> None:
            if explored[0] > self.budget:
                return
            explored[0] += 1
            if i > best["index"]:
                best["index"], best["subst"] = i, subst
            if i == len(renamed.body):
                return
            for s2 in self.bc.solutions(renamed.body[i], subst):
                dfs(i + 1, s2)

        dfs(0, start)
        i, subst = best["index"], best["subst"]
        if i >= len(renamed.body):        # body provable but head not: cannot happen
            return Reason(format_atom(atom), "holds", rule=rule.rid)
        blocked = renamed.body[i]
        shown = _readable(blocked.substitute(subst).to_text())
        if blocked.kind == "builtin":
            ok = evaluate_builtin(blocked, subst)
            return Reason(shown, "fails", "false" if not ok else "", rule.rid,
                          parent=_readable(format_atom(atom)))
        if blocked.kind == "not":
            target = substitute(blocked.atom, subst)
            proof = BackwardChainer(self.kb).prove(format_atom(target))
            why = ""
            if proof.proofs:
                root = proof.proofs[0]
                why = f"{format_atom(target)} is provable by {root.how}"
                own = f"requests({target[1]},"
                facts = [f for f in root.facts_used()
                         if f.startswith("requests") and not f.startswith(own)]
                if facts:
                    why += "; competing request: " + ", ".join(sorted(set(facts)))
            return Reason(shown, "fails", why or "the negated goal is provable", rule.rid,
                          parent=_readable(format_atom(atom)))
        target = substitute(blocked.atom, subst)
        child = self._explain_atom(target, depth + 1)
        child.goal = _readable(child.goal)
        return Reason(shown, "fails", child.detail if not child.children else "", rule.rid,
                      child.children, parent=_readable(format_atom(atom)))


def _readable(text: str) -> str:
    """Hide the renaming suffixes (X_w3 -> X) used to keep rule variables apart."""
    import re
    return re.sub(r"\b([A-Z][A-Za-z0-9]*)_w?\d+\b", r"\1", text)


def why_not(kb: KnowledgeBase, goal: str) -> Reason:
    return Explainer(kb).why_not(goal)


def explain_text(kb: KnowledgeBase, goal: str) -> str:
    reason = why_not(kb, goal)
    if reason.verdict == "holds":
        return f"{goal} holds."
    lines = [f"{goal} cannot be proved. Reasons, rule by rule:"]
    for child in reason.children:
        lines += child.render(1)
    if not reason.children:
        lines.append(f"  {reason.detail}")
    return "\n".join(lines)


def root_causes(kb: KnowledgeBase, goal: str) -> list[str]:
    """The deepest blocked literals: the short answer to 'why was I denied?'."""
    reason = why_not(kb, goal)
    if reason.verdict == "holds":
        return []
    out = []
    for leaf in reason.leaves():
        if leaf.detail == "explained above":
            continue
        label = (f"{leaf.parent} fails at {leaf.goal}" if leaf.parent else leaf.goal)
        label += f" ({leaf.detail})" if leaf.detail else ""
        if label not in out:
            out.append(label)
    return out
