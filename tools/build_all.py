"""Regenerate every artefact from the code.

    python tools/build_all.py              traces, diagrams (PNG), Prolog, OWL, report
    python tools/build_all.py --no-render  skip Mermaid -> PNG (needs Node.js + npx)
    python tools/build_all.py --no-report  skip the Word report

Outputs
    docs/generated/*.txt|md      trace sheets and listings used by the report
    docs/diagrams/*.mmd          generated Mermaid sources (static ones are kept)
    docs/diagrams/png/*.png      rendered diagrams (for GitHub and the appendix)
    docs/figures/*.png           report figures drawn at print size (tools/figures.py)
    prolog/smart_parking.pl      SWI-Prolog version of the knowledge base
    ontology/smart_parking.ttl   OWL 2 ontology (Turtle) for Protégé
    docs/report/*.docx           the CCP report
    website/data.js              data for the project website (tools/build_site.py)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from krr.core.terms import format_atom  # noqa: E402
from krr.export.diagrams import GENERATED  # noqa: E402
from krr.export.owl import to_turtle  # noqa: E402
from krr.export.prolog import to_prolog  # noqa: E402
from krr.frames.ontology import build_frames  # noqa: E402
from krr.frames.scripts import PARKING_SESSION, run_parking_script  # noqa: E402
from krr.knowledge_base.facts import grouped  # noqa: E402
from krr.knowledge_base.rules import CONSTRAINTS, RULES  # noqa: E402
from krr.knowledge_base.scenarios import TEST_CASES  # noqa: E402
from krr.logic.description_logic import TBOX, build_abox  # noqa: E402
from krr.reasoning.forward import format_support, format_trace  # noqa: E402
from krr.semantic_net.network import build_class_network  # noqa: E402
from krr.system import run  # noqa: E402

GEN = ROOT / "docs" / "generated"
DIAGRAMS = ROOT / "docs" / "diagrams"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}")


def generate_listings() -> None:
    main = run("morning_rush")

    lines = [f"Knowledge base facts for scenario morning_rush ({len(main.kb.facts)} facts)", ""]
    for title, rows in grouped(main.kb.facts):
        lines.append(f"[{title}]  {len(rows)} facts")
        lines += ["    " + r for r in rows]
        lines.append("")
    write(GEN / "facts.txt", "\n".join(lines))

    lines = []
    group = None
    for r in RULES:
        if r.group != group:
            group = r.group
            lines += ["", group]
        lines += [f"{r.rid}  {r.text}", f"     English: {r.natural}",
                  f"     FOL:     {r.to_fol()}"]
        if r.explanation:
            lines.append(f"     Note:    {r.explanation}")
    lines += ["", "Integrity constraints (denial clauses)"]
    for c in CONSTRAINTS:
        lines += [f"{c.cid}  {c.text}", f"     English: {c.natural}", f"     FOL:     {c.to_fol()}"]
    write(GEN / "rules.txt", "\n".join(lines).strip() + "\n")

    write(GEN / "forward_trace_full.txt", format_trace(main.forward))
    write(GEN / "forward_trace_sara.txt", format_support(main.forward, "allocate(sara, s_a1)"))
    conflict = [f for f in main.forward.firings if f.rule.rid in {"R21", "R22", "R23", "R24",
                                                                  "R25", "R26", "R28"}]
    write(GEN / "forward_trace_conflict.txt",
          "Priority, conflict and decision firings (morning_rush)\n" + "=" * 60 + "\n"
          + "\n".join(f.text() for f in conflict))
    cyc = ["Cycle  Stratum  Conflict set  New facts  Rules fired"]
    for c in main.forward.cycles:
        cyc.append(f"{c.number:>5}  {c.stratum:>7}  {c.conflict_set:>12}  {c.fired:>9}  "
                   f"{', '.join(c.rules_fired) or '(none: fixpoint)'}")
    write(GEN / "forward_cycles.txt", "\n".join(cyc))

    decisions = ["Driver   Space  Decision   Reason"]
    for o in main.outcomes():
        decisions.append(f"{o.person:<8} {o.space:<6} {'ALLOCATED' if o.allocated else 'DENIED':<10} "
                         f"{'; '.join(o.reasons[:1])}")
    write(GEN / "decisions.txt", "\n".join(decisions))

    for name, goal, scenario in (("backward_ali_tc01", "allocate(ali, s_a1)", "tc01_valid_student"),
                                 ("backward_sara", "allocate(sara, s_a1)", "morning_rush"),
                                 ("backward_usman", "authorized_driver(usman)", "morning_rush"),
                                 ("backward_ahmed_open", "can_allocate(ahmed, S)", "morning_rush"),
                                 ("backward_ali_conflict", "allocate(ali, s_a1)", "morning_rush")):
        r = run(scenario)
        res = r.prove(goal)
        text = [f"?- {goal}.", "", res.format_trace(), "", res.summary()]
        for i, proof in enumerate(res.proofs, 1):
            text += ["", f"Proof tree {i}:"] + proof.render()
        if not res.success:
            text += ["", r.explain(goal)]
        write(GEN / f"{name}.txt", "\n".join(text))

    r6 = run("tc06_no_suitable_space")
    write(GEN / "why_fatima.txt", r6.explain("allocate(fatima, s_e1)"))
    summary = []
    for sc in TEST_CASES:
        rows = run(sc).check_expectations()
        ok = all(e == f == b for _, e, f, b in rows)
        summary.append(f"{'ok  ' if ok else 'FAIL'} {sc.title:<58} {len(rows)} checks")
    write(GEN / "cases_summary.txt", "\n".join(summary))

    fs = build_frames()
    frames_text = [fs.describe(f.name) for f in fs.classes()]
    frames_text += [fs.describe(n) for n in ("ali", "sara", "s_a3", "zone_a", "p_usman", "r1")]
    write(GEN / "frames.txt", "\n\n".join(frames_text))
    script_text = [PARKING_SESSION.describe(), ""]
    for driver, space in (("sara", "s_a1"), ("usman", "s_a1"), ("fatima", "s_e1")):
        script_text += [run_parking_script(main.kb, driver, space).text(), ""]
    write(GEN / "script.txt", "\n".join(script_text))

    net = build_class_network()
    write(GEN / "semantic_network_edges.txt",
          "\n".join(f"{e.source} --{e.label}--> {e.target}" for e in net.edges))

    fol = []
    for st, ok, ce in main.fol_report():
        fol += [f"{st.sid}  {st.text}", f"     {st.english}",
                f"     Horn: {st.horn}", f"     Model check: {'holds' if ok else 'fails ' + str(ce)}"]
    write(GEN / "fol_statements.txt", "\n".join(fol))

    reasoner, abox, realized, clashes = main.dl_report()
    dl = ["TBox"] + [f"  {ax.aid}  {ax}" for ax in TBOX]
    dl += ["", "Inferred subsumptions"]
    dl += [f"  {a} ⊑ {b}" for a, b, inf in reasoner.classify() if inf]
    dl += ["", "Realization"]
    for person in ("ali", "sara", "usman", "zara", "ahmed", "fatima", "bilal", "hina"):
        dl.append(f"  {person:<7} {', '.join(sorted(realized[person]))}")
    dl += ["", "Consistency: " + ("consistent" if not clashes else "; ".join(map(str, clashes)))]
    tc12 = run("tc12_inconsistent_abox")
    dl += ["TC12 consistency: " + "; ".join(map(str, tc12.dl_report()[3]))]
    write(GEN / "dl_reasoning.txt", "\n".join(dl))

    cases = []
    for sc in TEST_CASES:
        r = run(sc)
        cases += [f"## {sc.title}", "", sc.description, "",
                  "Goal | Expected | Forward | Backward", "--- | --- | --- | ---"]
        for goal, e, f, b in r.check_expectations():
            cases.append(f"`{goal}` | {e} | {f} | {b}")
        cases.append("")
        if sc.focus_goal:
            res = r.prove(sc.focus_goal)
            cases.append(f"Backward chaining on `{sc.focus_goal}`: "
                         f"{'proved' if res.success else 'not provable'}.")
            cases.append("")
            cases.append("```")
            cases += res.proofs[0].render() if res.success else r.explain(sc.focus_goal).splitlines()
            cases.append("```")
        for c, _ in r.forward.violations:
            cases.append(f"Constraint {c.cid} violated: {c.natural}")
        for clash in r.dl_report()[3]:
            cases.append(f"DL reasoner: {clash}.")
        cases.append("")
    write(GEN / "test_cases.md", "\n".join(cases))


def generate_diagrams(render: bool) -> None:
    for name, func in GENERATED.items():
        write(DIAGRAMS / f"{name}.mmd", func() + "\n")
    if not render:
        return
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        print("  npx not found: skipping PNG rendering")
        return
    out = DIAGRAMS / "png"
    out.mkdir(exist_ok=True)
    config = DIAGRAMS / "mermaid-config.json"
    for src in sorted(DIAGRAMS.glob("*.mmd")):
        target = out / f"{src.stem}.png"
        cmd = [npx, "-y", "@mermaid-js/mermaid-cli", "-i", str(src), "-o", str(target),
               "-b", "white", "-s", "2", "-c", str(config)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        status = "ok" if result.returncode == 0 else f"FAILED: {result.stderr[-300:]}"
        print(f"  render {src.name}: {status}")


def generate_exports() -> None:
    main = run("morning_rush")
    write(ROOT / "prolog" / "smart_parking.pl", to_prolog(main.kb, main.scenario))
    write(ROOT / "ontology" / "smart_parking.ttl", to_turtle(build_abox()))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--no-report", action="store_true")
    args = parser.parse_args()
    print("Listings and traces")
    generate_listings()
    print("Diagrams")
    generate_diagrams(not args.no_render)
    print("Report figures")
    from figures import build_figures  # noqa: E402
    for path in build_figures():
        print(f"  {path.relative_to(ROOT)}")
    print("Prolog and OWL")
    generate_exports()
    if not args.no_report:
        print("Report")
        from build_report import build  # noqa: E402
        build()
        try:
            from finalize_report import finalize  # noqa: E402
            finalize(pdf=True)
        except ImportError:
            print("  pywin32 not installed: open the report in Word and update fields")
        except Exception as exc:  # Word missing or automation failed
            print(f"  could not update fields with Word ({exc}); update them in Word")
    print("Website data")
    from build_site import main as build_site  # noqa: E402
    build_site()


if __name__ == "__main__":
    main()
