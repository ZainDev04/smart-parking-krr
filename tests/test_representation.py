"""Frames, scripts, semantic network, FOL and DL."""

import unittest

from krr.frames.frames import FrameError
from krr.frames.ontology import build_frames
from krr.frames.scripts import run_parking_script
from krr.knowledge_base.scenarios import get
from krr.logic.description_logic import (A, And, DLReasoner, build_abox)
from krr.logic.fol import check_statements
from krr.reasoning.forward import forward_chain
from krr.semantic_net.network import build_class_network, build_instance_network


class FramesTest(unittest.TestCase):
    def setUp(self):
        self.fs = build_frames()

    def test_inherited_default(self):
        sv = self.fs.get("ali", "accessibilityBadge")
        self.assertEqual((sv.value, sv.source), ("no", "default from Person"))

    def test_own_value_overrides_default(self):
        self.assertEqual(self.fs.get("sara", "accessibilityBadge").source, "own value")

    def test_subclass_overrides_parent_default(self):
        self.assertEqual(self.fs.value("s_a1", "spaceType"), "standard")
        self.assertEqual(self.fs.value("s_a3", "spaceType"), "accessible")
        self.assertEqual(self.fs.get("s_a3", "spaceType").source, "default from AccessibleSpace")

    def test_if_needed(self):
        self.assertEqual(self.fs.value("zone_a", "capacity"), 5)
        self.assertEqual(self.fs.value("s_e2", "zoneType"), "employee_zone")

    def test_facets_validated(self):
        self.assertEqual(self.fs.validate(), [])
        self.fs.define_instance("bad_space", "ParkingSpace", locatedIn="ali", status="broken")
        errors = self.fs.validate()
        self.assertTrue(any("broken" in e for e in errors))
        self.assertTrue(any("not a ParkingZone" in e for e in errors))

    def test_unknown_slot_rejected(self):
        with self.assertRaises(FrameError):
            self.fs.define_instance("x", "Vehicle", colour="red")

    def test_translation_to_facts(self):
        facts = set(self.fs.to_facts())
        self.assertIn(("student", "ali"), facts)
        self.assertIn(("space_type", "s_a3", "accessible"), facts)
        self.assertIn(("accessibility_badge", "ali", "no"), facts)
        self.assertIn(("zone_opens", "zone_v", 8), facts)


class ScriptTest(unittest.TestCase):
    def test_successful_session(self):
        run = run_parking_script(get("morning_rush").build_kb(), "sara", "s_a1")
        self.assertTrue(run.completed)
        self.assertIn(("space_status", "s_a1", "occupied"), run.kb_after)

    def test_stops_at_permit_check(self):
        run = run_parking_script(get("morning_rush").build_kb(), "usman", "s_a1")
        self.assertFalse(run.completed)
        self.assertEqual(run.scenes[-1].scene.name, "Permit check")


class SemanticNetworkTest(unittest.TestCase):
    def test_every_class_frame_is_a_node(self):
        net = build_class_network()
        for frame in build_frames().classes():
            self.assertIn(frame.name, net.nodes)

    def test_link_kinds_present(self):
        labels = {e.label for e in build_class_network().edges}
        self.assertTrue({"is-a", "has-a", "part-of", "owns"} <= labels)

    def test_inheritance_through_is_a(self):
        net = build_class_network()
        self.assertIn(("owns", "Vehicle", "Person"), net.inherited_relations("Faculty"))

    def test_instance_network(self):
        net = build_instance_network(["ali"])
        self.assertIn("Person", net.superconcepts("ali"))


class FOLTest(unittest.TestCase):
    def test_statements_hold_in_main_model(self):
        facts = forward_chain(get("morning_rush").build_kb()).facts
        for st, ok, _ in check_statements(facts):
            self.assertTrue(ok, st.sid)

    def test_violation_found_with_counterexample(self):
        facts = forward_chain(get("morning_rush").build_kb()).facts | {("allocate", "ali", "s_a3")}
        failed = {st.sid: ce for st, ok, ce in check_statements(facts) if not ok}
        self.assertEqual(failed["F07"], {"x": "ali", "s": "s_a3"})

    def test_disjointness_statement_fails_on_bad_data(self):
        facts = forward_chain(get("tc12_inconsistent_abox").build_kb()).facts
        failed = {st.sid for st, ok, _ in check_statements(facts) if not ok}
        self.assertIn("F04", failed)


class DLTest(unittest.TestCase):
    def setUp(self):
        self.dl = DLReasoner()

    def test_told_and_inferred_subsumption(self):
        self.assertTrue(self.dl.subsumes(A("Faculty"), A("Person")))
        self.assertTrue(self.dl.subsumes(A("AuthorizedStudent"), A("ValidPermitHolder")))
        self.assertTrue(self.dl.subsumes(A("AuthorizedStudent"), A("AuthorizedDriver")))
        self.assertFalse(self.dl.subsumes(A("Person"), A("Student")))
        inferred = {(a, b) for a, b, inf in self.dl.classify() if inf}
        self.assertIn(("AuthorizedStudent", "AuthorizedDriver"), inferred)

    def test_unsatisfiable_concept(self):
        self.assertFalse(self.dl.satisfiable(And((A("Student"), A("Faculty")))))
        self.assertTrue(self.dl.satisfiable(And((A("Student"), A("BadgeHolder")))))

    def test_realization_agrees_with_horn_rules(self):
        fc = forward_chain(get("morning_rush").build_kb())
        realized = self.dl.realize(build_abox(fc.facts))
        for person in ("ali", "sara", "usman", "zara", "ahmed", "fatima", "bilal", "hina"):
            self.assertEqual("AuthorizedDriver" in realized[person],
                             fc.holds(f"authorized_driver({person})"), person)

    def test_consistent_main_abox(self):
        fc = forward_chain(get("morning_rush").build_kb())
        self.assertEqual(self.dl.check_consistency(build_abox(fc.facts)), [])

    def test_disjointness_clash(self):
        fc = forward_chain(get("tc12_inconsistent_abox").build_kb())
        clashes = self.dl.check_consistency(build_abox(fc.facts))
        self.assertEqual([(c.individual, c.axiom) for c in clashes], [("ali", "D01")])

    def test_universal_restriction_propagates(self):
        facts = forward_chain(get("morning_rush").build_kb()).facts | {("allocate", "ali", "s_a3")}
        clashes = self.dl.check_consistency(build_abox(facts))
        self.assertTrue(any(c.individual == "ali" and c.axiom == "D05" for c in clashes))


if __name__ == "__main__":
    unittest.main()
