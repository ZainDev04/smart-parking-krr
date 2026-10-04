# Presentation script (about 3 minutes)

Four speakers, about 45 seconds each. Run the Streamlit app before starting, with the "Main demo: morning rush" scenario selected.

## Speaker 1: Syed Mohmmad Huzaifa (problem, frames, script)

"Our project is the Smart Parking Access and Space Allocation Reasoning System. At a university car park, whether someone may park depends on many things at once: who they are, whether their permit is still valid today, which zone the bay is in, the time, their vehicle, accessibility, reservations, and who else wants the same bay. Gate staff apply these rules from memory and rarely explain a refusal.

We captured the domain first as frames. Each class frame, such as ParkingSpace, has slots with facets: type, allowed range, default and if-needed procedures. Defaults are inherited and can be overridden. An accessible bay inherits from ParkingSpace but overrides the space type. A ParkingSession script describes the visit scene by scene, and each scene is checked by the reasoner."

(Show: Frames & script tab, instance s_a3, then run the script for Usman.)

## Speaker 2: Maaz ur Rehman (semantic network, DL, trade-off)

"From the same frames we generate the semantic network: is-a links for the hierarchy, part-of from bay to zone to facility, and relations such as owns and made-by. Because it is generated, its names always match the rules.

The terminology is also written in description logic: 45 axioms with subsumption, existential and universal restrictions, and disjointness. Our reasoner classifies the hierarchy. For example, it infers that every authorized student is an authorized driver, which nobody wrote down. It also catches a data error where a student is also recorded as faculty.

We chose where each logic is used by its trade-off. Full first-order logic is too expensive to execute because entailment is undecidable, DL is decidable but cannot chain rules, and Horn clauses always terminate and can explain themselves."

(Show: Semantic network tab, then Description logic tab with scenario TC12.)

## Speaker 3: Owais Tariq (FOL, Horn clauses, forward chaining)

"Every requirement was written in English, then in first-order logic, then converted to a Horn clause with exactly one conclusion. We have 28 rules and 7 denial constraints. Negative requirements are handled carefully. The only rule that uses negation, the final allocation, runs in a second stratum after all conflicts are known.

Forward chaining starts from 164 facts and fires every rule whose conditions hold, cycle by cycle, until nothing new appears. Here it reaches a fixpoint in 10 cycles with 105 new facts. You can see Sara winning bay s_a1 over Zara and Ali because her accessibility badge gives her priority 3."

(Show: Forward chaining tab, move the slider from cycle 1 to 10, filter on allocate and loses.)

## Speaker 4: Shaikh Muhammad Zain (backward chaining, evaluation)

"Backward chaining works the other way. It starts from a question, for example can_allocate(ahmed, S), and works back through the rules to the facts, with unification and backtracking, like Prolog. It returns three bays and a proof tree for each. When a goal fails, our explainer reports the first condition that blocked it. Ali was refused because Sara outranked him; Fatima because a motorbike fits no bay in her zone.

To check correctness, the two engines were written independently, and for every derived fact in all 13 scenarios they give exactly the same answers. Twelve test cases cover every requirement, and 68 unit tests pass. The same knowledge base is also exported as a Prolog program and an OWL ontology.

In short: frames and DL describe the domain, FOL states what must always hold, and Horn clauses decide quickly and explain every answer. Thank you."

(Show: Backward chaining tab with can_allocate(ahmed, S), then allocate(ali, s_a1), then Test cases tab.)
