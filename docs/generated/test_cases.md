## TC1  Valid student, valid permit, free student bay

Ali (student, permit valid until 30 Jun 2027) asks for the vacant bay s_a1 in the student zone.

Goal | Expected | Forward | Backward
--- | --- | --- | ---
`authorized_driver(ali)` | True | True | True
`eligible_for_space(ali, s_a1)` | True | True | True
`can_allocate(ali, s_a1)` | True | True | True
`allocate(ali, s_a1)` | True | True | True

Backward chaining on `allocate(ali, s_a1)`: proved.

```
allocate(ali, s_a1)   [R28]
├── requests(ali, s_a1, 900)   [fact]
├── can_allocate(ali, s_a1)   [R19]
│   ├── eligible_for_space(ali, s_a1)   [R15]
│   │   ├── suitable_space(ali, s_a1)   [R14]
│   │   │   ├── zone_access(ali, zone_a)   [R13]
│   │   │   │   ├── authorized(ali, p_ali)   [R10]
│   │   │   │   │   ├── permit_matches_role(ali, p_ali)   [R07]
│   │   │   │   │   │   ├── has_permit(ali, p_ali)   [fact]
│   │   │   │   │   │   ├── permit_class(p_ali, student_permit)   [fact]
│   │   │   │   │   │   └── student(ali)   [fact]
│   │   │   │   │   └── permit_valid(p_ali)   [R06]
│   │   │   │   │       ├── permit_status(p_ali, active)   [fact]
│   │   │   │   │       ├── permit_start(p_ali, 20260701)   [fact]
│   │   │   │   │       ├── permit_expiry(p_ali, 20270630)   [fact]
│   │   │   │   │       ├── current_date(20261002)   [fact]
│   │   │   │   │       ├── 20260701 =< 20261002   [built-in]
│   │   │   │   │       └── 20270630 >= 20261002   [built-in]
│   │   │   │   ├── permit_class(p_ali, student_permit)   [fact]
│   │   │   │   ├── grants(student_permit, student_zone)   [fact]
│   │   │   │   ├── zone_type(zone_a, student_zone)   [fact]
│   │   │   │   └── zone_open(zone_a)   [R12]
│   │   │   │       ├── zone_opens(zone_a, 7)   [fact]
│   │   │   │       ├── zone_closes(zone_a, 22)   [fact]
│   │   │   │       ├── current_hour(10)   [fact]
│   │   │   │       ├── 10 >= 7   [built-in]
│   │   │   │       └── 10 < 22   [built-in]
│   │   │   ├── located_in(s_a1, zone_a)   [fact]
│   │   │   ├── owns(ali, car_ali)   [fact]
│   │   │   ├── vehicle_type(car_ali, car)   [fact]
│   │   │   ├── space_type(s_a1, standard)   [fact]
│   │   │   └── fits(car, standard)   [fact]
│   │   ├── space_type(s_a1, standard)   [fact]
│   │   └── open_type(standard)   [fact]
│   └── space_free(s_a1)   [R17]
│       └── space_status(s_a1, vacant)   [fact]
├── not loses(ali, s_a1)   [negation as failure]
└── not double_booked(ali)   [negation as failure]
```

## TC2  Expired permit

Usman's student permit expired on 15 Sep 2026. Today is 2 Oct 2026.

Goal | Expected | Forward | Backward
--- | --- | --- | ---
`permit_valid(p_usman)` | False | False | False
`authorized_driver(usman)` | False | False | False
`allocate(usman, s_a1)` | False | False | False

Backward chaining on `authorized_driver(usman)`: not provable.

```
authorized_driver(usman) cannot be proved. Reasons, rule by rule:
  R11 blocked at authorized(usman, P)
    R10 blocked at permit_valid(p_usman)
      R06 blocked at 20260915 >= 20261002  (false)
```

## TC3  Visitor without authorization

Hina is a visitor with no visitor pass. Bilal, also a visitor, has a pass for today.

Goal | Expected | Forward | Backward
--- | --- | --- | ---
`authorized_driver(hina)` | False | False | False
`allocate(hina, s_v1)` | False | False | False
`authorized_driver(bilal)` | True | True | True

Backward chaining on `authorized_driver(hina)`: not provable.

```
authorized_driver(hina) cannot be proved. Reasons, rule by rule:
  R11 blocked at authorized(hina, P)
    R10 blocked at permit_matches_role(hina, P)
      R07 blocked at has_permit(hina, P)  (no such fact is stored)
      R08 blocked at has_permit(hina, P)  (no such fact is stored)
      R09 blocked at has_permit(hina, P)  (no such fact is stored)
```

## TC4  Space already occupied

Ali asks for s_a2, a student bay that is occupied.

Goal | Expected | Forward | Backward
--- | --- | --- | ---
`eligible_for_space(ali, s_a2)` | True | True | True
`space_free(s_a2)` | False | False | False
`can_allocate(ali, s_a2)` | False | False | False
`allocate(ali, s_a2)` | False | False | False

Backward chaining on `can_allocate(ali, s_a2)`: not provable.

```
can_allocate(ali, s_a2) cannot be proved. Reasons, rule by rule:
  R19 blocked at space_free(s_a2)
    R17 blocked at space_status(s_a2, vacant)  (no such fact is stored)
  R20 blocked at space_status(s_a2, reserved)  (no such fact is stored)
```

## TC5  Student requests an employee-only space

Ali asks for s_e1 in the employee zone.

Goal | Expected | Forward | Backward
--- | --- | --- | ---
`authorized_driver(ali)` | True | True | True
`zone_access(ali, zone_e)` | False | False | False
`allocate(ali, s_e1)` | False | False | False

Backward chaining on `can_allocate(ali, s_e1)`: not provable.

```
can_allocate(ali, s_e1) cannot be proved. Reasons, rule by rule:
  R19 blocked at eligible_for_space(ali, s_e1)
    R15 blocked at suitable_space(ali, s_e1)
      R14 blocked at located_in(s_e1, zone_a)  (no such fact is stored)
    R16 blocked at suitable_space(ali, s_e1)  (explained above)
  R20 blocked at eligible_for_space(ali, s_e1)  (explained above)
```

## TC6  Eligible driver, but no suitable space

Fatima (staff) is authorized for the employee zone, but she rides a motorbike and the employee zone has no motorbike bay.

Goal | Expected | Forward | Backward
--- | --- | --- | ---
`authorized_driver(fatima)` | True | True | True
`zone_access(fatima, zone_e)` | True | True | True
`suitable_space(fatima, s_e1)` | False | False | False
`allocate(fatima, s_e1)` | False | False | False

Backward chaining on `can_allocate(fatima, S)`: not provable.

```
can_allocate(fatima, S) cannot be proved. Reasons, rule by rule:
  R19 blocked at eligible_for_space(fatima, S)
    R15 blocked at suitable_space(fatima, S)
      R14 blocked at fits(motorbike, standard)  (no such fact is stored)
    R16 blocked at suitable_space(fatima, S)  (explained above)
  R20 blocked at eligible_for_space(fatima, S)  (explained above)
```

## TC7  Three drivers request the same space

Zara (08:50), Ali (09:05) and Sara (09:10, badge holder) all ask for s_a1. Sara has priority 3 and wins. Between Zara and Ali (both priority 1) the earlier request wins, so Ali also loses to Zara.

Goal | Expected | Forward | Backward
--- | --- | --- | ---
`allocate(sara, s_a1)` | True | True | True
`loses(zara, s_a1)` | True | True | True
`loses(ali, s_a1)` | True | True | True
`allocate(ali, s_a1)` | False | False | False
`allocate(zara, s_a1)` | False | False | False

Backward chaining on `allocate(ali, s_a1)`: not provable.

```
allocate(ali, s_a1) cannot be proved. Reasons, rule by rule:
  R28 blocked at not loses(ali, s_a1)  (loses(ali, s_a1) is provable by R25; competing request: requests(sara, s_a1, 910))
```

## TC8  Accessible space requested by an ineligible driver

Ali has no accessibility badge and asks for the accessible bay s_a3. Sara, who holds a badge, is eligible for the same bay.

Goal | Expected | Forward | Backward
--- | --- | --- | ---
`suitable_space(ali, s_a3)` | True | True | True
`eligible_for_space(ali, s_a3)` | False | False | False
`allocate(ali, s_a3)` | False | False | False
`eligible_for_space(sara, s_a3)` | True | True | True

Backward chaining on `eligible_for_space(ali, s_a3)`: not provable.

```
eligible_for_space(ali, s_a3) cannot be proved. Reasons, rule by rule:
  R15 blocked at open_type(accessible)  (no such fact is stored)
  R16 blocked at accessibility_badge(ali, yes)  (no such fact is stored)
```

## TC9  Conflicting reservations

Dr. Ahmed already holds reservation r2 for s_e3. A second reservation r3 for s_e1 on the same day is added, then he asks for s_e3.

Goal | Expected | Forward | Backward
--- | --- | --- | ---
`double_booked(ahmed)` | True | True | True
`can_allocate(ahmed, s_e3)` | True | True | True
`allocate(ahmed, s_e3)` | False | False | False

Backward chaining on `allocate(ahmed, s_e3)`: not provable.

```
allocate(ahmed, s_e3) cannot be proved. Reasons, rule by rule:
  R28 blocked at not double_booked(ahmed)  (double_booked(ahmed) is provable by R27)
```

## TC10  Visitor zone closed at 19:00

Bilal has a valid visitor pass but arrives at 19:00. The visitor zone is open 08:00-17:00.

Goal | Expected | Forward | Backward
--- | --- | --- | ---
`authorized_driver(bilal)` | True | True | True
`zone_open(zone_v)` | False | False | False
`allocate(bilal, s_v1)` | False | False | False

Backward chaining on `zone_access(bilal, zone_v)`: not provable.

```
zone_access(bilal, zone_v) cannot be proved. Reasons, rule by rule:
  R13 blocked at zone_open(zone_v)
    R12 blocked at 19 < 17  (false)
```

## TC11  Reserved space requested by someone else

s_a5 is reserved for Zara today. Ali asks for it.

Goal | Expected | Forward | Backward
--- | --- | --- | ---
`eligible_for_space(ali, s_a5)` | True | True | True
`can_allocate(ali, s_a5)` | False | False | False
`can_allocate(zara, s_a5)` | True | True | True

Backward chaining on `can_allocate(ali, s_a5)`: not provable.

```
can_allocate(ali, s_a5) cannot be proved. Reasons, rule by rule:
  R19 blocked at space_free(s_a5)
    R17 blocked at space_status(s_a5, vacant)  (no such fact is stored)
  R20 blocked at holds_reservation(ali, s_a5)
    R18 blocked at reserved_by(R, ali)  (no such fact is stored)
```

## TC12  Inconsistent data: a student recorded as faculty

A data-entry error also records Ali as faculty. The Horn constraint IC4 and the DL disjointness axiom Student ⊓ Employee ⊑ ⊥ must both report it.

Goal | Expected | Forward | Backward
--- | --- | --- | ---
`employee(ali)` | True | True | True
`student(ali)` | True | True | True

Backward chaining on `employee(ali)`: proved.

```
employee(ali)   [R04]
└── faculty(ali)   [fact]
```
Constraint IC4 violated: Nobody is both a student and an employee (Student ⊓ Employee ⊑ ⊥).
DL reasoner: ali is both Employee and Student, which D01 declares disjoint.
