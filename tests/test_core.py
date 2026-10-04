"""Unit tests for terms, parsing, unification, rule safety and stratification."""

import unittest

from krr.core.kb import Constraint, KnowledgeBase, Rule
from krr.core.terms import (Literal, ParseError, ReasoningError, evaluate_builtin, is_var,
                            is_variant, parse_atom, parse_clause, parse_literal, unify)


class TermsTest(unittest.TestCase):
    def test_variables_and_constants(self):
        self.assertTrue(is_var("X"))
        self.assertTrue(is_var("_tmp"))
        self.assertFalse(is_var("ali"))
        self.assertFalse(is_var(20261002))

    def test_parse_atom(self):
        self.assertEqual(parse_atom("owns(ali, car_ali)"), ("owns", "ali", "car_ali"))
        self.assertEqual(parse_atom("current_date(20261002)"), ("current_date", 20261002))
        with self.assertRaises(ParseError):
            parse_atom("Owns(ali)")

    def test_parse_literals(self):
        self.assertEqual(parse_literal("E >= D"), Literal("builtin", (">=", "E", "D")))
        self.assertEqual(parse_literal("X \\= Y"), Literal("builtin", ("\\=", "X", "Y")))
        self.assertEqual(parse_literal("not loses(X, S)").kind, "not")

    def test_parse_clause(self):
        head, body = parse_clause("a(X) :- b(X, Y), c(Y).")
        self.assertEqual(head, ("a", "X"))
        self.assertEqual(len(body), 2)
        head, body = parse_clause(":- student(X), employee(X).")
        self.assertIsNone(head)

    def test_unify(self):
        self.assertEqual(unify(("p", "X", "b"), ("p", "a", "Y")), {"X": "a", "Y": "b"})
        self.assertIsNone(unify(("p", "a"), ("p", "b")))
        self.assertIsNone(unify(("p", "X", "X"), ("p", "a", "b")))
        self.assertIsNone(unify(("p", "a"), ("q", "a")))

    def test_variant(self):
        self.assertTrue(is_variant(("p", "X", "Y"), ("p", "A", "B")))
        self.assertFalse(is_variant(("p", "X", "X"), ("p", "A", "B")))

    def test_builtin_needs_bound_values(self):
        with self.assertRaises(ReasoningError):
            evaluate_builtin(parse_literal("E >= D"), {"E": 5})
        self.assertTrue(evaluate_builtin(parse_literal("E >= D"), {"E": 5, "D": 3}))


class RuleTest(unittest.TestCase):
    def test_unsafe_head_variable_rejected(self):
        with self.assertRaises(ParseError):
            Rule.parse("bad", "p(X, Y) :- q(X).")

    def test_unbound_comparison_rejected(self):
        with self.assertRaises(ParseError):
            Rule.parse("bad", "p(X) :- X > Y, q(X, Y).")

    def test_fol_reading(self):
        r = Rule.parse("r", "person(X) :- student(X).")
        self.assertEqual(r.to_fol(), "∀x (student(x) → person(x))")

    def test_constraint_fol(self):
        c = Constraint.parse("c", ":- student(X), employee(X).")
        self.assertEqual(c.to_fol(), "∀x ¬(student(x) ∧ employee(x))")

    def test_stratification(self):
        kb = KnowledgeBase([("q", "a")], [Rule.parse("r1", "p(X) :- q(X), not s(X)."),
                                          Rule.parse("r2", "s(X) :- q(X).")])
        self.assertEqual(kb.rule("r1").stratum, 1)
        self.assertEqual(kb.rule("r2").stratum, 0)

    def test_recursion_through_negation_rejected(self):
        with self.assertRaises(ParseError):
            KnowledgeBase([("q", "a")], [Rule.parse("r1", "p(X) :- q(X), not s(X)."),
                                         Rule.parse("r2", "s(X) :- q(X), not p(X).")])


if __name__ == "__main__":
    unittest.main()
