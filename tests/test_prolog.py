"""The generated SWI-Prolog program must prove exactly what the Python
forward chainer derives, in every scenario. Skipped when swipl is missing."""

import unittest

from krr.export.prolog import conclusions_in_python, conclusions_in_swipl, find_swipl
from krr.knowledge_base.scenarios import TEST_CASES, get

SWIPL = find_swipl()


@unittest.skipUnless(SWIPL, "SWI-Prolog (swipl) is not installed")
class PrologAgreesTest(unittest.TestCase):
    def test_every_scenario(self):
        for sc in [get("morning_rush")] + TEST_CASES:
            with self.subTest(scenario=sc.key):
                kb = sc.build_kb()
                answers, warnings = conclusions_in_swipl(kb, sc, SWIPL)
                self.assertEqual(warnings, "", "the program should load without warnings")
                self.assertEqual(answers, conclusions_in_python(kb))

    def test_main_scenario_allocations(self):
        kb = get("morning_rush").build_kb()
        answers, _ = conclusions_in_swipl(kb, get("morning_rush"), SWIPL)
        self.assertEqual(sorted(a for a in answers if a.startswith("allocate(")),
                         ["allocate(ahmed,s_e3)", "allocate(bilal,s_v1)", "allocate(sara,s_a1)"])


if __name__ == "__main__":
    unittest.main()
