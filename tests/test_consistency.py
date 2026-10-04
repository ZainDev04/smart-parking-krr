"""Consistency audit across paradigms.

Checks that frames, rules, FOL, DL, the semantic network and the Prolog
export all use the same vocabulary, so the report cannot describe a
predicate or concept the code does not have.
"""

import re
import unittest
from pathlib import Path

from krr.core.terms import parse_clause
from krr.export.prolog import to_prolog
from krr.frames.ontology import build_frames
from krr.knowledge_base.rules import CONSTRAINTS, RULES
from krr.knowledge_base.scenarios import SCENARIOS, get
from krr.logic.description_logic import (CONCEPT_FROM_FACT, ROLE_FROM_PREDICATE, ROLES,
                                         DLReasoner)
from krr.logic.fol import STATEMENTS, Pred
from krr.semantic_net.network import build_class_network

ROOT = Path(__file__).resolve().parents[1]
CONTEXT_PREDICATES = {"current_date", "current_hour", "requests"}


def fol_predicates(formula):
    found, stack = set(), [formula]
    while stack:
        f = stack.pop()
        if isinstance(f, Pred):
            found.add(f.name)
        for attr in ("body", "left", "right"):
            child = getattr(f, attr, None)
            if child is not None and not isinstance(child, str):
                stack.append(child)
        stack.extend(getattr(f, "parts", ()))
    return found


class VocabularyTest(unittest.TestCase):
    def setUp(self):
        self.kb = get("morning_rush").build_kb()
        self.stored = {f[0] for f in self.kb.facts}
        self.derived = self.kb.derived_predicates

    def test_every_body_predicate_is_stored_or_derived(self):
        for rule in RULES:
            for lit in rule.body:
                if lit.kind != "builtin":
                    self.assertIn(lit.predicate, self.stored | self.derived,
                                  f"{rule.rid} uses unknown predicate {lit.predicate}")

    def test_every_rule_documented(self):
        ids = [r.rid for r in RULES]
        self.assertEqual(len(ids), len(set(ids)))
        for rule in RULES:
            self.assertTrue(rule.natural and rule.group, rule.rid)

    def test_constraints_use_known_predicates(self):
        for c in CONSTRAINTS:
            for lit in c.body:
                if lit.kind != "builtin":
                    self.assertIn(lit.predicate, self.stored | self.derived, c.cid)

    def test_fol_predicates_exist(self):
        for st in STATEMENTS:
            for p in fol_predicates(st.formula):
                self.assertIn(p, self.stored | self.derived, f"{st.sid}: {p}")

    def test_frame_predicates_reach_the_kb(self):
        fs = build_frames()
        for frame in fs.classes():
            if frame.predicate and fs.instances(frame.name):
                self.assertIn(frame.predicate, self.stored | self.derived, frame.name)

    def test_dl_vocabulary_maps_to_kb(self):
        for pred, (role, _) in ROLE_FROM_PREDICATE.items():
            self.assertIn(role, ROLES)
            self.assertIn(pred, self.stored | self.derived)
        names = set(DLReasoner().concept_names())
        for key, concept in CONCEPT_FROM_FACT.items():
            self.assertIn(concept, names)
            self.assertIn(key[0], self.stored | self.derived)
        for frame in build_frames().classes():
            self.assertIn(frame.name, names | {"ParkingFacility", "Reservation"},
                          f"frame {frame.name} has no DL concept")

    def test_network_matches_frames(self):
        net = build_class_network()
        fs = build_frames()
        for e in net.edges:
            if e.label == "is-a":
                self.assertEqual(fs.frames[e.source].isa, e.target)

    def test_scenario_facts_use_known_predicates(self):
        for key in SCENARIOS:
            for f in get(key).context_facts():
                self.assertIn(f[0], self.stored | self.derived | CONTEXT_PREDICATES, key)


class PrologExportTest(unittest.TestCase):
    def test_round_trip(self):
        sc = get("morning_rush")
        kb = sc.build_kb()
        text = to_prolog(kb, sc)
        clauses = [line for line in text.splitlines()
                   if line and not line.startswith(("%", ":-", "/*", " ", "*/"))
                   and not line.startswith(("violation", "consistent", "show_allocations"))
                   and re.match(r"^[a-z]", line)]
        facts, rules = set(), []
        for line in clauses:
            head, body = parse_clause(line.replace("\\+ ", "not "))
            if body:
                rules.append((head, tuple(body)))
            else:
                facts.add(head)
        self.assertEqual(facts, kb.facts)
        self.assertEqual(rules, [(r.head, r.body) for r in kb.rules])


class GeneratedFilesTest(unittest.TestCase):
    def test_static_diagrams_exist(self):
        for name in ("architecture", "reasoning_engine", "forward_chaining_flow",
                     "backward_chaining_flow", "parking_script"):
            self.assertTrue((ROOT / "docs" / "diagrams" / f"{name}.mmd").exists(), name)


if __name__ == "__main__":
    unittest.main()
