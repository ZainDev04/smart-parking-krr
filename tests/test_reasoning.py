"""The two chaining engines must agree with each other and with the rules.

These tests are the strongest evidence that the traces in the report are
correct: forward and backward chaining are implemented independently, yet
for every derived predicate they produce exactly the same set of answers.
"""

import dataclasses
import unittest

from krr.core.kb import KnowledgeBase, Rule, match_body
from krr.core.terms import format_atom, substitute
from krr.knowledge_base.scenarios import SCENARIOS, TEST_CASES, get
from krr.reasoning.backward import BackwardChainer
from krr.reasoning.explain import root_causes
from krr.reasoning.forward import forward_chain
from krr.system import run


class ForwardChainingTest(unittest.TestCase):
    def test_small_example(self):
        kb = KnowledgeBase([("student", "ali"), ("valid", "ali")],
                           [Rule.parse("r1", "eligible(X) :- student(X), valid(X)."),
                            Rule.parse("r2", "happy(X) :- eligible(X).")])
        result = forward_chain(kb)
        self.assertEqual(result.derived, {("eligible", "ali"), ("happy", "ali")})
        self.assertEqual([f.rule.rid for f in result.firings], ["r1", "r2"])
        self.assertEqual(len(result.cycles), 3)          # two productive cycles + fixpoint

    def test_closure_is_a_model_of_every_rule(self):
        """After the fixpoint no rule instance can produce anything new."""
        for key in SCENARIOS:
            result = forward_chain(get(key).build_kb())
            closure = KnowledgeBase(result.facts)
            for rule in get(key).build_kb().rules:
                for subst in match_body(rule.body, closure):
                    self.assertIn(substitute(rule.head, subst), result.facts,
                                  f"{key}: {rule.rid} not closed")

    def test_every_firing_is_justified(self):
        result = forward_chain(get("morning_rush").build_kb())
        known = set(result.initial)
        for firing in sorted(result.firings, key=lambda f: f.step):
            for lit in firing.rule.body:
                ground = substitute(lit.atom, firing.bindings)
                if lit.kind == "atom":
                    self.assertIn(ground, known, f"step {firing.step} used an unknown fact")
            known.add(firing.derived)

    def test_terminates_and_reports_cycles(self):
        result = forward_chain(get("morning_rush").build_kb())
        self.assertEqual(result.cycles[-1].fired, 0)
        self.assertEqual({c.stratum for c in result.cycles}, {0, 1})


class EnginesAgreeTest(unittest.TestCase):
    def test_same_answers_for_every_derived_predicate(self):
        for key in SCENARIOS:
            kb = get(key).build_kb()
            fc = forward_chain(kb)
            bc = BackwardChainer(kb, record=False)
            for pred in sorted(kb.derived_predicates):
                arity = len(kb.rules_for(pred)[0].head) - 1
                variables = [f"V{i}" for i in range(arity)]
                query = f"{pred}({', '.join(variables)})"
                answers = bc.prove(query, all_answers=True).answers
                from_bc = {(pred, *(a[v] for v in variables)) for a in answers}
                from_fc = {f for f in fc.facts if f[0] == pred}
                self.assertEqual(from_bc, from_fc, f"{key}: {pred} differs")


class BackwardChainingTest(unittest.TestCase):
    def test_trace_records_rules_and_facts(self):
        kb = get("tc01_valid_student").build_kb()
        result = BackwardChainer(kb).prove("allocate(ali, s_a1)")
        self.assertTrue(result.success)
        kinds = {e.kind for e in result.trace}
        self.assertTrue({"GOAL", "RULE", "FACT", "BUILTIN", "NOT", "PROVED"} <= kinds)
        tree = result.proofs[0]
        self.assertEqual(tree.how, "R28")
        self.assertIn("permit_valid(p_ali)", "\n".join(tree.render()))

    def test_open_query_returns_all_answers(self):
        kb = get("morning_rush").build_kb()
        result = BackwardChainer(kb).prove("can_allocate(ahmed, S)")
        self.assertEqual(sorted(a["S"] for a in result.answers), ["s_e1", "s_e2", "s_e3"])

    def test_loop_check(self):
        kb = KnowledgeBase([("edge", "a", "b"), ("edge", "b", "a")],
                           [Rule.parse("r1", "path(X, Y) :- edge(X, Y)."),
                            Rule.parse("r2", "path(X, Y) :- path(X, Z), edge(Z, Y).")])
        result = BackwardChainer(kb).prove("path(a, c)")
        self.assertFalse(result.success)
        self.assertIn("LOOP", {e.kind for e in result.trace})


class ExplanationTest(unittest.TestCase):
    def test_expired_permit_reason(self):
        kb = get("tc02_expired_permit").build_kb()
        causes = root_causes(kb, "allocate(usman, s_a1)")
        self.assertTrue(any("20260915 >= 20261002" in c for c in causes))

    def test_conflict_reason_names_winner(self):
        kb = get("tc07_conflict").build_kb()
        causes = root_causes(kb, "allocate(ali, s_a1)")
        self.assertTrue(any("not loses(ali, s_a1)" in c for c in causes))

    def test_visitor_without_pass(self):
        kb = get("tc03_visitor_no_pass").build_kb()
        causes = root_causes(kb, "authorized_driver(hina)")
        self.assertTrue(any("has_permit(hina, P)" in c for c in causes))


class ScenarioTest(unittest.TestCase):
    def test_all_expectations(self):
        for sc in [get("morning_rush")] + TEST_CASES:
            for goal, expected, fc, bc in run(sc).check_expectations():
                self.assertEqual(fc, expected, f"{sc.key}: forward {goal}")
                self.assertEqual(bc, expected, f"{sc.key}: backward {goal}")

    def test_main_scenario_allocations(self):
        r = run("morning_rush")
        allocations = sorted(format_atom(f) for f in r.forward.facts if f[0] == "allocate")
        self.assertEqual(allocations, ["allocate(ahmed, s_e3)", "allocate(bilal, s_v1)",
                                       "allocate(sara, s_a1)"])

    def test_one_day_pass_only_on_its_day(self):
        """vp_bilal starts and expires on 2 Oct 2026, so it fails a day either side."""
        for date, valid in ((20261001, False), (20261002, True), (20261003, False)):
            r = run(dataclasses.replace(get("tc03_visitor_no_pass"), date=date))
            self.assertEqual(("permit_valid", "vp_bilal") in r.forward.facts, valid, date)
            self.assertEqual(r.prove("permit_valid(vp_bilal)").success, valid, date)

    def test_pass_before_start_date_reason(self):
        kb = dataclasses.replace(get("tc03_visitor_no_pass"), date=20261001).build_kb()
        causes = root_causes(kb, "permit_valid(vp_bilal)")
        self.assertTrue(any("20261002 =< 20261001" in c for c in causes), causes)

    def test_constraints(self):
        for sc in [get("morning_rush")] + TEST_CASES:
            violations = {c.cid for c, _ in run(sc).forward.violations}
            expected = {"IC4"} if sc.key == "tc12_inconsistent_abox" else set()
            self.assertEqual(violations, expected, sc.key)


if __name__ == "__main__":
    unittest.main()
