{{titlepage}}

{{rubric}}

# Acknowledgements

We thank our course instructor, Miss Dure Shahwar, for the CT-351 lectures on frames, description logic and resolution that this project builds on, and the Department of Computer Science and Information Technology at NED University for the lab time we used to build and test the system.

# Executive summary

A university car park has more rules than it looks. Whether a driver may park depends on what kind of person they are, which permit they hold and whether it is still valid, which zone the bay is in and whether that zone is open, whether the vehicle fits the bay, whether the bay needs an accessibility badge, whether it is free or reserved, and who else wants the same bay. Gate staff apply these rules from memory, and refused drivers are rarely told why.

We built a knowledge-based system that makes this decision and explains it. The domain is modelled in five ways that share one vocabulary. Frames hold the concepts, their slots, facets and default values, and a ParkingSession script describes the stages of a visit. A semantic network generated from the frames shows how the concepts relate. First-order logic states the rules and twelve further constraints with explicit quantifiers, and a description logic TBox of 45 axioms gives the class hierarchy, restrictions and disjointness. The policy that actually runs is 28 Horn clauses and 7 denial constraints.

Two inference engines written in plain Python run the Horn rules. The forward chainer starts from {{stat facts}} facts and derives {{stat derived}} new ones in {{stat cycles}} cycles, using stratified negation for the one "unless" in the policy. The backward chainer proves single goals by SLD resolution and records every step, and a third module explains why a goal fails. A DL reasoner classifies the TBox and checks the data for contradictions, and an FOL model checker tests the twelve constraints on every run.

Twelve test cases cover valid and expired permits, visitors without passes, occupied and reserved bays, wrong zones, vehicles that do not fit, accessible bays, conflicting requests, double bookings, closing hours and bad data. Both engines give the expected answer in all {{stat goal_checks}} goal checks, and they derive exactly the same facts in every scenario. The {{stat unit_tests}} unit tests pass. The system has a command-line interface, a Streamlit web interface and a generated SWI-Prolog version of the same knowledge base.

# Table of contents

{{toc}}

# List of figures

{{lof}}

# List of tables

{{lot}}

{{endcols}}

# Chapter 1: Introduction {newpage}

This chapter sets out the problem, why it suits knowledge-based reasoning, what the system must do and what it leaves out. It covers the first rubric criterion (problem statement and motivation) and the domain requirements that the CCP guide asks for in the text summary.

## 1.1 Background

Smart parking systems usually mean sensors and apps that show free bays. The harder part is deciding who is allowed to use which bay. That decision rests on policy (permits, zones, accessibility, reservations) rather than on sensor data, and policy is exactly what knowledge representation is for: facts about the world, rules that say what follows from them, and a reasoner that applies the rules the same way every time and can show its working.

## 1.2 Problem statement

Given structured facts about people, vehicles, permits, zones, bays and reservations, plus today's date, the current hour and a list of requests, decide for every request whether the driver may enter and which bay they get. Every "yes" must come with the chain of facts and rules that supports it, and every "no" must come with the first condition that failed. The policy must be written once, in a form that can be read, checked and changed without rewriting code.

## 1.3 Motivation

Three problems with the current manual process drove the project. Decisions are inconsistent, because two guards can apply the same rule differently. Decisions are unexplained, so a refused driver cannot tell whether the problem is their permit, the zone or the bay. Policy changes are slow, because they live in people's heads or in scattered code.

A database alone does not fix this (section 2.6). The domain also needs every paradigm in the course: a class hierarchy with defaults, a fixed sequence of events, typed relations, quantified constraints, disjoint classes and many if-then rules that must run fast.

## 1.4 Domain requirements

The rules below came out of knowledge acquisition (section 2.4). The rule numbers in brackets are where each requirement is implemented.

1. General parking needs a valid permit: status active, and today on or after its start date and on or before its expiry date (R06, R10).
2. A permit counts only for the kind of person it was issued to: student permits for students, employee permits for faculty and staff, visitor passes for visitors (R07-R09).
3. A visitor without a one-day visitor pass is not authorized (R09).
4. Students may use only student zones, employees only the employee zone, visitors only the visitor zone (R13 with the grants/2 table).
5. Nobody may enter a zone outside its opening hours (R12).
6. A vehicle gets only a bay it fits: cars use standard bays, electric cars also use EV bays, motorbikes use motorbike bays (R14 with the fits/2 table).
7. Accessible bays are only for accessibility badge holders (R16).
8. An occupied bay is never allocated (R17, R19, IC3).
9. A reserved bay goes only to the person holding today's reservation for it (R18, R20).
10. A person with two reservations on the same day gets nothing until the conflict is resolved (R27, R28).
11. When several eligible drivers want one bay, the highest priority wins (badge holders 3, employees 2, students and visitors 1), and the earlier request breaks a tie (R21-R26).
12. A bay never goes to two people and nobody gets two bays (IC1, IC2).
13. Nobody is both a student and an employee, a student and a visitor, an employee and a visitor, or faculty and staff (IC4-IC7, DL axioms D01-D04).

## 1.5 Project objectives

1. Represent the domain with frames (at least ten class frames with slots, facets and defaults), a script and a semantic network generated from the frames.
2. Write every rule in FOL with explicit quantifiers, plus at least ten constraints that go beyond Horn form, and check them on the data.
3. Write a DL TBox with subsumption, existential and universal restrictions, definitions and disjointness, and a reasoner that classifies it and finds contradictions.
4. Convert the policy into Horn clauses and run it with working forward and backward chaining engines that produce step-by-step traces.
5. Pass at least the eight test cases in the template with both engines, and show that the two engines derive the same facts.

## 1.6 Scope

The system covers one campus car park with three zones and nine bays, eight people and one day of requests. It decides access and allocation and explains each decision. It does not read live sensors, take payments, plan routes, handle hourly reservations or learn from data. Times are whole hours and dates are YYYYMMDD integers.

## 1.7 Proposed solution

The solution has four layers (Figure 1). The representation layer holds the frames, script, semantic network, FOL statements and DL TBox. All of them feed one knowledge base of facts and Horn rules. The inference layer has the forward and backward chainers, the why-not explainer, the DL reasoner and the FOL model checker. On top sit a command-line interface, a Streamlit web interface and a public website (section 10.9). A build script regenerates the Prolog program, the OWL ontology, the trace sheets and this report from the code, so the report cannot drift from what the engines do.

## 1.8 Report organization

Chapter 2 analyses the domain and Chapter 3 gives the overall knowledge model. Chapters 4 to 7 cover frames and the script, the semantic network, FOL and description logic. Chapter 8 lists the Horn knowledge base and Chapter 9 the inference engine with its traces. Chapters 10 to 14 cover implementation, testing, the expressivity and tractability trade-off, limitations and the conclusion. The appendices hold the full listings, code, screenshots and team evidence.

# Chapter 2: Domain analysis and knowledge acquisition

This chapter describes the parking domain, its entities and relationships, where the rules came from and which constraints they must respect. It ends by explaining why a plain database is not enough, which is one of the items the CCP guide asks for in the text summary.

## 2.1 Smart parking domain

The test campus is modelled on the NED main campus car park. It has one facility (ned_lot) with three zones: zone_a for students (open 07:00-22:00, five bays), zone_e for employees (06:00-23:00, three bays) and zone_v for visitors (08:00-17:00, one bay). The bays include an accessible bay, a motorbike bay, an EV charging bay, one occupied bay and two reserved bays. Eight people use it. Ali, Sara, Usman and Zara are students; Sara holds an accessibility badge and Usman's permit expired on 15 September 2026. Dr. Ahmed is faculty and drives an electric car, Fatima is staff and rides a motorbike, and Bilal and Hina are visitors, only Bilal with a pass. The main scenario is the morning rush of 2 October 2026, with eight requests between 08:00 and 09:20.

## 2.2 Domain entities

Table: Domain entities
{{entities}}

## 2.3 Domain relationships

People are related to the class hierarchy by is-a (Student is-a Person, Faculty is-a Employee). A person owns vehicles and has-a permit. A bay is located in (part of) a zone, which is part of the facility. A reservation is made by a person for a bay on a date, so it is a reified three-way relation. Value relations tie the policy together: a permit class grants a zone type and a vehicle type fits a space type. The reasoner derives further relations from these, the most important being eligible-for (eligible_for_space) between a person and a bay, and allocate between a driver and the bay they get.

## 2.4 Knowledge acquisition

We collected the kind of documents a university parking office publishes: permit categories and validity, zone signs and hours, the accessible parking policy, the reservation procedure and the rule for disputed bays. Where NED does not publish a rule, we wrote down an explicit project assumption (for example the three-level priority scale).

Two of us then played the parking officer and the gate guard while the others asked "what happens if" questions. Every answer was written as an if-then sentence. "Can a student park with an expired permit?" became "a permit is valid if its status is active and it has not expired", which is R06. Nouns in these sentences became classes, categories became slot values, verbs became relations, and repeated patterns ("faculty and staff both...") became superclasses such as Employee.

Finally every requirement became a test scenario with an expected answer, and we fixed the knowledge base until all of them passed. One error found this way: the first draft let an ineligible driver make others lose a conflict, so R25 and R26 now require the winner to satisfy can_allocate.

## 2.5 Domain constraints

The hard constraints are requirements 8, 12 and 13 of section 1.4: no occupied bay is allocated, no bay goes to two people, nobody gets two bays and the person classes are disjoint. These are checked after every run as denial clauses IC1-IC7. The policy also has exceptions that the rules must handle: a reserved bay is not free but may still go to its holder (R20), an employee permit opens a zone a student permit does not (R13), and an accessible bay is suitable for a car but still needs a badge (R16).

## 2.6 Limitations of traditional database systems

A relational database could store every fact here and is better than our system at storage, concurrency and large queries. It falls short on reasoning:

- It answers only what is stored. Concluding that Dr. Ahmed is a person because faculty are employees and employees are people needs a join written by hand into every query; the reasoner derives it once from R04 and R02.
- Business rules end up spread over application code, triggers and stored procedures, where they cannot be listed or checked together. Here all 28 rules are in one file and printed in Chapter 8.
- A query result carries no explanation. The backward chainer returns a proof tree for every "yes" and the failing condition for every "no".
- Check constraints cannot express statements such as "whoever gets an accessible bay holds a badge" (F07), which quantify across several tables.
- A database works under the closed-world assumption only. The DL layer also supports the open-world reading (section 7.7), which can tell "not authorized" from "not known to be authorized".

# Chapter 3: Knowledge representation architecture

This chapter gives the overall knowledge model, the concept hierarchy and which paradigm is used for what. It is the map for Chapters 4 to 8.

## 3.1 Overall knowledge model

![System architecture and knowledge model](figures/architecture.png)

Knowledge enters through the frames. The frame system settles every default and writes one fact per slot value, so the Horn knowledge base never re-types a fact. The same predicate names are used in the semantic network, FOL, DL and the Prolog export, and a unit test (tests/test_consistency.py) fails if any layer uses a name the others do not.

## 3.2 Concept hierarchy

Person has three subclasses, Student, Employee and Visitor, and Employee has two, Faculty and Staff. ParkingSpace has AccessibleSpace, EVChargingSpace and MotorbikeSpace. Vehicle, ParkingPermit, ParkingZone, ParkingFacility and Reservation have no subclasses as frames; in the DL layer, Vehicle splits into Car, ElectricCar and Motorbike and ParkingPermit into StudentPermit, EmployeePermit, VisitorPass and ValidPermit. Value concepts (VehicleType, SpaceType, ZoneType, PermitClass) hold the allowed symbolic values. The frame hierarchy is drawn in section 4.1.

## 3.3 Knowledge representation paradigms

Table: Role of each paradigm in the project
| Paradigm | Purpose in this project | Example |
| --- | --- | --- |
| Frames and script | Concepts with slots, facets and inherited defaults; the stages of a parking visit | AccessibleSpace overrides spaceType = accessible |
| Semantic network | Visual map of concepts and relations, with inheritance and path queries | ParkingSpace part-of ParkingZone |
| FOL | Exact statement of rules and constraints with quantifiers | ∀s (parking_space(s) → ∃z (parking_zone(z) ∧ located_in(s, z))) |
| Description logic | Classes, roles, subsumption, restrictions and disjointness; consistency checking | AuthorizedStudent ≡ Student ⊓ ∃hasPermit.(ValidPermit ⊓ StudentPermit) |
| Horn clauses | The executable policy, run by forward and backward chaining | `authorized(X, P) :- permit_matches_role(X, P), permit_valid(P).` |

# Chapter 4: Frames and scripts

This chapter documents the frame system: its structure, each class frame with its slots and facets, and the ParkingSession script. It covers the frames half of rubric criterion 2.

## 4.1 Frame architecture

A frame is a named structure with slots. Class frames describe a kind of thing and instance frames describe one individual; each has an ISA link to its parent and inherits all of its ancestors' slots. Each slot carries facets: type (str, int, symbol or frame:Class for a link), default, range (allowed values), cardinality, an if-needed procedure, the logic predicate it becomes and the network relation it becomes.

When a slot of an instance is read, the system looks in three places in order: the instance's own value, an if-needed procedure on the class or an ancestor, and the nearest default up the ISA chain. A subclass can override a default. ParkingSpace says spaceType is standard and AccessibleSpace says accessible, so s_a3 gets accessible without storing it. Logic cannot override a conclusion, so the frame layer settles defaults first and hands one definite value per slot to the logic layer. This is how accessibility_badge(ali, no) reaches the knowledge base without anyone typing it. The 38 instance frames produce 135 facts, and FrameSystem.validate() checks every value against its type, range and cardinality facets.

![Frame hierarchy with slots and links](figures/frame_hierarchy.png)

## 4.2 Frame: Person

Person is the root of the people hierarchy. Its four slots are inherited by every subclass. accessibilityBadge has the default no, so only Sara needs an explicit value.

Table: Frame Person
{{frame Person}}

## 4.3 Frame: Student

Student inherits fullName, accessibilityBadge, owns and hasPermit from Person and adds two slots of its own.

Table: Frame Student (own slots)
{{frame Student}}

## 4.4 Frame: Faculty / Staff

Faculty and Staff both sit under Employee, which carries employeeId and department so that the employee rules apply to both. Faculty has the default designation Lecturer, which Dr. Ahmed overrides with Assistant Professor.

Table: Frames Employee, Faculty and Staff
{{frame Employee Faculty Staff}}

## 4.5 Frame: Visitor

Table: Frame Visitor (own slots)
{{frame Visitor}}

A visitor has no permit by default. Bilal's hasPermit slot is filled with the one-day pass vp_bilal; Hina's is empty, which is why R09 cannot fire for her.

## 4.6 Frame: Vehicle

Table: Frame Vehicle
{{frame Vehicle}}

Six of the eight vehicles take the default car; ev_ahmed and bike_fatima set their own type.

## 4.7 Frame: Parking permit

Table: Frame ParkingPermit
{{frame ParkingPermit}}

## 4.8 Frame: Parking space

ParkingSpace has the if-needed slot zoneType, which follows locatedIn to the zone and reads that zone's type. The three subclasses override the spaceType default and add their own slots.

Table: Frames ParkingSpace and subclasses
{{frame ParkingSpace AccessibleSpace EVChargingSpace MotorbikeSpace}}

## 4.9 Frame: Parking zone

capacity is computed on demand: it counts the bays whose locatedIn is this zone, so zone_a gives 5 and nobody has to keep the number up to date.

Table: Frame ParkingZone
{{frame ParkingZone}}

## 4.10 Frame: Reservation

A reservation links three things (person, bay, date), so it is a frame of its own rather than a slot on Person. Its three slots become the binary predicates reserved_by, reserved_space and reservation_date.

Table: Frame Reservation
{{frame Reservation}}

## 4.11 Script / event sequence

A frame describes a thing; a script describes a stereotyped sequence of events (Schank and Abelson, 1977). ParkingSession has the usual parts: track (campus parking with a permit or pass), roles (driver, gate system, parking office), props (vehicle, permit, zone, bay, reservation), entry conditions (a registered vehicle, a request, a known date and hour) and results (bay occupied, driver parked). Its seven scenes (Figure 3) are arrive at the gate, permit check, zone check, bay check, availability, allocation and park. Together they cover the steps the template asks for: request, validate, check eligibility, find a suitable bay, resolve conflicts, and allocate or deny.

![ParkingSession script scenes](figures/parking_script.png)

The script runs. Each scene asks the backward chainer one goal and the script stops at the first scene that fails, with the reason from the explainer:

```
Running script ParkingSession for driver=usman, space=s_a1
  Scene 1 Arrive at gate   PASS  requests(usman, s_a1, T)
  Scene 2 Permit check     STOP  authorized_driver(usman)
      reason: permit_valid(p_usman) fails at 20260915 >= 20261002 (false)
```

For Fatima and s_e1 the script gets one scene further and stops at the bay check, because her motorbike does not fit a standard bay. For Sara and s_a1 all six checks pass and scene 7 changes the bay's status to occupied.

# Chapter 5: Semantic network

This chapter presents the semantic network, the relation types it uses and the paths that answer domain questions. It covers the second half of rubric criterion 2.

## 5.1 Semantic network design

The network is generated from the frames: every class frame is a node, every ISA link an is-a edge and every frame-valued slot a labelled edge. Because it is generated, its labels always match the frame and rule vocabulary. The first figure below shows the concept level. The second shows one worked example: Ali, his car and permit, Zara's reservation r1 and the bay, zone and values on the paths in section 5.3.

![Concept-level semantic network](figures/semantic_network.png)

![Semantic network with individuals](figures/semantic_network_example.png)

## 5.2 Relationship types

Table: Relationship types in the semantic network
| Relationship | Meaning | Example |
| --- | --- | --- |
| is-a | Subclass link; the child inherits every relation of the parent | Student is-a Person |
| instance-of | Individual to its class | ali instance-of Student |
| has-a | A person holds a permit | Person has-a ParkingPermit |
| owns | A person owns a registered vehicle | Person owns Vehicle |
| part-of (located-in) | Physical containment | ParkingSpace part-of ParkingZone part-of ParkingFacility |
| made-by, for-space (reserves) | The two sides of a reservation | Reservation made-by Person; Reservation for-space ParkingSpace |
| has-type, has-class | Entity to a value concept | ParkingSpace has-type SpaceType |
| grants, fits | Policy between value concepts | PermitClass grants ZoneType; VehicleType fits SpaceType |
| eligible-for (derived) | Produced by the rules, not stored | ali eligible_for_space s_a1 |

## 5.3 Semantic network walkthrough

1. Faculty to Person: Faculty is-a Employee is-a Person. Faculty has no owns edge of its own, but inherits "owns Vehicle" along this path, which is how Dr. Ahmed can own ev_ahmed.
2. Bay to facility: s_a1 instance-of ParkingSpace, part-of zone_a, part-of ned_lot. This is the containment chain the DL axioms T15 and T16 require.
3. Permit to zone: p_ali has-class student_permit, which grants student_zone, which is the has-type of zone_a. This path is rule R13 drawn as a graph.
4. Vehicle to bay: car_ali has-type car, which fits standard, which is the has-type of s_a1. This path is the fit test in R14; for Fatima the path motorbike fits standard does not exist, which is why TC6 fails.
5. Reservation: r1 made-by zara and r1 for-space s_a5. Ali has no made-by edge into any reservation for s_a5, so R20 cannot allocate it to him (TC11).
6. Path query: the shortest chain from Faculty to ParkingZone found by the network code is Faculty is-a Employee is-a Person, made-by from Reservation, for-space ParkingSpace, part-of ParkingZone.

# Chapter 6: First-order logic (FOL)

This chapter defines the FOL language, the facts, the rules with their quantifiers and twelve further statements that go beyond Horn form. Together with Chapter 7 it covers rubric criterion 3.

## 6.1 FOL vocabulary

- Constants name individuals and values: ali, p_ali, s_a1, zone_a, car, accessible, 20261002.
- Variables are lower case in formulas (x, s, p) and upper case in Horn clauses (X, S, P).
- Unary predicates give class membership: person, student, employee, faculty, staff, visitor, vehicle, permit, parking_zone, parking_space, reservation.
- Binary predicates give attributes and relations: owns, has_permit, permit_class, permit_status, permit_start, permit_expiry, vehicle_type, located_in, part_of, space_type, space_status, zone_type, zone_opens, zone_closes, reserved_by, reserved_space, reservation_date, accessibility_badge, grants, fits.
- Context predicates: current_date(d), current_hour(h), requests(x, s, t).
- Derived predicates: permit_valid, permit_matches_role, authorized, authorized_driver, zone_open, zone_access, suitable_space, eligible_for_space, space_free, holds_reservation, can_allocate, priority, loses, double_booked, allocate.
- Connectives and quantifiers: ¬, ∧, ∨, →, ∀, ∃, =, and the comparisons ≥, ≤, >, < on dates and hours stored as integers. No function symbols are used.

## 6.2 Domain facts

Facts are ground atoms. Some examples from the knowledge base, with their meaning:

- student(ali): Ali is a student.
- has_permit(ali, p_ali) ∧ permit_class(p_ali, student_permit): Ali holds a student permit.
- permit_expiry(p_usman, 20260915): Usman's permit expired on 15 September 2026.
- permit_start(vp_bilal, 20261002) ∧ permit_expiry(vp_bilal, 20261002): Bilal's visitor pass is valid on 2 October 2026 only.
- requests(sara, s_a1, 910): Sara asked for s_a1 at 09:10.

## 6.3 FOL rules

A Horn rule head :- b1, ..., bn is read as ∀x1...∀xk ((b1 ∧ ... ∧ bn) → head), where x1...xk are all its variables. The table below gives ten of the 28 rules; the FOL column is printed by Rule.to_fol() from the same rule objects the engines run. The rest are in Appendix B.

Table: FOL form of selected rules
{{fol_rules R04 R06 R07 R10 R11 R13 R14 R16 R19 R25}}

## 6.4 Quantifier usage

Every rule is universally quantified over all its variables, and the scope of each quantifier is the whole implication. A variable that appears only in the body can equally be read as existential inside the antecedent. R11 is the clearest case: ∀x ∀p (authorized(x, p) → authorized_driver(x)) is equivalent to ∀x (∃p authorized(x, p) → authorized_driver(x)), "anyone authorized by some permit is an authorized driver".

Some knowledge cannot be written as a Horn rule because it needs ∃ in the conclusion, disjunction, equality or classical negation. The next table lists twelve such statements. The model checker evaluates each one on the model built by forward chaining (domain: all {{stat constants}} constants) and returns a counterexample if one fails.

Table: Further FOL statements
{{fol_statements}}

- F01 has the pattern ∀s (... → ∃z ...): for every bay there is a zone. Swapping the quantifiers to ∃z ∀s would claim that one zone holds every bay, which is false.
- F05 needs three universal variables because it compares two allocations of the same bay.
- F09 is purely existential. Backward chaining answers it with the query located_in(S, zone_a), space_free(S) and returns S = s_a1.
- F10 has ¬∃p inside the antecedent. It holds in our model but does not follow from the rules in classical FOL; it needs the closed-world assumption (section 8.4).

## 6.5 Consistency verification

Each formula was checked in four ways. Every variable is bound by exactly one quantifier whose scope is the whole formula. Every head variable of a rule also appears in a positive body literal, and every variable in a comparison or under "not" is bound earlier (range restriction, enforced by Rule.check_safety() when the rule is parsed). Every implication points from the conditions to the conclusion. Finally the statements are evaluated on real data: all twelve hold on the main scenario, and F04 fails on the TC12 data with the counterexample x = ali, which is the expected result.

# Chapter 7: Description logic

This chapter gives the DL concepts, roles and axioms, a sample of the ABox, and what each kind of axiom means. The language is ALCI: ⊓, ⊔, ∃R.C, ∀R.C, inverse roles R⁻ and ⊥.

## 7.1 DL concepts

Atomic concepts: Person, Student, Employee, Faculty, Staff, Visitor, BadgeHolder, NonBadgeHolder, Vehicle, Car, ElectricCar, Motorbike, ParkingPermit, StudentPermit, EmployeePermit, VisitorPass, ValidPermit, ParkingFacility, ParkingZone, ParkingSpace, AccessibleSpace, EVChargingSpace, MotorbikeSpace and Reservation. Defined concepts: ValidPermitHolder, AuthorizedStudent, AuthorizedEmployee, AuthorizedVisitor and AuthorizedDriver.

## 7.2 DL roles

Each role is one binary predicate of the knowledge base, so the ABox is read straight from the facts.

Table: DL roles
{{dl_roles}}

## 7.3 Subsumption axioms

C ⊑ D says every C is a D. These axioms build the hierarchy and are the same knowledge as Horn rules R01-R05.

Table: Subsumption axioms
{{dl_axioms sub}}

## 7.4 Disjointness axioms

C ⊓ D ⊑ ⊥ says no individual is in both. Disjointness is inherited: D01 makes Faculty and Student disjoint too, because Faculty ⊑ Employee.

Table: Disjointness axioms
{{dl_axioms disjoint}}

## 7.5 Membership assertions

ABox concept assertions come from the frames and from derived facts; role assertions come from the binary facts. The main scenario has 114 assertions, for example Student(ali), Faculty(ahmed), NonBadgeHolder(ali), BadgeHolder(sara), AccessibleSpace(s_a3), ValidPermit(p_ali), StudentPermit(p_ali), hasPermit(ali, p_ali), owns(ahmed, ev_ahmed), locatedIn(s_a1, zone_a), partOf(zone_a, ned_lot), madeBy(r1, zara) and forSpace(r1, s_a5).

## 7.6 Existential and universal restrictions

Table: Restrictions
{{dl_axioms restrict}}

Table: Defined concepts
{{dl_axioms equiv}}

## 7.7 DL interpretation

The ∃ axioms (T15-T18) say that something must exist: every bay is in some zone, every vehicle has some owner. They do not name it. The ∀ axioms (T19, T20) restrict whatever fillers exist: anyone an accessible bay is allocated to must be a badge holder. The definitions (T24-T28) work in both directions, so the reasoner can recognise an AuthorizedStudent from her permit, not only list her.

The reasoner classifies the TBox and finds {{stat inferred}} subsumptions that nobody wrote, such as AuthorizedStudent ⊑ AuthorizedDriver (from T25 and T28). Realization agrees with the Horn rules: an individual is an AuthorizedDriver in DL exactly when authorized_driver holds after forward chaining, and a unit test checks this for all eight people. T19 is active too: if a test forces s_a3 to be allocated to Ali, ∀-propagation adds BadgeHolder(ali), which clashes with NonBadgeHolder(ali) through D05, and the reasoner reports it. In TC12 the reasoner reports "ali is both Employee and Student, which D01 declares disjoint".

The DL reasoner uses the open-world assumption. Usman holds a permit, but nothing says it is a ValidPermit, so the reasoner cannot conclude AuthorizedDriver(usman), and it cannot conclude the negation either; the answer is "unknown". The Horn engine uses the closed-world assumption, so authorized_driver(usman) is simply false and Usman is turned away. The gate needs the closed-world answer; a shared ontology needs the open-world reading, because a missing fact there usually means "not recorded".

# Chapter 8: Knowledge base and Horn clauses

This chapter separates the base facts from the derived facts, lists the rules and shows how each requirement became a Horn clause. It covers the Horn clause half of rubric criterion 4.

## 8.1 Knowledge base

The knowledge base of the main scenario has {{stat facts}} base facts: 142 from the frames, 12 policy facts (grants/2, fits/2, open_type/1) and 10 context facts (date, hour and eight requests). Forward chaining adds {{stat derived}} derived facts such as permit_valid, zone_access, priority and allocate. Base facts are never changed by the rules; derived facts are recomputed on every run, so a change in the data always gives a fresh, consistent result.

## 8.2 Facts

A fact is a Horn clause with no body. A representative sample:

```
student(ali).  faculty(ahmed).  staff(fatima).  visitor(bilal).  accessibility_badge(sara, yes).
has_permit(ali, p_ali).  permit_class(p_ali, student_permit).  permit_start(p_ali, 20260701).  permit_expiry(p_ali, 20270630).
owns(ahmed, ev_ahmed).  vehicle_type(ev_ahmed, electric_car).  vehicle_type(bike_fatima, motorbike).
located_in(s_a1, zone_a).  space_type(s_a3, accessible).  space_status(s_a2, occupied).
zone_type(zone_a, student_zone).  zone_opens(zone_a, 7).  zone_closes(zone_a, 22).
reserved_by(r1, zara).  reserved_space(r1, s_a5).  reservation_date(r1, 20261002).
grants(student_permit, student_zone).  fits(car, standard).  fits(electric_car, ev_charging).
current_date(20261002).  current_hour(10).  requests(sara, s_a1, 910).
```

The full list of {{stat facts}} facts is in Appendix A.

## 8.3 Rules

A rule is a definite Horn clause: exactly one positive literal (the head) and one or more body literals. The 28 rules fall into eight groups: class hierarchy (R01-R05), permits and authorization (R06-R11), zones and time (R12-R13), suitability and eligibility (R14-R16), availability (R17-R20), priority (R21-R24), conflicts (R25-R27) and the decision (R28). A Horn clause with no positive literal is a denial, written `:- body.`, which says the body must never be true. IC1-IC7 are checked after every forward-chaining run.

Table: Horn rule base and constraints
{{horn_table}}

## 8.4 Horn clause conversion

Each requirement went through four steps: an if-then sentence, an FOL formula, a rewrite so that the conclusion is a single atom, and Prolog syntax. Three examples:

**Expired permits cannot authorize parking.** Read positively: a permit is valid only if it is active, has started and has not expired. FOL: ∀p ∀b ∀e ∀d ((permit_status(p, active) ∧ permit_start(p, b) ∧ permit_expiry(p, e) ∧ current_date(d) ∧ b ≤ d ∧ e ≥ d) → permit_valid(p)). As a clause: ¬permit_status(p, active) ∨ ¬permit_start(p, b) ∨ ¬permit_expiry(p, e) ∨ ¬current_date(d) ∨ ¬(b ≤ d) ∨ ¬(e ≥ d) ∨ permit_valid(p), which has one positive literal and is therefore Horn (R06). An expired or not-yet-started permit never satisfies the body, so it can never authorize. The start date matters for Bilal: his one-day pass has the same start and expiry date, so it is valid on 2 October 2026 and on no other day.

**A student may use a student bay.** Taken literally this needs a disjunction over every kind of person and zone. Splitting by permit class and moving the pairing into the policy table grants/2 gives one Horn rule (R13) and three facts. A new zone type now needs one new fact, not a new rule.

**Allocate the bay unless someone with higher priority wants it.** "Unless" is negation, which a definite clause cannot contain. The positive part becomes loses(Y, S), derived when another eligible requester outranks Y (R25, R26). The decision R28 then uses negation as failure, `not loses(X, S)`. The rules are layered into strata: loses/2 and double_booked/1 are fully computed in stratum 0 before R28 runs in stratum 1, so "not" means "cannot be derived" and the result does not depend on rule order. This is the only place negation is used, and the stratifier rejects any rule set with recursion through negation.

Other negative requirements are handled positively. "Occupied bays cannot be allocated" becomes "only vacant bays, or bays reserved for the requester, can be allocated" (R19, R20), and IC3 confirms the outcome. The built-in comparisons ≥, >, < and ≠ are evaluated, never stored, as in Prolog.

# Chapter 9: Inference engine: forward and backward chaining

This chapter explains both engines, gives their pseudocode and shows step-by-step traces generated by running them. None of the traces below is written by hand. It covers the chaining half of rubric criterion 4.

## 9.1 Inference engine architecture

![Inference engine architecture](figures/reasoning_engine.png)

Both engines read the same knowledge base. A request can be answered goal-first (backward) or data-first (forward). Forward results go through the integrity constraints before they are reported; backward results come back as a proof tree or, on failure, as a why-not explanation.

## 9.2 Forward chaining algorithm

Forward chaining is data-driven: it starts from the facts and fires rules until nothing new appears (krr/reasoning/forward.py).

```
procedure FORWARD-CHAIN(facts, rules)
    WM := facts
    for each stratum k = 0, 1 do                  # stratum 1 holds only R28
        repeat
            snapshot := copy(WM)
            conflict_set := { (r, θ) : r in rules of stratum k,
                              body(r)θ is true in snapshot }
            new := { head(r)θ : (r, θ) in conflict_set, head(r)θ not in WM }   # refraction
            log each firing (rule, bindings, premises, new fact)
            WM := WM ∪ new
        until new = ∅                             # fixpoint for this stratum
    check denial constraints IC1-IC7 on WM
    return WM
```

Because each cycle reads from a snapshot, a fact derived in cycle n is first used in cycle n + 1, so the cycle number is the length of the longest chain behind each fact. Termination is guaranteed: there are finitely many constants and no function symbols, so only finitely many ground atoms exist, and every productive cycle adds at least one.

## 9.3 Forward chaining trace

The main scenario reaches its fixpoint after {{stat cycles}} cycles:

Table: Forward chaining cycles
{{cycles}}

Cycles 1-7 derive new facts and cycle 8 finds none, so stratum 0 is complete. Cycle 9 runs R28 in stratum 1 and cycle 10 confirms the fixpoint. The full run has {{stat derived}} firings (Appendix C). The trace sheet below keeps only the firings that the conclusion allocate(sara, s_a1) depends on, in the order they happened.

Table: Forward trace for allocate(sara, s_a1)
{{fwd_table allocate(sara, s_a1)}}

The decision is reached in seven levels: permit_valid and permit_matches_role, then authorized, zone_access, suitable_space, eligible_for_space, can_allocate and finally allocate. Three other students also asked for s_a1. R23 gives the other students priority 1 in cycle 1 and R21 gives Sara priority 3 in cycle 2. In cycle 7, once can_allocate(sara, s_a1) is known, R25 fires three times: Sara beats Usman, Ali and Zara (Appendix C lists these firings). Usman loses as well even though he could never get the bay, because his request is still there. In stratum 1, R28 allocates s_a1 only to Sara, the one requester with no loses fact. The final decisions, with reasons from the explainer:

Table: Decisions for the morning rush
{{decisions}}

## 9.4 Backward chaining algorithm

Backward chaining is goal-driven: it starts from a hypothesis and works back to the facts that support it. The engine is SLD resolution, the method Prolog uses (krr/reasoning/backward.py).

```
procedure SOLVE(goals, θ, ancestors)
    if goals is empty then yield θ; return
    G := first(goals) θ
    if G is a comparison: if it evaluates true, SOLVE(rest, θ)       # built-in
    else if G = not A:    if SOLVE([A], θ) has no answer, SOLVE(rest, θ)
    else if G is a variant of one of its ancestors: fail             # loop check
    else
        for each stored fact F that unifies with G (mgu σ): SOLVE(rest, θσ)
        for each rule H :- B with variables renamed apart:
            if H unifies with G (mgu σ): SOLVE(B + rest, θσ, ancestors + G)
        # trying the next fact or rule after a failure is backtracking
```

Subgoals are proved depth first, left to right. Ground queries stop at the first proof and queries with variables collect every answer. Each step is logged as GOAL, RULE, FACT, BUILTIN, NOT, PROVED or FAIL, with its depth.

## 9.5 Backward chaining trace

Test case TC1: Ali asks for the vacant student bay s_a1 and nobody else wants it. Query `?- allocate(ali, s_a1).` Each row is one rule application in the proof; the dots show depth.

Table: Backward trace for allocate(ali, s_a1)
{{bwd_table tc01_valid_student allocate(ali, s_a1)}}

The leaves of the proof are 21 stored facts and 3 comparisons. The two "not" goals succeed because no competing request and no second reservation exist, so loses(ali, s_a1) and double_booked(ali) cannot be proved.

A failed proof shows backtracking. For `?- authorized_driver(usman).` R11 reduces the goal to authorized(usman, P) and R10 to permit_matches_role and permit_valid. R07 succeeds with P = p_usman, but permit_valid(p_usman) fails at the comparison 20260915 >= 20261002. The engine backtracks and tries R08 and R09 for permit_matches_role; both fail because p_usman is neither an employee permit nor a visitor pass. With no alternatives left, the goal fails, and the explainer reports "permit_valid(p_usman) fails at 20260915 >= 20261002". The full 41-step trace is in Appendix D.

Queries with variables return every answer: `?- can_allocate(ahmed, S).` gives S = s_e1, s_e2 and s_e3 (s_e2 is an EV bay that fits his electric car and s_e3 is reserved for him today).

## 9.6 Forward vs. backward chaining

Forward chaining computes everything at once, which suits the morning batch: {{stat derived}} firings decide all eight requests, though some of that work (such as Hina's priority) answers no question. Backward chaining touches only what the question needs and gives a proof tree directly, which suits one driver at the gate, but it can repeat work: proving allocate(sara, s_a1) takes {{stat sara_steps}} trace steps because the "not loses" subgoal re-proves can_allocate for every competitor. Tabling would remove that repetition. We use both, and their agreement is itself a test (section 11.4).

# Chapter 10: System implementation

This chapter describes the code: the technology, the file layout, how each part is implemented and how a user runs it. It covers the "sample execution output and code snippets" deliverable.

## 10.1 Technology stack

The system is written in Python 3.10 or newer (tested on 3.10, 3.12 and 3.14). The reasoning engines, CLI and tests use only the standard library, so anyone can run them without installing anything and every line of the reasoning is ours to explain in the viva. Streamlit provides the web interface, python-docx builds this report, Pillow draws its figures at print size (tools/figures.py), Mermaid draws the diagrams kept in the repository, and the knowledge base is also exported to SWI-Prolog and to OWL 2 (Turtle) for Protégé. The project website uses Three.js for its 3D scene and Pyodide to run the engine in the browser (section 10.9). GitHub Actions runs the tests on every push.

## 10.2 Project structure

{{tree}}

## 10.3 Knowledge base implementation

An atom is a Python tuple such as ("owns", "ali", "car_ali"). Tuples are hashable, so facts are kept in sets indexed by predicate name. A variable is a string that starts with an upper-case letter, and a substitution is a dictionary from variables to terms. Rules are written as Prolog text in krr/knowledge_base/rules.py, parsed into Rule objects and checked for safety when the module loads. Unification is the standard algorithm for function-free terms (Appendix E).

## 10.4 Frame implementation

Slot, Frame and FrameSystem are dataclasses in krr/frames/frames.py. FrameSystem.get() implements the lookup order of section 4.1 and returns the value together with its source (own value, default from a named frame, or if-needed). If-needed procedures are ordinary Python functions stored in the slot. FrameSystem.to_facts() turns instance frames into knowledge base facts using the predicate facet.

## 10.5 Forward chaining implementation

One cycle takes a snapshot of working memory, matches every rule body against it and keeps only new heads:

```
snapshot = {p: set(work.facts_for(p)) for p in work.predicates}
for rule in rules:
    for subst in match_body(rule.body, work, {}, snapshot):
        conflict_set += 1
        head = substitute(rule.head, subst)
        if head in work or head in new_this_cycle:
            continue                       # refraction: nothing new
        new_this_cycle[head] = Firing(step, cycle_no, stratum, rule, subst, premises, head)
```

The stratifier assigns R28 to stratum 1 because its body has "not", and raises an error if a rule set contains recursion through negation.

## 10.6 Backward chaining implementation

The solver is a Python generator, so backtracking is just asking it for the next answer:

```
for rule in self.kb.rules_for(goal[0]):
    renamed = rule.renamed(str(next(self._counter)))   # standardise apart
    s2 = unify(goal, renamed.head, subst)
    if s2 is None:
        continue
    for s3, children in self._solve_body(renamed.body, s2, depth + 1, ancestors + (goal,)):
        yield s3, ProofNode(format_atom(substitute(goal, s3)), rule.rid, children)
```

Renaming is why traces show variables such as P_5. A depth limit of 40 is a second guard after the loop check.

## 10.7 User interaction / CLI

```
python main.py demo          python main.py prove "can_allocate(ahmed, S)"    python main.py cases
python main.py forward       python main.py why "allocate(usman, s_a1)"       streamlit run app.py
```

The Streamlit interface has ten tabs: overview, knowledge base, frames and script, semantic network, FOL, DL, forward chaining (with a slider that replays inference cycle by cycle), backward chaining (free-text queries with trace, drawn proof tree and why-not), test cases, and a playground where the user changes the date, hour and requests and runs the reasoner again.

## 10.8 Sample execution

Output of `python main.py why "allocate(fatima, s_e1)" -s tc06_no_suitable_space`:

{{include generated/why_fatima.txt}}

The output of `python main.py cases` is summarised in section 11.2. Screenshots of the running web interface are in Appendix F.

## 10.9 Project website

The project also has a public website at https://smart-parking-krr.vercel.app. The page itself is static: tools/build_site.py runs the engines and writes every decision, proof, inference cycle and test result into a data file, so what the site shows is the code's own output. The car park is drawn in 3D with Three.js, and a flat 2D version is used when the browser has no WebGL or the visitor has asked for reduced motion.

The 3D view replays the morning rush. The eight cars arrive, the forward chainer runs its {{stat cycles}} cycles, and each car is checked at the gate. Allocated cars reverse into their bay, and refused cars turn away with the root cause found by the explainer. Further down the page the camera visits the knowledge core (the forward-chaining cycles), a proof tower for the backward-chaining answer that is selected, the semantic network and the twelve test cases.

Two features run the real engine in the browser. Pyodide, a build of CPython for WebAssembly, loads the krr package from a zip file next to the page, so no server is involved.

- Scenario clock. Any date and hour can be chosen. krr/site_export.py rebuilds the main scenario with new current_date and current_hour facts and runs forward chaining again. At 23:00, for example, every zone is closed and no request is allocated, and on 3 October 2026 Bilal's one-day pass fails R06.
- Add a driver. A form asks for name, role, vehicle, permit state, bay, arrival time and accessibility badge. The answers become the same kind of facts the frames give the built-in drivers, such as student(omar), owns(omar, veh_omar), permit_start(pm_omar, D) and requests(omar, s_a1, 905). The engine then decides every request again, and Ask why shows the new driver's proof or the first condition that failed (Appendix F).

The second feature lets an examiner describe a new case and see it answered with a proof built from our rules. tests/test_site_export.py checks both features with the same unittest suite as the rest of the system.

# Chapter 11: Testing and results

This chapter explains how the system was tested and what the results show. All numbers below are produced by running the code when this report is built.

## 11.1 Testing strategy

Testing works at four levels. Unit tests cover the parser, unification, rule safety, frames, the semantic network, the DL reasoner and the FOL model checker. Rule tests check single rules on small fact sets. Inference tests check that the forward closure is a model of every rule and that every firing uses only facts known before it. Scenario tests run twelve cases (the template's eight plus four) and compare each expected goal with both engines.

## 11.2 Test cases

Table: Test cases run through both engines
{{test_table}}

## 11.3 Results analysis

Every case passes with both engines. The cases exercise each requirement of section 1.4 at least once, and each denial is caught at the right rule: an expired permit at R06 (TC2), a missing pass at R09 (TC3), an occupied bay at R19/R20 (TC4), the wrong zone at R13 (TC5), a vehicle that does not fit at R14 (TC6), the missing badge at R16 (TC8), a closed zone at R12 (TC10) and someone else's reservation at R20 (TC11). TC7 checks both conflict rules, priority (R25) and arrival time (R26). TC9 checks the only use of negation. TC12 checks that bad data is caught, independently, by IC4 and by DL axiom D01.

## 11.4 Inference accuracy / consistency

- All 12 test cases and the main scenario give the expected result with both engines: {{stat goal_checks}} goal checks, each answered the same way by forward and backward chaining.
- For every derived predicate in all 13 scenarios, backward chaining with all variables free returns exactly the set of facts forward chaining derives. The engines are written independently, so this is the strongest check we have.
- All 12 FOL statements hold on the main model; F04 fails on the TC12 data with the counterexample x = ali, as it should.
- The DL ABox of the main scenario is consistent, and DL realization of AuthorizedDriver matches authorized_driver for all eight people.
- The generated Prolog program is parsed back by a unit test and contains exactly the same facts and rules. Loaded in SWI-Prolog 10, it proves exactly the conclusions the Python forward chainer derives in all 13 scenarios, including the IC4 violation in TC12, and it loads without warnings. `python main.py prolog` repeats this check, and GitHub Actions runs it on every push.
- The suite has {{stat unit_tests}} unit tests, all passing.

We did not measure speed or accuracy on real traffic, because there is no real traffic data; the claims above are about logical correctness on our scenarios.

# Chapter 12: Expressivity, tractability and design analysis

This chapter applies the course's expressivity and tractability trade-off to the parking domain and explains why the system uses several paradigms instead of one.

## 12.1 Propositional logic limitations

Propositional logic has no objects or variables. "A student with a valid student permit may enter a student zone" must be written once for every student, permit and zone: ali_valid ∧ ali_student → ali_zone_a, and so on. With 8 people, 7 permits and 3 zones, R13 alone becomes dozens of rules, and each new student needs new ones. It also cannot say "every bay is in some zone" (F01) or compare an expiry date with today. Inference is decidable, and propositional Horn clauses can even be decided in linear time, but the knowledge base would grow with every person and bay.

## 12.2 FOL expressivity

Quantified variables let one rule cover every individual, so the 28 rules work for any number of drivers and bays. FOL can also state F01 (existential), F02 (equality), F03 (disjunction) and F10 (negation inside a quantifier), none of which propositional logic can say in general form.

## 12.3 FOL computational limitations

Entailment in full FOL is only semi-decidable: a prover may run forever on a formula that does not follow. Even when it stops, resolution in full FOL has no useful time bound. A gate cannot wait for an answer that may never come. Our model checker avoids the problem because it evaluates the statements on one finite model, which always terminates; it does not prove that they follow from the rules in every model.

## 12.4 Description logic trade-offs

DL is a decidable fragment of FOL. Each DL axiom translates into FOL with at most two variables: ParkingSpace ⊑ ∃locatedIn.ParkingZone becomes ∀x (ParkingSpace(x) → ∃y (locatedIn(x, y) ∧ ParkingZone(y))). Satisfiability in ALC is PSPACE-complete, and in the EL fragment (only ⊓ and ∃), which covers most of our TBox, subsumption takes polynomial time (Baader, Brandt and Lutz, 2005). The price is that DL cannot join several variables in a chain. R25 compares the priorities of two requesters for the same bay, which needs three variables bound together, and the comparison PX > PY is not a DL constructor.

## 12.5 Horn clauses and tractable inference

A Horn clause has at most one positive literal, so disjunctive and existential conclusions (F01, F03) cannot be written. In return the system gets what the gate needs. Without function symbols (Datalog) the set of derivable facts is finite, so forward chaining always terminates; ours stops after {{stat cycles}} cycles. Forward chaining over ground Horn clauses runs in polynomial time in the number of facts. Every answer has a proof made of rule applications, which is what the explainer shows. And Horn clauses run directly in Prolog. Stratified negation as failure adds "unless" without losing termination, at the cost of non-monotonicity: a new higher-priority request can remove an allocation.

## 12.6 Why multi-paradigm KRR?

No single formalism does everything here. Frames handle defaults and overriding, which logic cannot do without non-monotonic extensions. The script captures the order of events. The semantic network makes the model readable and answers path questions. FOL states what must always be true, including statements that cannot be executed efficiently. DL keeps the terminology consistent and supports the open-world reading. Horn clauses execute the policy and explain it. One vocabulary, checked by a unit test, lets them work as one system.

# Chapter 13: Limitations and future work

This chapter states what the system cannot do and how it could be extended.

## 13.1 Current limitations

- Time is coarse: whole hours and whole-day reservations. A zone closing at 17:30 cannot be expressed.
- Request times are assumed unique. Two equal-priority requests at the same minute would both be allocated; IC1 would report it, but no rule resolves it.
- One request per driver is assumed; IC2 would report a driver allocated two bays.
- Each run is a snapshot. Allocating a bay does not change its status inside the same run, because classical logic cannot retract facts; the script updates the status afterwards.
- The DL reasoner is structural: complete for the EL part of the TBox but incomplete for ⊔ and ∀. Full ALCI reasoning needs a tableau reasoner such as HermiT, which can be run on the exported OWL file in Protégé.
- The backward chainer has no tabling, so shared subgoals are recomputed.

## 13.2 Future improvements

1. Represent time intervals (Allen's interval relations or the event calculus) for hourly reservations and exact closing times.
2. After a loss, suggest the best free alternative bay; the query can_allocate(X, S) already lists the candidates.
3. Add tabling to the backward chainer.
4. Add certainty factors for sensor-reported occupancy, which is not always reliable.
5. Connect to live occupancy sensors and the permit database, keeping the rule base unchanged.
6. Add a truth maintenance mode so one new request does not recompute the whole closure.

# Chapter 14: Conclusion

This chapter sums up the work and maps it to the CCP requirements.

## 14.1 Summary

We modelled campus parking access and allocation in five paradigms that share one vocabulary: frames, a script, a semantic network, FOL and a DL ontology. Decisions come from 28 Horn rules with one stratified negation, run by a forward chainer that writes complete trace sheets and a backward chainer that proves single goals and explains every denial.

## 14.2 Achievements

Every critical element of the CCP guide is covered, and the compliance checklist at the end of the report maps each requirement to its section.

## 14.3 Final evaluation

The system shows that one parking policy can be represented several ways and kept consistent, and that two independent engines reach the same decisions on every test. It explains every refusal down to the failing fact or comparison. What remains outside scope is real-time data, finer time, uncertainty and deployment at the gate.

# References

1. Brachman, R. J. and Levesque, H. J. (2004). Knowledge Representation and Reasoning. Morgan Kaufmann.
2. Russell, S. and Norvig, P. (2021). Artificial Intelligence: A Modern Approach, 4th edition. Pearson.
3. Baader, F., Calvanese, D., McGuinness, D. L., Nardi, D. and Patel-Schneider, P. F. (eds.) (2003). The Description Logic Handbook. Cambridge University Press.
4. Baader, F., Brandt, S. and Lutz, C. (2005). Pushing the EL envelope. Proceedings of IJCAI 2005, pp. 364-369.
5. Minsky, M. (1974). A Framework for Representing Knowledge. MIT AI Laboratory Memo 306.
6. Schank, R. C. and Abelson, R. P. (1977). Scripts, Plans, Goals and Understanding. Lawrence Erlbaum Associates.
7. Quillian, M. R. (1968). Semantic memory. In M. Minsky (ed.), Semantic Information Processing. MIT Press.
8. Kowalski, R. (1974). Predicate logic as programming language. Proceedings of IFIP Congress 74, pp. 569-574.
9. Clark, K. L. (1978). Negation as failure. In H. Gallaire and J. Minker (eds.), Logic and Data Bases. Plenum Press.
10. Apt, K. R., Blair, H. A. and Walker, A. (1988). Towards a theory of declarative knowledge. In J. Minker (ed.), Foundations of Deductive Databases and Logic Programming. Morgan Kaufmann.
11. W3C OWL Working Group (2012). OWL 2 Web Ontology Language Document Overview (Second Edition). https://www.w3.org/TR/owl2-overview/
12. SWI-Prolog Reference Manual. https://www.swi-prolog.org/pldoc/
13. Department of Computer Science and IT, NED University. CT-351 Knowledge Representation & Reasoning, Complex Computing Problem guide.

# Appendix A: Complete knowledge base

All {{stat facts}} facts of the main scenario, grouped as in docs/generated/facts.txt. The rules are in section 8.3 and Appendix B.

{{facts_compact}}

# Appendix B: Complete Horn clauses

The complete executable rule set, R01-R28 and IC1-IC7, is the Horn clause column of the rule table in section 8.3. That table is printed from krr/knowledge_base/rules.py, the same objects the engines run, so it cannot differ from the code. The generated SWI-Prolog program prolog/smart_parking.pl holds the same 28 clauses in the same order. R01-R27 are written there exactly as in the table; the parts that change in Prolog are shown below: R28 writes `not` as `\+`, each denial constraint becomes a `violation/1` clause, and two helper predicates check consistency and print the allocations.

{{prolog_tail}}

# Appendix C: Forward chaining traces

Every firing of the main scenario in order: step number, cycle, rule and derived fact. Premises and bindings for each step are in docs/generated/forward_trace_full.txt.

{{all_firings}}

# Appendix D: Backward chaining traces

The failed proof of `authorized_driver(usman)` with backtracking (section 9.5). The full trace of the successful TC1 proof is in docs/generated/backward_ali_tc01.txt.

{{include generated/backward_usman.txt 6}}

# Appendix E: Important source code

Unification of function-free terms (krr/core/terms.py):

```
def unify_terms(a, b, subst):
    a, b = resolve(a, subst), resolve(b, subst)
    if a == b:
        return subst
    if is_var(a):
        return {**subst, a: b}
    if is_var(b):
        return {**subst, b: a}
    return None              # two different constants never unify
```

The forward chaining cycle and backward rule resolution are in sections 10.5 and 10.6, and frame slot lookup is FrameSystem.get() in krr/frames/frames.py. The repository holds the rest of the code.

# Appendix F: Execution screenshots

Screenshots of the Streamlit interface running the main scenario, followed by two from the project website (section 10.9).

{{screens}}

# Appendix G: Team participation evidence

Each member owned one part of the system from design to code to report chapter, so each of us can answer viva questions on our part in depth. All four of us reviewed the full rule base together before it was frozen, and every rule was agreed by the whole group.

Table: Team contributions
{{contributions}}

In the viva each member presents and demonstrates their own part: Syed Mohmmad Huzaifa the problem, frames and script; Maaz ur Rehman the semantic network and DL reasoner; Owais Tariq the Horn rules and forward chaining; Shaikh Muhammad Zain backward chaining, the interface and the test cases. The presentation script in docs/viva gives each member one part.

# CT-351 CCP final compliance checklist

Table: CCP compliance checklist
{{compliance}}
