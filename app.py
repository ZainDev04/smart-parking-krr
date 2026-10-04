"""Streamlit interface for the Smart Parking KRR system.

Run with:  streamlit run app.py

The UI only displays what the krr package computes. Every number, trace and
proof on screen comes from the same engines the CLI and the tests use.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from krr.core.terms import ParseError, ReasoningError, parse_query
from krr.frames.ontology import TODAY, build_frames
from krr.frames.scripts import PARKING_SESSION, run_parking_script
from krr.knowledge_base.facts import grouped
from krr.knowledge_base.rules import CONSTRAINTS, RULES
from krr.knowledge_base.scenarios import SCENARIOS, TEST_CASES, Expectation, Scenario
from krr.logic.description_logic import TBOX, explain_owa
from krr.reasoning.backward import BackwardChainer, ProofNode
from krr.reasoning.forward import format_trace
from krr.semantic_net.network import build_class_network, build_instance_network
from krr.system import run

st.set_page_config(page_title="Smart Parking KRR", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 3.2rem;}
div[data-testid="stMetricValue"] {font-size: 1.6rem;}
.verdict-ok {color:#15803d; font-weight:600;}
.verdict-no {color:#b91c1c; font-weight:600;}
code {white-space: pre-wrap;}
</style>""", unsafe_allow_html=True)

PEOPLE = ["ali", "sara", "usman", "zara", "ahmed", "fatima", "bilal", "hina"]
SPACES = ["s_a1", "s_a2", "s_a3", "s_a4", "s_a5", "s_e1", "s_e2", "s_e3", "s_v1"]


@st.cache_resource(show_spinner=False)
def cached_run(key: str):
    return run(key)


def run_custom(sc: Scenario):
    return run(sc)


# ----- sidebar --------------------------------------------------------------------

st.sidebar.title("Smart Parking KRR")
st.sidebar.caption("CT-351 Knowledge Representation & Reasoning, NED University")
keys = list(SCENARIOS)
key = st.sidebar.selectbox("Scenario", keys, format_func=lambda k: SCENARIOS[k].title)
R = cached_run(key)
st.sidebar.write(R.scenario.description)
st.sidebar.markdown(f"Date `{R.scenario.date}` · hour `{R.scenario.hour}:00`")
st.sidebar.divider()
st.sidebar.markdown(
    "Team\n\n"
    "- Syed Mohmmad Huzaifa (AI-23022)\n"
    "- Maaz ur Rehman (AI-23036)\n"
    "- Owais Tariq (AI-23037)\n"
    "- Shaikh Muhammad Zain (AI-23306)")

tabs = st.tabs(["Overview", "Knowledge base", "Frames & script", "Semantic network",
                "First-order logic", "Description logic", "Forward chaining",
                "Backward chaining", "Test cases", "Playground"])


def decisions_table(r) -> pd.DataFrame:
    rows = []
    for o in r.outcomes():
        rows.append({"Driver": o.person, "Space": o.space,
                     "Decision": "Allocated" if o.allocated else "Denied",
                     "Reason (from backward chaining)": "; ".join(o.reasons[:2])})
    return pd.DataFrame(rows)


def proof_dot(node: ProofNode) -> str:
    lines = ["digraph Proof {", "rankdir=LR;", 'node [shape=box, fontname="Helvetica", fontsize=10];']
    counter = [0]

    def visit(n: ProofNode) -> str:
        counter[0] += 1
        nid = f"n{counter[0]}"
        colour = {"fact": "#dcfce7", "built-in": "#f1f5f9",
                  "negation as failure": "#fee2e2"}.get(n.how, "#dbeafe")
        label = n.text.replace('"', "'") + f"\\n[{n.how}]"
        lines.append(f'{nid} [label="{label}", style=filled, fillcolor="{colour}"];')
        for c in n.children:
            lines.append(f"{nid} -> {visit(c)};")
        return nid

    visit(node)
    lines.append("}")
    return "\n".join(lines)


# ----- Overview ------------------------------------------------------------------

with tabs[0]:
    st.header("Smart Parking Access & Space Allocation Reasoning System")
    st.write("A multi-paradigm knowledge-based system. The campus parking domain is "
             "captured in frames and a semantic network, constrained with first-order "
             "and description logic, and decided by Horn-clause rules run with forward "
             "and backward chaining.")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Facts", len(R.forward.initial))
    c2.metric("Rules", len(RULES))
    c3.metric("Derived facts", len(R.forward.derived))
    c4.metric("FC cycles", len(R.forward.cycles))
    c5.metric("Constraint violations", len(R.forward.violations))
    st.subheader("Decisions for this scenario")
    if R.kb.facts_for("requests"):
        st.dataframe(decisions_table(R), hide_index=True, width="stretch")
    else:
        st.info("This scenario has no parking requests.")
    if R.forward.violations:
        for c, s in R.forward.violations:
            st.error(f"{c.cid}: {c.natural}")
    st.subheader("How the paradigms connect")
    st.markdown(
        "1. Frames hold the individuals, slots, facets and defaults. They are translated "
        "into ground facts.\n"
        "2. The semantic network is drawn from the same frames.\n"
        "3. Horn rules R01-R28 derive authorization, eligibility, priority and allocation.\n"
        "4. Forward chaining computes everything that follows; backward chaining proves one "
        "goal and explains failures.\n"
        "5. FOL statements and DL axioms are checked against the result.")

# ----- Knowledge base -------------------------------------------------------------

with tabs[1]:
    st.header("Knowledge base")
    left, right = st.columns([1, 2])
    with left:
        st.subheader(f"Facts ({len(R.kb.facts)})")
        for title, rows in grouped(R.kb.facts):
            with st.expander(f"{title} ({len(rows)})"):
                st.code("\n".join(rows), language="prolog")
    with right:
        st.subheader(f"Rules ({len(RULES)})")
        group = st.selectbox("Rule group", ["All"] + sorted({r.group for r in RULES}))
        for rule in RULES:
            if group != "All" and rule.group != group:
                continue
            with st.expander(f"{rule.rid}  {rule.natural}"):
                st.code(rule.text, language="prolog")
                st.markdown(f"FOL: `{rule.to_fol()}`")
                if rule.explanation:
                    st.caption(rule.explanation)
                st.caption(f"Stratum {rule.stratum}")
        st.subheader("Integrity constraints (denial clauses)")
        st.dataframe(pd.DataFrame([{"Id": c.cid, "Clause": c.text, "Meaning": c.natural}
                                   for c in CONSTRAINTS]), hide_index=True,
                     width="stretch")

# ----- Frames & script ------------------------------------------------------------

with tabs[2]:
    st.header("Frames")
    fs = build_frames()
    c1, c2 = st.columns(2)
    with c1:
        cls = st.selectbox("Class frame", [f.name for f in fs.classes()])
        st.code(fs.describe(cls))
        rows = []
        for name, spec in fs.slot_specs(cls).items():
            facets = spec.facets()
            rows.append({"Slot": name, **{k: str(v) for k, v in facets.items()},
                         "Defined in": fs.defining_frame(cls, name, "type")})
        st.dataframe(pd.DataFrame(rows).fillna(""), hide_index=True, width="stretch")
    with c2:
        inst = st.selectbox("Instance frame", [f.name for f in fs.instances()])
        st.code(fs.describe(inst))
        st.caption("Each value shows where it came from: own value, an inherited default, "
                   "or an if-needed procedure.")
        facts = [f for f in fs.to_facts() if f[1] == inst]
        st.markdown("Translated into logic:")
        st.code("\n".join(f"{f[0]}({', '.join(map(str, f[1:]))})." for f in facts),
                language="prolog")
    errors = fs.validate()
    if errors:
        st.error("; ".join(errors))
    else:
        st.success("All instance values satisfy their facets.")

    st.header("Script: ParkingSession")
    st.code(PARKING_SESSION.describe())
    sc1, sc2 = st.columns(2)
    driver = sc1.selectbox("Driver", PEOPLE, key="script_driver")
    space = sc2.selectbox("Space", SPACES, key="script_space")
    kb = R.kb.copy()
    if not any(f[1] == driver and f[2] == space for f in kb.facts_for("requests")):
        kb.add_fact(("requests", driver, space, 999))
        st.caption(f"A request requests({driver}, {space}, 999) was added for this run.")
    script_run = run_parking_script(kb, driver, space)
    for res in script_run.scenes:
        mark = "PASS" if res.passed else "STOP"
        st.markdown(f"Scene {res.scene.number} **{res.scene.name}** `{res.goal}` → {mark}"
                    + (f"  \n&nbsp;&nbsp;&nbsp;{res.detail}" if res.detail else ""))
    st.info("Script completed: the driver is parked." if script_run.completed
            else "Script stopped: the driver is turned away.")

# ----- Semantic network -------------------------------------------------------------

with tabs[3]:
    st.header("Semantic network")
    view = st.radio("View", ["Concepts", "Individual"], horizontal=True)
    if view == "Concepts":
        net = build_class_network()
    else:
        who = st.selectbox("Individual", PEOPLE + SPACES + ["r1", "r2"])
        net = build_instance_network([who])
    st.graphviz_chart(net.to_dot("LR"), width="stretch")
    st.caption("Blue boxes are concepts, yellow ellipses are value concepts, green boxes are "
               "individuals. Thick blue edges are is-a; dashed green edges are instance-of.")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Inheritance")
        node = st.selectbox("Node", list(net.nodes), key="inh")
        inherited = net.inherited_relations(node)
        st.write(f"Superconcepts: {', '.join(net.superconcepts(node)) or 'none'}")
        if inherited:
            st.dataframe(pd.DataFrame(inherited, columns=["Relation", "Target", "Inherited from"]),
                         hide_index=True)
    with c2:
        st.subheader("Path between two nodes")
        full = build_instance_network(PEOPLE + ["r1", "r2"] + SPACES)
        a = st.selectbox("From", list(full.nodes), index=list(full.nodes).index("ali"))
        b = st.selectbox("To", list(full.nodes), index=list(full.nodes).index("Person"))
        path = full.path(a, b)
        if path:
            st.code("\n".join(f"{e.source} --{e.label}--> {e.target}" for e in path))
        else:
            st.write("No path.")

# ----- FOL -------------------------------------------------------------------------

with tabs[4]:
    st.header("First-order logic")
    st.subheader("FOL reading of the Horn rules")
    st.dataframe(pd.DataFrame([{"Rule": r.rid, "FOL": r.to_fol(), "English": r.natural}
                               for r in RULES]), hide_index=True, width="stretch")
    st.subheader("Domain statements beyond Horn clauses, checked on the computed model")
    rows = []
    for stmt, ok, ce in R.fol_report():
        rows.append({"Id": stmt.sid, "Formula": stmt.text, "Meaning": stmt.english,
                     "In this model": "holds" if ok else f"fails for {ce}",
                     "Horn clause form": stmt.horn})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

# ----- DL --------------------------------------------------------------------------

with tabs[5]:
    st.header("Description logic")
    reasoner, abox, realized, clashes = R.dl_report()
    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("TBox")
        st.dataframe(pd.DataFrame([{"Id": ax.aid, "Axiom": str(ax), "Meaning": ax.note}
                                   for ax in TBOX]), hide_index=True, width="stretch",
                     height=420)
    with c2:
        st.subheader("Classification")
        inferred = [(a, b) for a, b, inf in reasoner.classify() if inf]
        st.write("Subsumptions the reasoner derived from definitions:")
        st.code("\n".join(f"{a} ⊑ {b}" for a, b in inferred))
        st.subheader("Consistency")
        if clashes:
            for c in clashes:
                st.error(str(c))
        else:
            st.success("The ABox is consistent with the TBox.")
    st.subheader("Realization")
    who = st.selectbox("Individual", sorted(realized), index=sorted(realized).index("ali"))
    st.write(", ".join(sorted(realized[who])))
    concept = st.selectbox("Ask the DL reasoner", ["AuthorizedDriver", "ValidPermitHolder",
                                                   "BadgeHolder", "AuthorizedStudent"])
    st.info(explain_owa(realized, who, concept))
    with st.expander("ABox assertions"):
        st.code("\n".join(abox.assertions()))

# ----- Forward chaining --------------------------------------------------------------

with tabs[6]:
    st.header("Forward chaining")
    fc = R.forward
    cyc = pd.DataFrame([{"Cycle": c.number, "Stratum": c.stratum,
                         "Conflict set": c.conflict_set, "New facts": c.fired,
                         "Rules fired": ", ".join(c.rules_fired)} for c in fc.cycles])
    st.dataframe(cyc, hide_index=True, width="stretch")
    upto = st.slider("Show inference up to cycle", 1, len(fc.cycles), len(fc.cycles))
    firings = [f for f in fc.firings if f.cycle <= upto]
    st.dataframe(pd.DataFrame([{"Step": f.step, "Cycle": f.cycle, "Rule": f.rule.rid,
                                "Premises": " ∧ ".join(f.premises),
                                "Derived": f.text().splitlines()[-1].split("derive", 1)[1].strip()}
                               for f in firings]),
                 hide_index=True, width="stretch", height=420)
    preds = sorted({f.derived[0] for f in firings})
    pick = st.multiselect("Filter derived facts by predicate", preds,
                          default=[p for p in ("allocate", "loses", "can_allocate") if p in preds])
    st.code("\n".join(f.text().splitlines()[-1].split("derive", 1)[1].strip()
                      for f in firings if f.derived[0] in pick))
    st.download_button("Download full trace", format_trace(fc), file_name=f"forward_{key}.txt")

# ----- Backward chaining --------------------------------------------------------------

with tabs[7]:
    st.header("Backward chaining")
    examples = [R.scenario.focus_goal or "allocate(sara, s_a1)", "can_allocate(ahmed, S)",
                "authorized_driver(usman)", "allocate(ali, s_a1)", "eligible_for_space(X, s_a3)",
                "located_in(S, zone_a), space_free(S)"]
    choice = st.selectbox("Example goals", examples)
    goal = st.text_input("Goal (Prolog syntax, variables start with a capital)", choice)
    try:
        result = BackwardChainer(R.kb).prove(goal)
        (st.success if result.success else st.error)(result.summary())
        c1, c2 = st.columns([3, 2])
        with c1:
            st.subheader(f"Trace ({len(result.trace)} steps)")
            st.code(result.format_trace(max_lines=400))
        with c2:
            if result.proofs:
                st.subheader("Proof tree")
                st.graphviz_chart(proof_dot(result.proofs[0]), width="stretch")
                st.caption("Rules used: " + ", ".join(dict.fromkeys(result.proofs[0].rules_used())))
            else:
                st.subheader("Why not?")
                lits = parse_query(goal)
                if len(lits) == 1 and lits[0].kind == "atom":
                    st.code(R.explain(goal))
                else:
                    st.write("Explanations are given for single goals.")
    except (ParseError, ReasoningError) as exc:
        st.error(f"Could not run the query: {exc}")

# ----- Test cases -------------------------------------------------------------------

with tabs[8]:
    st.header("Test cases")
    rows, details = [], {}
    for sc in TEST_CASES:
        r = cached_run(sc.key)
        checks = r.check_expectations()
        ok = all(e == f == b for _, e, f, b in checks)
        rows.append({"Case": sc.title, "Checks": len(checks),
                     "Forward = backward = expected": "yes" if ok else "NO",
                     "Constraint violations": ", ".join(c.cid for c, _ in r.forward.violations)})
        details[sc.title] = (sc, r, checks)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    pick = st.selectbox("Inspect a case", list(details))
    sc, r, checks = details[pick]
    st.write(sc.description)
    st.dataframe(pd.DataFrame(checks, columns=["Goal", "Expected", "Forward", "Backward"]),
                 hide_index=True)
    if sc.focus_goal:
        st.markdown(f"Backward chaining on `{sc.focus_goal}`")
        res = r.prove(sc.focus_goal)
        if res.success:
            st.code("\n".join(res.proofs[0].render()))
        else:
            st.code(r.explain(sc.focus_goal))

# ----- Playground --------------------------------------------------------------------

with tabs[9]:
    st.header("Playground")
    st.write("Set the date, the hour and the requests, then let the reasoner decide.")
    c1, c2 = st.columns(2)
    date = c1.number_input("Date (YYYYMMDD)", value=TODAY, step=1)
    hour = c2.slider("Hour", 0, 23, 10)
    default = pd.DataFrame([{"driver": "ali", "space": "s_a1", "time": 905},
                            {"driver": "zara", "space": "s_a1", "time": 850},
                            {"driver": "bilal", "space": "s_v1", "time": 920}])
    edited = st.data_editor(default, num_rows="dynamic", width="stretch",
                            column_config={
                                "driver": st.column_config.SelectboxColumn(options=PEOPLE),
                                "space": st.column_config.SelectboxColumn(options=SPACES),
                                "time": st.column_config.NumberColumn(min_value=0, max_value=2359)})
    extra = st.text_area("Extra facts (one per line, optional)", "",
                         placeholder="accessibility_badge(ali, yes)")
    if st.button("Reason", type="primary"):
        requests = [(row.driver, row.space, int(row.time)) for row in edited.itertuples()
                    if isinstance(row.driver, str) and isinstance(row.space, str)]
        custom = Scenario("custom", "Custom scenario", "Built in the playground.",
                          requests=requests, date=int(date), hour=int(hour),
                          add=[l.strip().rstrip(".") for l in extra.splitlines() if l.strip()],
                          expectations=[Expectation(f"allocate({p}, {s})", True)
                                        for p, s, _ in requests])
        try:
            cr = run_custom(custom)
            st.dataframe(decisions_table(cr), hide_index=True, width="stretch")
            st.caption(f"{len(cr.forward.derived)} facts derived in {len(cr.forward.cycles)} cycles.")
            for c, _ in cr.forward.violations:
                st.error(f"{c.cid}: {c.natural}")
            with st.expander("Forward chaining trace"):
                st.code(format_trace(cr.forward, show_initial=False))
        except (ParseError, ReasoningError, ValueError) as exc:
            st.error(f"Could not reason about this input: {exc}")
