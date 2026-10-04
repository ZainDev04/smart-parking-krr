"""One-call access to the whole system, used by the CLI, the UI and the tests."""

from __future__ import annotations

from dataclasses import dataclass

from .core.kb import KnowledgeBase
from .knowledge_base.scenarios import SCENARIOS, Scenario, get
from .logic.description_logic import DLReasoner, build_abox
from .logic.fol import check_statements
from .reasoning.backward import BackwardChainer, BackwardResult
from .reasoning.explain import explain_text, root_causes
from .reasoning.forward import ForwardResult, forward_chain


@dataclass
class Outcome:
    person: str
    space: str
    allocated: bool
    reasons: list[str]


@dataclass
class Run:
    scenario: Scenario
    kb: KnowledgeBase
    forward: ForwardResult

    def prove(self, goal: str) -> BackwardResult:
        return BackwardChainer(self.kb).prove(goal)

    def explain(self, goal: str) -> str:
        return explain_text(self.kb, goal)

    def outcomes(self) -> list[Outcome]:
        """Decision for every request, with the root cause for each denial."""
        out = []
        for fact in sorted(self.kb.facts_for("requests"), key=lambda f: f[3]):
            _, person, space, _ = fact
            goal = f"allocate({person}, {space})"
            allocated = self.forward.holds(goal)
            out.append(Outcome(person, space, allocated,
                               [] if allocated else root_causes(self.kb, goal)))
        return out

    def check_expectations(self) -> list[tuple[str, bool, bool, bool]]:
        """(goal, expected, forward result, backward result) for each expectation."""
        rows = []
        bc = BackwardChainer(self.kb, record=False)
        for e in self.scenario.expectations:
            rows.append((e.goal, e.holds, self.forward.holds(e.goal), bc.prove(e.goal).success))
        return rows

    def dl_report(self):
        reasoner = DLReasoner()
        abox = build_abox(self.forward.facts)
        return reasoner, abox, reasoner.realize(abox), reasoner.check_consistency(abox)

    def fol_report(self):
        return check_statements(self.forward.facts)


def run(scenario: str | Scenario = "morning_rush") -> Run:
    sc = get(scenario) if isinstance(scenario, str) else scenario
    kb = sc.build_kb()
    return Run(sc, kb, forward_chain(kb))


__all__ = ["run", "Run", "SCENARIOS", "get"]
