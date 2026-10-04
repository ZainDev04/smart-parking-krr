# Viva preparation guide

The questions are grouped by topic. Every member should know the general section and section A. Then each member should know their own section thoroughly and be able to answer the basic questions of the other three, because the examiner may ask anyone anything. The answers are short on purpose: say the answer, then point at the code, the report or the UI to show it.

Owners:

- Syed Mohmmad Huzaifa (AI-23022): section B, frames and scripts
- Maaz ur Rehman (AI-23036): section C, semantic network, DL, expressivity
- Owais Tariq (AI-23037): section D, FOL, Horn clauses, forward chaining
- Shaikh Muhammad Zain (AI-23306): section E, backward chaining, implementation, testing

## A. General questions (everyone)

1. What problem does your project solve?
   It decides who may park in which campus bay. The decision depends on the person's category, permit validity, zone, opening hours, vehicle type, accessibility, occupancy, reservations and conflicts. Every decision comes with a proof or a reason for refusal.

2. Why does this domain need KRR and not just a database?
   A database only returns stored rows. It cannot derive that a faculty member is a person, it has no inheritance with defaults, its rules are hidden in application code, and it cannot explain its answers. Our system derives new facts from 28 explicit rules and explains every decision (report section 2.6).

3. What is a knowledge base?
   A set of facts and rules that represent what is known about a domain. Ours has 154 base facts (142 from frames plus 12 policy facts), per-scenario context facts, 28 Horn rules and 7 constraints, all in krr/knowledge_base.

4. What is an inference engine?
   The program that applies rules to facts to derive conclusions. We have two: a forward chainer (data-driven) and a backward chainer (goal-driven). Both read the same knowledge base.

5. Which KR paradigms did you use, and why each one?
   - Frames for structure and defaults.
   - A script for the event sequence of a parking session.
   - A semantic network for relations and inheritance.
   - FOL for precise constraints.
   - DL for the terminology and consistency checking.
   - Horn clauses for efficient, explainable rule execution.

6. How do you keep the paradigms consistent?
   There is one source of truth. Frames generate the facts, the semantic network and the DL ABox. The rule file drives both engines, the FOL listing and the Prolog file. tests/test_consistency.py checks that every name used anywhere exists in the knowledge base.

7. Walk us through one decision.
   Sara asks for s_a1 at 09:10. The derivation chain is:
   1. R06: her permit is valid.
   2. R07: it is a student permit and she is a student.
   3. R10: she is authorized.
   4. R13: she may enter zone_a, which is open (R12).
   5. R14: her car fits a standard bay.
   6. R15: she is eligible.
   7. R19: s_a1 is vacant, so it can be allocated.
   8. R21: she has priority 3 because she holds a badge, so R25 makes Zara and Ali lose.
   9. R28: nobody beats her, so she is allocated s_a1.

## B. Frames and scripts (Syed Mohmmad Huzaifa)

8. What is a frame?
   A structured representation of a concept or an individual, made of named slots (Minsky, 1974). Class frames describe kinds of things (ParkingSpace); instance frames describe individuals (s_a1).

9. What is a slot and what is a facet?
   A slot is an attribute or relation of a frame (spaceType, locatedIn). A facet is information about a slot. Ours are value, default, type, range, cardinality, if-needed, predicate and relation. Example: ParkingSpace.status has type symbol, range {vacant, occupied, reserved} and default vacant.

10. What is a default value, and how is it inherited?
    A value assumed when nothing more specific is known. To read a slot, the frame system looks at the instance's own value, then an if-needed procedure, then the nearest default up the ISA chain. Ali has no accessibilityBadge value, so he gets "no" from Person.

11. Give an example of overriding a default.
    ParkingSpace has the default spaceType standard. AccessibleSpace overrides it with accessible. s_a3 is an AccessibleSpace, so its spaceType is accessible, while s_a1 (a plain ParkingSpace) stays standard.

12. What is an if-needed procedure?
    A procedure attached to a slot that computes the value only when it is asked for (procedural attachment). ParkingZone.capacity counts the spaces located in the zone. ParkingSpace.zoneType reads the type of the space's zone.

13. Why not put defaults in the logic?
    Classical logic is monotonic: once something is derived, adding facts cannot remove it. A default must be overridable, which is non-monotonic. So the frame layer settles defaults first and passes one definite value per slot to the logic layer.

14. What is a script?
    A frame-like structure for a stereotyped sequence of events (Schank and Abelson). It has a track, roles, props, entry conditions, ordered scenes and results. Our ParkingSession script has 7 scenes: arrive, permit check, zone check, bay check, availability, allocation, park.

15. How is your script connected to reasoning?
    Each scene has a goal that the backward chainer proves. The script stops at the first failing scene and reports the reason. For example, Usman stops at "Permit check" because 20260915 >= 20261002 is false. Try python main.py script usman s_a1.

## C. Semantic network, description logic, expressivity (Maaz ur Rehman)

16. What is a semantic network?
    A graph whose nodes are concepts or individuals and whose labelled edges are relations (Quillian, 1968). Ours has is-a, instance-of, has-a, part-of, owns, made-by, for-space, has-type, has-class, grants and fits edges.

17. What is the difference between is-a, has-a and part-of?
    - is-a is subclass membership: Student is-a Person, so everything true of every Person is true of every Student.
    - has-a is possession: Person has-a ParkingPermit.
    - part-of is physical containment: ParkingSpace part-of ParkingZone part-of ParkingFacility.

18. How does inheritance work in your network?
    A node inherits the outgoing relation edges of every concept above it along is-a and instance-of. Faculty has no owns edge of its own but inherits "owns Vehicle" from Person.

19. What is description logic?
    A family of decidable fragments of FOL for describing concepts (classes), roles (binary relations) and individuals. The TBox holds terminology axioms, the ABox holds assertions. We use ALCI: ⊓, ⊔, ∃, ∀ and inverse roles.

20. What is subsumption? Give one told and one inferred example.
    C ⊑ D means every C is a D. Faculty ⊑ Employee is told (axiom T03). AuthorizedStudent ⊑ AuthorizedDriver is inferred: the reasoner derived it from the definitions T25 and T28, and nobody wrote it.

21. What is a disjointness axiom and why do you need it?
    C ⊓ D ⊑ ⊥ means nothing can be both. D01 Student ⊓ Employee ⊑ ⊥. In TC12 Ali is recorded as both student and faculty, and the reasoner reports the clash. Without disjointness, the data error would go unnoticed.

22. Explain an existential and a universal restriction from your TBox.
    - T15 ParkingSpace ⊑ ∃locatedIn.ParkingZone: every space is in at least one zone.
    - T19 AccessibleSpace ⊑ ∀allocatedTo.BadgeHolder: everyone an accessible bay is allocated to must be a badge holder. If the bay went to Ali, the reasoner would infer BadgeHolder(ali), which clashes with NonBadgeHolder(ali).

23. What is the open-world assumption?
    A missing fact means "unknown", not "false". The DL reasoner cannot say Usman is not authorized, only that it is not entailed. The Horn engine uses the closed-world assumption and says "no". The gate needs CWA; a shared ontology needs OWA.

24. Why is propositional logic not enough?
    It has no variables or quantifiers. R13 would need a separate rule for every person, permit and zone, and "every space is in some zone" cannot be written at all.

25. If FOL is so expressive, why not use it for everything?
    FOL entailment is only semi-decidable: a prover may never stop on a non-theorem. DL is decidable, and Horn clauses without function symbols always terminate in polynomial time. So we use FOL to specify and check, DL for terminology, and Horn clauses to execute.

## D. FOL, Horn clauses, forward chaining (Owais Tariq)

26. What are the parts of an FOL formula?
    Constants (ali, s_a1), variables (x, s), predicates (owns, permit_valid), connectives (¬ ∧ ∨ → ↔), quantifiers (∀ ∃) and equality.

27. What do the universal and existential quantifiers mean? Give examples.
    - ∀x φ: φ holds for every object. Example R01: ∀x (student(x) → person(x)).
    - ∃x φ: φ holds for at least one object. Example F09: ∃s (located_in(s, zone_a) ∧ space_free(s)), "there is a free bay in the student zone".

28. Why does order of quantifiers matter?
    In F01, ∀s (parking_space(s) → ∃z located_in(s, z)) says each space has its own zone. ∃z ∀s ... would claim one zone contains every space, which is false.

29. What is a Horn clause?
    A disjunction of literals with at most one positive literal. Three kinds:
    - Facts have one positive literal and no body.
    - Rules (definite clauses) have one positive literal and a body.
    - Goal or denial clauses have no positive literal, like our IC1-IC7.

30. How did you convert a rule to Horn form?
    For example: "Expired permits cannot authorize."
    1. Read it positively: a permit is valid if active, started and not expired.
    2. FOL: ∀p∀b∀e∀d ((permit_status(p, active) ∧ permit_start(p, b) ∧ permit_expiry(p, e) ∧ current_date(d) ∧ b ≤ d ∧ e ≥ d) → permit_valid(p)).
    3. Clause form has one positive literal, permit_valid(p).
    4. Prolog: R06.

31. How do you handle negation if Horn clauses cannot have it?
    Three ways:
    - Positive encoding: only vacant bays are free.
    - Closed-world denial: no allocation is derived.
    - Stratified negation as failure, in R28 only: not loses(X, S), which is checked after loses is fully computed in stratum 0.

32. Explain your forward chaining algorithm.
    1. Start with all facts in working memory.
    2. Each cycle, build the conflict set (every rule instance whose body matches the facts known at the start of the cycle).
    3. Fire the instances with new conclusions and add those facts.
    4. Repeat until a cycle adds nothing (fixpoint), then do the same for stratum 1.

    The main scenario takes 10 cycles and derives 105 facts.

33. What is a conflict set? What is refraction?
    The conflict set is all rule instances that could fire now. Refraction means an instance whose conclusion is already known is not fired again, which guarantees termination.

34. Why does forward chaining terminate?
    There are no function symbols, so only finitely many ground atoms exist, and each productive cycle adds at least one new one.

## E. Backward chaining, implementation, testing (Shaikh Muhammad Zain)

35. Explain backward chaining.
    1. Start from a goal.
    2. Find a fact that matches it, or a rule whose head unifies with it.
    3. Replace the goal by the rule's body as subgoals.
    4. Prove the subgoals depth first, left to right.
    5. On failure, backtrack to the next alternative.

    This is SLD resolution, as in Prolog.

36. What is unification?
    Finding a substitution that makes two atoms identical. can_allocate(X, S) and can_allocate(ali, s_a1) unify with {X=ali, S=s_a1}. Two different constants never unify.

37. Why are variables renamed (P_5, T_1) in the trace?
    Standardising apart. Each use of a rule gets fresh variable names so that its variables do not clash with variables already bound in the goal or in other rule uses.

38. How does your backward chainer avoid infinite loops?
    A subgoal that is a variant of one of its own ancestors is refused (loop check), and there is a depth limit. A unit test with a cyclic path rule checks this.

39. Forward vs backward chaining: when do you use which?
    - Forward chaining is data-driven. It computes everything at once, which suits deciding the whole morning batch (105 firings).
    - Backward chaining is goal-driven. It answers one question and gives the proof and the reason for failure, which suits one driver at the gate.

    Backward chaining can repeat work. Proving allocate(sara, s_a1) took 2,240 steps because it recomputes shared subgoals; tabling would fix that.

40. How do you know your engines are correct?
    - They are independent implementations, yet for every derived predicate in all 13 scenarios they return exactly the same answers.
    - The forward closure is checked to be a model of every rule.
    - Each firing is checked to use only facts that were already known.
    - All 12 test cases match their expected results.
    - The generated Prolog file allows a third, external check in SWI-Prolog.

41. How does the "why not" explanation work?
    For each rule that could conclude the goal, it finds how far the body can be proved and reports the first blocked literal. If that literal is derived, it explains it one level deeper. Example: allocate(fatima, s_e1) is blocked at fits(motorbike, standard).

42. What does each part of the code do?
    - krr/core: terms, unification, rules, stratification.
    - krr/frames: frames and the script.
    - krr/knowledge_base: facts, rules, scenarios.
    - krr/reasoning: forward, backward, explain.
    - krr/logic: FOL and DL.
    - krr/semantic_net: the network.
    - krr/export: Prolog, OWL, diagrams.
    - main.py: CLI.
    - app.py: Streamlit UI.
    - tests: 68 unit tests.

## Demonstration checklist for the viva

1. python main.py cases: all 12 cases, both engines agree.
2. streamlit run app.py, Forward chaining tab: move the cycle slider from 1 to 10.
3. Backward chaining tab: query can_allocate(ahmed, S) and show the three answers and the proof tree.
4. Query allocate(ali, s_a1) in the main scenario: show the "why not" explanation (Sara won on priority).
5. Description logic tab, scenario TC12: show the clash.
6. Frames tab: open s_a3 and point to "default from AccessibleSpace".
