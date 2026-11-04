# Rubric checklist

Each line names a requirement from the CCP guide or the rubric and where the project meets it.

## Guide: critical elements

- [x] Frames and scripts with class frames, slots, facets and default values: report section 3.1 (3.1.1-3.1.11), krr/frames/ontology.py, krr/frames/scripts.py.
- [x] Semantic network showing is-a, has-a and part-of: report section 3.2 (concept and instance network figures), krr/semantic_net/network.py.
- [x] FOL facts, rules and quantifiers: report section 4.1 (rule formulas FOL-01 to FOL-10, all 28 in Rule.to_fol(), plus F01-F12 with ∀ and ∃).
- [x] DL subsumption, membership and disjointness axioms: report section 4.2 (T01-T28, D01-D17, ABox assertions).
- [x] Expressivity vs. tractability of propositional logic and FOL in this domain: report section 8.2.2.
- [x] Horn clause conversion: report section 5 (all facts, rules, denial clauses, three worked conversions, negation policy, Prolog form).
- [x] Forward chaining trace (data-driven): report section 6.1.
- [x] Backward chaining trace (goal-driven): report section 6.2, including a failure with backtracking.

## Guide: deliverables in order

- [x] Title page and grading rubric sheet, with all four students.
- [x] Text summary: domain requirements (2.1.3), problem statement and motivation (1.1-1.2), limitations of traditional databases (2.2.4), team participation statement (section 11).
- [x] Semantic network and frame architecture diagrams (Figures 2, 4, 5).
- [x] Formal logic definitions: FOL formulas and DL axioms (section 4).
- [x] Horn clause knowledge base and step-by-step chaining trace sheets (sections 5 and 6).
- [x] Sample execution output and code snippets: Python rule engine and Prolog program (section 7.2).

## Rubric criteria (target: 2, Proficient)

- [x] Criterion 1, problem statement and motivation: objective, 13 numbered domain requirements, motivation and justification (sections 1 and 2).
- [x] Criterion 2, structural KR: 15 class frames and 38 instance frames with value, default, type, range, cardinality, if-needed and predicate facets; inheritance and overriding; an executable script; a semantic network generated from the frames.
- [x] Criterion 3, formal logic: every rule has an FOL form with explicit quantifiers; 12 more FOL statements are model-checked on every run; the DL TBox has subsumption, ∃, ∀, inverse roles, definitions and disjointness, and the reasoner classifies it and checks consistency.
- [x] Criterion 4, inference engine: 28 Horn rules plus 7 denial clauses. Forward and backward chaining are real engines. Their traces are generated from runs, and both engines are proven to agree on every derived fact.
- [x] Criterion 5, team participation and viva: each member owns one paradigm end to end (contributions table in section 11). The viva guide has questions and answers per member and a presentation script with one part each.

## Quality checks

- [x] python -m unittest discover -s tests: all tests pass.
- [x] python main.py cases: 12 cases, 0 mismatches.
- [x] The consistency audit in tests/test_consistency.py passes: frames, rules, FOL, DL, network and Prolog all use the same vocabulary.
- [x] python tools/build_all.py regenerates every trace, diagram and the report.

## Before submission

- [ ] On Windows with Word, run python tools/finalize_report.py --pdf after building (fills the contents and lists, writes the PDF). Otherwise open the report in Word and accept the request to update fields.
- [ ] Each member rehearses their own section of the viva guide and their part of the presentation script.
- [ ] Optional: install SWI-Prolog, run swipl prolog/smart_parking.pl, and check that ?- show_allocations. prints the three allocations.
