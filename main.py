"""Command-line interface for the Smart Parking reasoning system.

    python main.py                         interactive menu
    python main.py demo                    full walkthrough of the main scenario
    python main.py forward [-s SCENARIO]   forward chaining trace
    python main.py prove GOAL [-s ...]     backward chaining trace and proof tree
    python main.py why GOAL [-s ...]       why a goal cannot be proved
    python main.py cases                   run every test case with both engines
    python main.py prolog                  check the generated Prolog in SWI-Prolog
    python main.py kb | frames | network | fol | dl | script DRIVER SPACE | scenarios

Only the Python standard library is needed.
"""

from __future__ import annotations

import argparse
import sys

from krr.core.terms import ParseError, ReasoningError
from krr.frames.ontology import build_frames
from krr.frames.scripts import PARKING_SESSION, run_parking_script
from krr.knowledge_base.facts import grouped
from krr.knowledge_base.rules import CONSTRAINTS, RULES
from krr.knowledge_base.scenarios import SCENARIOS, TEST_CASES
from krr.logic.description_logic import TBOX
from krr.reasoning.forward import format_trace
from krr.semantic_net.network import build_class_network, build_instance_network
from krr.system import run

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")      # FOL/DL symbols on Windows consoles


def heading(text: str) -> None:
    print("\n" + text)
    print("=" * len(text))


# ----- commands ----------------------------------------------------------------

def cmd_kb(args) -> None:
    r = run(args.scenario)
    heading(f"Facts ({len(r.kb.facts)}) for scenario {r.scenario.key}")
    for title, rows in grouped(r.kb.facts):
        print(f"\n[{title}]")
        for row in rows:
            print("  " + row)
    heading(f"Rules ({len(RULES)})")
    group = None
    for rule in RULES:
        if rule.group != group:
            group = rule.group
            print(f"\n{group}")
        print(f"  {rule.rid}  {rule.text}")
        print(f"        {rule.natural}")
    heading("Integrity constraints")
    for c in CONSTRAINTS:
        print(f"  {c.cid}  {c.text}   {c.natural}")


def cmd_frames(args) -> None:
    fs = build_frames()
    names = [args.name] if args.name else [f.name for f in fs.classes()]
    for name in names:
        if name not in fs.frames:
            raise SystemExit(f"no frame called {name}")
        print(fs.describe(name) + "\n")
    errors = fs.validate()
    print("Facet check: " + ("all instance values satisfy their facets." if not errors
                             else "; ".join(errors)))
    if not args.name:
        print("\n" + PARKING_SESSION.describe())


def cmd_network(args) -> None:
    net = build_instance_network([args.individual]) if args.individual else build_class_network()
    heading("Semantic network edges")
    for e in net.edges:
        print(f"  {e.source:<16} --{e.label}--> {e.target}")
    if args.individual:
        heading(f"What {args.individual} inherits along instance-of / is-a")
        for label, target, origin in net.inherited_relations(args.individual):
            print(f"  {label} {target}   (from {origin})")


def cmd_forward(args) -> None:
    r = run(args.scenario)
    print(f"Scenario: {r.scenario.title}\n{r.scenario.description}\n")
    print(format_trace(r.forward, show_initial=not args.brief))
    heading("Decisions")
    for o in r.outcomes():
        verdict = "ALLOCATED" if o.allocated else "DENIED"
        print(f"  {o.person:<7} -> {o.space:<5} {verdict}")
        for reason in o.reasons[:2]:
            print(f"        because {reason}")


def cmd_prove(args) -> None:
    r = run(args.scenario)
    result = r.prove(args.goal)
    heading(f"Backward chaining: ?- {args.goal}")
    print(result.format_trace(max_lines=None if args.full else 120))
    print("\n" + result.summary())
    for i, proof in enumerate(result.proofs[:3], 1):
        heading(f"Proof tree {i}")
        print("\n".join(proof.render()))
    if not result.success:
        heading("Why not?")
        print(r.explain(args.goal))


def cmd_why(args) -> None:
    print(run(args.scenario).explain(args.goal))


def cmd_cases(args) -> None:
    failures = 0
    for sc in TEST_CASES:
        r = run(sc)
        heading(sc.title)
        print(sc.description)
        for goal, expected, fc, bc in r.check_expectations():
            ok = expected == fc == bc
            failures += not ok
            print(f"  {'ok  ' if ok else 'FAIL'} {goal:<34} expected={str(expected):<5} "
                  f"forward={str(fc):<5} backward={bc}")
        if r.forward.violations:
            for c, _ in r.forward.violations:
                print(f"  constraint {c.cid} violated: {c.natural}")
        _, _, _, clashes = r.dl_report()
        for clash in clashes:
            print(f"  DL clash: {clash}")
    print(f"\n{len(TEST_CASES)} test cases, {failures} mismatches.")
    if failures:
        raise SystemExit(1)


def cmd_fol(args) -> None:
    heading("FOL reading of every Horn rule")
    for rule in RULES:
        print(f"  {rule.rid}  {rule.to_fol()}")
    heading("Further FOL statements, checked on the forward-chaining model")
    for st, ok, ce in run(args.scenario).fol_report():
        print(f"  {st.sid}  {st.text}")
        print(f"        {st.english}  [{'holds' if ok else 'FAILS ' + str(ce)}]")
        print(f"        Horn: {st.horn}")


def cmd_dl(args) -> None:
    r = run(args.scenario)
    reasoner, abox, realized, clashes = r.dl_report()
    heading("TBox")
    for ax in TBOX:
        print(f"  {ax.aid}  {str(ax):<60} {ax.note}")
    heading("Classification (inferred subsumptions marked *)")
    for a, b, inferred in reasoner.classify():
        print(f"  {'*' if inferred else ' '} {a} ⊑ {b}")
    heading("Realization of people")
    for person in ("ali", "sara", "usman", "zara", "ahmed", "fatima", "bilal", "hina"):
        print(f"  {person:<7} {', '.join(sorted(realized.get(person, [])))}")
    heading("Consistency")
    print("  consistent" if not clashes else "\n".join(f"  {c}" for c in clashes))


def cmd_script(args) -> None:
    r = run(args.scenario)
    print(run_parking_script(r.kb, args.driver, args.space).text())


def cmd_scenarios(args) -> None:
    for key, sc in SCENARIOS.items():
        print(f"  {key:<30} {sc.title}")


def cmd_demo(args) -> None:
    r = run(args.scenario)
    heading("1. Scenario")
    print(r.scenario.description)
    heading("2. Forward chaining (data-driven)")
    print(format_trace(r.forward, show_initial=False))
    heading("3. Decisions")
    for o in r.outcomes():
        print(f"  {o.person:<7} -> {o.space:<5} {'ALLOCATED' if o.allocated else 'DENIED'}"
              + (f"   ({o.reasons[0]})" if o.reasons else ""))
    goal = r.scenario.focus_goal or "allocate(sara, s_a1)"
    heading(f"4. Backward chaining (goal-driven): ?- {goal}")
    result = r.prove(goal)
    print(result.format_trace(max_lines=80))
    print("\n" + result.summary())
    if result.proofs:
        print("\n".join(result.proofs[0].render()))
    heading("5. Why was Ali denied?")
    print(r.explain("allocate(ali, s_a1)"))
    heading("6. Script run for Usman")
    print(run_parking_script(r.kb, "usman", "s_a1").text())


# ----- interactive menu --------------------------------------------------------

MENU = """
Smart Parking KRR system
  1  Main demo (forward + backward + explanations)
  2  Forward chaining trace
  3  Prove a goal (backward chaining)
  4  Why can a goal not be proved?
  5  Run all test cases
  6  Frames and the parking script
  7  Semantic network
  8  FOL statements
  9  Description logic
  0  Quit
"""


def interactive() -> None:
    scenario = "morning_rush"
    ns = argparse.Namespace
    while True:
        print(MENU)
        choice = input("Choose: ").strip()
        try:
            if choice == "0":
                return
            if choice == "1":
                cmd_demo(ns(scenario=scenario))
            elif choice == "2":
                cmd_forward(ns(scenario=scenario, brief=True))
            elif choice in ("3", "4"):
                goal = input("Goal, e.g. can_allocate(ali, S): ").strip()
                if choice == "3":
                    cmd_prove(ns(scenario=scenario, goal=goal, full=False))
                else:
                    cmd_why(ns(scenario=scenario, goal=goal))
            elif choice == "5":
                cmd_cases(ns())
            elif choice == "6":
                cmd_frames(ns(name=None))
            elif choice == "7":
                cmd_network(ns(individual=input("Individual (blank for classes): ").strip() or None))
            elif choice == "8":
                cmd_fol(ns(scenario=scenario))
            elif choice == "9":
                cmd_dl(ns(scenario=scenario))
        except (ParseError, ReasoningError, KeyError) as exc:
            print(f"Error: {exc}")
        except SystemExit:
            pass
        input("\nPress Enter to continue...")


def cmd_prolog(args) -> None:
    """Load the generated Prolog program for every scenario in SWI-Prolog and
    check that it proves exactly what the Python forward chainer derives."""
    from krr.export.prolog import conclusions_in_python, conclusions_in_swipl, find_swipl
    swipl = find_swipl()
    if not swipl:
        raise SystemExit("SWI-Prolog (swipl) was not found. Install it from https://www.swi-prolog.org.")
    heading("Python forward chaining vs SWI-Prolog")
    mismatches = 0
    for sc in [SCENARIOS["morning_rush"]] + TEST_CASES:
        kb = sc.build_kb()
        py = conclusions_in_python(kb)
        pl, warnings = conclusions_in_swipl(kb, sc, swipl)
        same = py == pl and not warnings
        mismatches += not same
        print(f"  {'ok  ' if same else 'DIFF'} {sc.key:<32} {len(py):>4} conclusions in Python, {len(pl):>4} in Prolog")
        for fact in sorted(py - pl):
            print(f"       only Python: {fact}")
        for fact in sorted(pl - py):
            print(f"       only Prolog: {fact}")
        if warnings:
            print(f"       SWI-Prolog warnings: {warnings}")
    print(f"\n{len(TEST_CASES) + 1} scenarios, {mismatches} differences.")
    if mismatches:
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Smart Parking Access & Space Allocation "
                                            "Reasoning System (CT-351 KRR)")
    sub = p.add_subparsers(dest="command")

    def add(name, func, help_text, scenario=True):
        sp = sub.add_parser(name, help=help_text)
        if scenario:
            sp.add_argument("-s", "--scenario", default="morning_rush",
                            help="scenario key (see 'python main.py scenarios')")
        sp.set_defaults(func=func)
        return sp

    add("demo", cmd_demo, "full walkthrough")
    add("kb", cmd_kb, "list facts, rules and constraints")
    add("frames", cmd_frames, "show frames and the script", False).add_argument("name", nargs="?")
    add("network", cmd_network, "semantic network", False).add_argument("individual", nargs="?")
    add("forward", cmd_forward, "forward chaining trace").add_argument("--brief", action="store_true")
    sp = add("prove", cmd_prove, "backward chaining for a goal")
    sp.add_argument("goal")
    sp.add_argument("--full", action="store_true", help="do not shorten the trace")
    add("why", cmd_why, "explain why a goal fails").add_argument("goal")
    add("cases", cmd_cases, "run all test cases", False)
    add("prolog", cmd_prolog, "check the generated Prolog program in SWI-Prolog", False)
    add("fol", cmd_fol, "first-order logic")
    add("dl", cmd_dl, "description logic")
    sp = add("script", cmd_script, "run the ParkingSession script")
    sp.add_argument("driver")
    sp.add_argument("space")
    add("scenarios", cmd_scenarios, "list scenarios", False)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if not args.command:
        interactive()
        return
    try:
        args.func(args)
    except (ParseError, ReasoningError, KeyError) as exc:
        raise SystemExit(f"Error: {exc}")


if __name__ == "__main__":
    main()
