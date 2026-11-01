"""Streamlit page: new layered KBS (knowledge_base/ + kbs_engine/ + decision_support/).

Streamlit adds this page automatically because it lives in src/pages/ next to src/app.py.
The legacy page (src/app.py) is unchanged and remains available for comparison.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datetime import datetime

import pandas as pd
import streamlit as st

from decision_support import render_text
from decision_support import ui_adapter as ua
from kbs_engine import InferenceEngine, KnowledgeBase

st.set_page_config(page_title="New KBS Diagnosis", page_icon="🔧", layout="wide")


@st.cache_resource
def load_engine():
    kb = KnowledgeBase()
    return kb, InferenceEngine(kb)


kb, engine = load_engine()
OBSERVED = ua.observed_symptoms(kb)
TESTS = ua.test_options(kb)                  # only tests that a rule can interpret
LIMITS = ua.site_limits(kb)                  # thresholds with no sourced value (used only if a site value is given)

# ------------------------------------------------------------------ session-state defaults (blank = unknown)
DEFAULTS = {"eq_pump_design": "not specified", "est": [], "opt_legacy_thresholds": False, "opt_compare": True}
DEFAULTS.update({f"eq_{pid}": None for pid, _ in ua.EQUIPMENT_FIELDS})
DEFAULTS.update({f"m_{iid}": None for iid, *_ in ua.MEASUREMENT_FIELDS})
DEFAULTS.update({f"obs_{sid}": "unknown" for sid, _ in OBSERVED})
DEFAULTS.update({f"test_{tid}": ua.TEST_NOT_DONE for tid in TESTS})
DEFAULTS.update({f"lim_{t['threshold_id']}": None for t in LIMITS})
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)

_PUMP = {"eq_pump_design": "radial", "eq_PAR-02": 100.0, "eq_PAR-03": 5.0, "eq_PAR-04": 50.0}
_HEALTHY = {"m_IND-01": 2.0, "m_IND-02": 55.0, "m_IND-03": 50.0, "m_IND-04": 65.0, "m_IND-05": 95.0,
            "m_IND-07": 1.5, "m_IND-12": 6.6, "m_IND-08": 47.0, "m_IND-09": 2.0}
EXAMPLES = {
    "Healthy pump": {**_PUMP, **_HEALTHY},
    "Cavitation": {**_PUMP, **_HEALTHY, "m_IND-07": 0.5, "m_IND-12": 4.4, "obs_SYM-13": "present"},
    "Dry running (incomplete data)": {**_PUMP, **_HEALTHY, "m_IND-05": 3.0, "m_IND-12": 2.0},
    "Competing: cavitation vs air ingress": {**_PUMP, **_HEALTHY, "m_IND-07": 0.5, "m_IND-05": 65.0,
                                             "obs_SYM-13": "present", "obs_SYM-18": "present"},
    "No data": {},
}

st.title("🔧 New KBS Diagnosis")
st.caption("Layered knowledge-based diagnosis (structured knowledge base, forward-chaining engine, "
           "decision-support report). Academic prototype: symptom thresholds are provisional and "
           "not OEM limits. The legacy diagnosis page remains available in the sidebar.")
st.caption("Enter what you know, leave the rest blank, then press **Run new KBS diagnosis**. Measurements are "
           "turned into symptoms, rules infer faults and causes, and the report explains every conclusion. "
           "Hover over the ⓘ icons for what each field is used for.")

with st.sidebar:
    st.header("Example cases")
    choice = st.selectbox("Load an example", list(EXAMPLES), key="example_choice")
    if st.button("Load example"):
        for k, v in DEFAULTS.items():
            st.session_state[k] = v
        st.session_state.update(EXAMPLES[choice])
        st.session_state.pop("ds_result", None)
        st.rerun()
    st.info("Leave a field blank if the value is not known. Blank inputs are treated as **unknown**, "
            "never as normal.")

# ------------------------------------------------------------------ input form
with st.form("diagnosis_form"):
    st.subheader("1. Equipment parameters")
    st.caption("Rated values come from the pump data sheet; healthy-baseline values were measured when this pump "
               "was known to be healthy. They let flow, head and current be judged relative to *this* pump.")
    st.selectbox("Pump design", ua.PUMP_DESIGNS, key="eq_pump_design",
                 help="Radial, mixed or axial impeller. Some evidence differs by design: in a radial pump low flow "
                      "draws LESS motor current (S-01 p.17), so rules R-DIS-2 and N-01 apply only to radial pumps. "
                      "'not specified' leaves those rules unused.")
    cols = st.columns(4)
    for i, (pid, label) in enumerate(ua.EQUIPMENT_FIELDS):
        # no widget min/max: out-of-range values must reach the validator, not be clamped or silently kept
        cols[i % 4].number_input(label, key=f"eq_{pid}", format="%.2f", placeholder="unknown",
                                 help=ua.parameter_help(kb, pid))

    st.subheader("2. Measurements")
    st.caption("Each reading is compared with a provisional limit to decide whether a symptom is present. "
               "A blank reading makes its symptoms *unknown*, never normal.")
    cols = st.columns(4)
    for i, (iid, label, lo, hi) in enumerate(ua.MEASUREMENT_FIELDS):
        cols[i % 4].number_input(label, key=f"m_{iid}", format="%.2f", placeholder="unknown",
                                 help=ua.measurement_help(kb, iid))
    st.multiselect("Values that are estimated (not measured) - evidence will not be derived from them",
                   [iid for iid, *_ in ua.MEASUREMENT_FIELDS],
                   format_func=lambda i: dict((a, b) for a, b, *_ in ua.MEASUREMENT_FIELDS)[i], key="est",
                   help="Tick readings that are guesses or copied from elsewhere. Their symptoms become unknown, so a "
                        "guess can never confirm or rule out a fault.")

    st.subheader("3. Observations")
    st.caption("**present** = seen or heard · **absent** = checked and not found · **unknown** = not checked. "
               "Unknown is never treated as absent; rules that need the observation stay pending.")
    cols = st.columns(3)
    for i, (sid, name) in enumerate(OBSERVED):
        desc = kb.symptoms[sid]["description"]
        cols[i % 3].radio(name, ua.OBSERVATION_STATES, key=f"obs_{sid}", horizontal=True,
                          help=(desc + ". " if desc else "") + f"Symptom {sid}.")

    with st.expander("4. Diagnostic test results (optional)"):
        st.caption("Tests confirm or identify a fault or root cause. Only tests that a rule can interpret are "
                   "listed; 'not done' means no result. Other tests the report may request are interpreted by "
                   "the engineer, not by the system.")
        cols = st.columns(3)
        for i, (tid, options) in enumerate(TESTS.items()):
            cols[i % 3].selectbox(kb.tests[tid]["name"], options, key=f"test_{tid}", help=ua.test_help(kb, tid))

    with st.expander("5. Site-specific limits (optional)"):
        st.caption("The knowledge base has no sourced value for these limits, so they are skipped unless you "
                   "enter your site or manufacturer value. Entered limits are labelled as user-supplied in the "
                   "report. Baseline percentages need the matching healthy-baseline parameter in section 1.")
        cols = st.columns(3)
        for i, t in enumerate(LIMITS):
            unit = {"pct_rated": "% of rated", "pct_baseline": "% of baseline"}.get(t["basis"], t["unit"])
            cols[i % 3].number_input(f"{kb.name(t['symptom_id'])}: {ua._OP[t['operator']]} … {unit}",
                                     key=f"lim_{t['threshold_id']}", format="%.2f", placeholder="not set",
                                     help=f"{t['threshold_id']} on {kb.indicators[t['indicator_id']]['name']}. "
                                          f"{t['notes'] or ''}")

    c1, c2 = st.columns(2)
    c1.checkbox("Allow legacy absolute thresholds when no rated/baseline value is given",
                key="opt_legacy_thresholds", help=ua.legacy_threshold_help(kb))
    c2.checkbox("Compare with the legacy engine", key="opt_compare",
                help="Also runs the old weighted-scoring engine on the same inputs, shown only in the "
                     "'Legacy comparison' tab. It cannot change the new diagnosis.")
    submitted = st.form_submit_button("Run new KBS diagnosis", type="primary")

if submitted:
    ss = st.session_state
    case, errors, warnings = ua.build_case(
        kb, ss["eq_pump_design"],
        {pid: ss[f"eq_{pid}"] for pid, _ in ua.EQUIPMENT_FIELDS},
        {iid: ss[f"m_{iid}"] for iid, *_ in ua.MEASUREMENT_FIELDS},
        {sid: ss[f"obs_{sid}"] for sid, _ in OBSERVED},
        {tid: ss[f"test_{tid}"] for tid in TESTS}, ss["est"],
        {t["threshold_id"]: ss[f"lim_{t['threshold_id']}"] for t in LIMITS})
    ss["ds_submissions"] = ss.get("ds_submissions", 0) + 1
    if errors:
        st.session_state.pop("ds_result", None)
        st.error("Diagnosis NOT run - correct the invalid inputs below. No previous result is shown.")
        for e in errors:
            st.error(f"Invalid input: {e}")
    else:
        try:
            result, report = ua.run_new_kbs(engine, case, ss["opt_legacy_thresholds"])
            # the new diagnosis is complete before the legacy engine runs; the comparison gets a copy of the case
            legacy = ua.run_legacy_isolated(case) if ss["opt_compare"] else None
            st.session_state["ds_result"] = {"report": report, "warnings": warnings, "legacy": legacy,
                                             "tests_entered": ua.test_usage(kb, case, result),
                                             "submission": ss["ds_submissions"],
                                             "time": datetime.now().strftime("%H:%M:%S")}
        except ValueError as exc:
            st.session_state.pop("ds_result", None)
            st.error(f"Invalid input: {exc}")

# ------------------------------------------------------------------ report
saved = st.session_state.get("ds_result")
if saved:
    rep = saved["report"]
    for w in saved["warnings"]:
        st.warning(w)
    st.header("Diagnostic report")
    st.caption(f"Report for submission #{saved['submission']} at {saved['time']}. It does not reflect input "
               "changes made after that - press 'Run new KBS diagnosis' again to update.")
    outcome_label = {"diagnosis": "Diagnosis", "OUT-N": "Normal", "OUT-U": "Unknown"}[rep["outcome"]]
    if rep["safety_warnings"]:
        st.error(rep["headline"])
    elif rep["outcome"] == "OUT-N":
        st.success(rep["headline"])
    elif rep["outcome"] == "OUT-U":
        st.warning(f"UNKNOWN - {rep['outcome_text']}. {rep['headline']}")
    else:
        st.info(rep["headline"])
    s = rep["evidence_summary"]
    c = st.columns(5)
    c[0].metric("Outcome", outcome_label)
    c[1].metric("Diagnoses", len(rep["hypotheses"]["diagnoses"]))
    c[2].metric("Safety warnings", len(rep["safety_warnings"]))
    c[3].metric("Evidence present / absent", f"{s['present']} / {s['absent']}")
    c[4].metric("Evidence unknown", s["unknown"])

    for w in rep["safety_warnings"]:
        st.error(f"⚠️ SAFETY: {w['message']}  \nTriggered by: {'; '.join(w['triggered_by'])} "
                 f"(knowledge support: {w['knowledge_support']})")
    for w in rep["work_precautions"]:
        st.info(f"Work precaution: {w['message']} ({w['safety_id']})")

    with st.expander("How to read this report"):
        st.markdown(
            "- **Outcome** - *Diagnosis*: at least one fault is likely or confirmed. *Normal*: every symptom that "
            "could be assessed is known to be absent. *Unknown*: the evidence is not enough for a diagnosis "
            "(missing readings, unknown observations, only possible or pending faults). The system then asks for "
            "the missing information or tests instead of guessing.\n"
            "- **Diagnostic status** - how strongly this case's evidence points to the fault: confirmed (a test "
            "result matched) > likely > possible > pending (some evidence, more needed) > unlikely > blocked.\n"
            "- **Knowledge support** - how well the rule behind it is sourced: Strong (independent engineering "
            "source), Moderate (manufacturer source), Unvalidated (project knowledge only - shown at most as "
            "'possible'). Status and support are separate questions.\n"
            "- **Hazard class** - how dangerous the fault type is in general; it is not a measure of this case.\n"
            "- **Cost / downtime** - qualitative classes (LOW / MEDIUM / HIGH) inherited from the legacy knowledge "
            "base; Unvalidated, no money or hours.\n"
            "- **Maintenance priority** - P1 immediate (make-safe action or active safety warning), P2 high "
            "(likely or confirmed fault), P3 planned (everything else). A project policy, Unvalidated.\n"
            "- **Safety warnings** are checked against every hypothesis, not only the top one.")

    # evidence status labels in the diagnosis panels (Streamlit badges adapt to light and dark themes)
    BADGE = {"present": ":green-badge[Present]", "absent": ":gray-badge[Absent]",
             "unknown": ":orange-badge[Unknown]", "not_used": ":gray-badge[Not used]",
             "test": ":green-badge[Test result]"}
    _esc = lambda s: s.replace("[", "\\[").replace("]", "\\]")    # keep text intact inside :gray[...]

    tabs = st.tabs(["Diagnoses", "Root causes", "Evidence", "Tests & information needed",
                    "Maintenance actions", "Full report", "Legacy comparison"])
    titles = {"diagnoses": "Diagnoses (confirmed / likely)", "also_possible": "Also possible",
              "under_investigation": "Under investigation - more information needed",
              "ruled_out_or_argued_against": "Ruled out / argued against"}
    with tabs[0]:
        st.caption("Fault hypotheses grouped by diagnostic status, each with its evidence, missing evidence and "
                   "the rules (with sources) that produced it.")
        if rep["competing_diagnoses"]:
            for cd in rep["competing_diagnoses"]:
                st.warning("Competing diagnoses: " + " vs ".join(f["name"] for f in cd["faults"]) +
                           ". Carry out the discriminating tests.")
        if not any(rep["hypotheses"].values()):
            st.write("No fault hypotheses.")
        if rep["unexplained_evidence"]:
            st.subheader("Evidence not explained by any rule")
            st.caption("These observations are present but no diagnostic rule's conditions are met. The links below "
                       "come from the knowledge base and are NOT diagnoses.")
            for u in rep["unexplained_evidence"]:
                links = "; ".join(f"{x['name']} (support {x['knowledge_support']}"
                                  + (f", {x['condition']}" if x["condition"] else "") + ")"
                                  for x in u["linked_to"]) or "no link in the knowledge base"
                st.markdown(f"- **{u['symptom']}** - linked to: {links}")
        if any(rep["hypotheses"].values()):
            st.caption(f"Evidence labels: {BADGE['present']} observed or measured and used by a rule · "
                       f"{BADGE['absent']} checked and not found · {BADGE['unknown']} not yet known - a rule is "
                       f"waiting for it · {BADGE['not_used']} present, but its rule still needs other evidence, "
                       "so it does not count yet")
        for key, title in titles.items():
            hs = rep["hypotheses"][key]
            if not hs:
                continue
            st.subheader(title)
            for h in hs:
                head = f"{h['rank']}. " if h["rank"] else ""
                with st.expander(f"{head}{h['name']} - status: {h['diagnostic_status']} | "
                                 f"knowledge support: {h['knowledge_support']}", expanded=(key == "diagnoses")):
                    st.markdown(f"**Diagnostic status:** {h['diagnostic_status_text']}  \n"
                                f"**Knowledge support:** {h['knowledge_support_text']}  \n"
                                f"**Hazard class:** {h['hazard']['class']} (support {h['hazard']['knowledge_support']}) "
                                "- case severity not assessed  \n"
                                f"**Repair cost / downtime:** {h['maintenance_impact']['cost_class']} / "
                                f"{h['maintenance_impact']['downtime_class']} (qualitative, support "
                                f"{h['maintenance_impact']['knowledge_support']})")
                    lines = []
                    for e in h["supporting_evidence"]:
                        text = (f"{e.get('symptom', e.get('test'))}: {e.get('state', e.get('result'))}"
                                + (f" - {e['reading']}" if e.get("reading") else ""))
                        if e.get("partial"):
                            lines.append(f"- {BADGE['not_used']} :gray[{_esc(text)} (partial: {e['for_rule']} "
                                         "still needs more information)]")
                        else:
                            lines.append(f"- {BADGE['present'] if 'symptom' in e else BADGE['test']} {text}")
                    for cx in h["contradicting_evidence"]:
                        ev = ", ".join(f"{BADGE.get(x['state'], BADGE['unknown'])} {x['symptom']}" for x in cx["evidence"])
                        lines.append(f"- {cx['effect']} by {cx['rule_id']}: {ev} - {cx['reasoning']}")
                    for x in h["expected_but_absent"]:
                        lines.append(f"- {BADGE['absent']} expected symptom absent: {x['symptom']} "
                                     f"(support {x['knowledge_support']})")
                    for mi in h["missing_evidence"]:
                        lines.append(f"- {BADGE['unknown']} {mi['rule_id']} needs: {', '.join(mi['needs'])}")
                    if lines:
                        st.markdown("\n".join(lines))
                    for ex in h["explanation"]:
                        cap = " → shown as 'possible' (unvalidated knowledge)" if ex["capped_because_unvalidated"] else ""
                        st.markdown(f"**Why ({ex['rule_id']})**: {ex['reasoning']}  \n"
                                    f"rule likelihood: {ex['rule_likelihood']}{cap}; knowledge support: "
                                    f"{ex['knowledge_support']}; sources: "
                                    + ", ".join(f"{s_['id']} ({s_['title']})" for s_ in ex["sources"]))
                        for a in ex["assumptions"]:
                            st.caption(f"Assumption: {a}")
    with tabs[1]:
        st.caption("Why the fault happened: concluded root causes, candidate causes from the knowledge base with the "
                   "test that would confirm each, and fault-to-fault chains.")
        if rep["root_causes"]:
            st.dataframe(pd.DataFrame([{"cause": c_["name"], "status": c_["diagnostic_status"],
                                        "knowledge support": c_["knowledge_support"]} for c_ in rep["root_causes"]]),
                         hide_index=True)
        if rep["candidate_root_causes"]:
            st.markdown("**Candidate root causes** (from knowledge base; not yet confirmed)")
            st.dataframe(pd.DataFrame([{"fault": c_["fault"], "candidate cause": c_["cause"],
                                        "knowledge support": c_["knowledge_support"],
                                        "confirm with": ", ".join(t["test"] for t in c_["confirm_with"]) or "-"}
                                       for c_ in rep["candidate_root_causes"]]), hide_index=True)
        for ch in rep["fault_chains"]:
            st.write(f"Fault chain: {ch['from']} → {ch['to']} (support {ch['knowledge_support']})")
        if not (rep["root_causes"] or rep["candidate_root_causes"]):
            st.write("No root-cause information for this case.")
    with tabs[2]:
        st.caption("Every symptom the engine could assess: its state, where it came from (sensor, observation, "
                   "implied, conflict) and the reading and limit used. Readings marked NOT USED were estimated or "
                   "inconsistent. Symptoms not listed had no reading or observation (unknown).")
        st.dataframe(pd.DataFrame([{"symptom": e["symptom"], "state": e["state"], "source": e["source"] or "",
                                    "reading / threshold": e.get("reading", "")} for e in rep["evidence"]]),
                     hide_index=True)
        for dcf in rep["data_conflicts"]:
            st.warning(f"Data conflict ({dcf['type']}): {dcf['detail']}")
    with tabs[3]:
        st.caption("What to do next to reach or confirm a diagnosis: discriminating tests (to separate competing "
                   "faults), confirming tests, and observations that would let pending rules decide.")
        for t in saved.get("tests_entered", []):
            used = ("used by rule " + ", ".join(t["used_by"])) if t["used_by"] else \
                "no rule drew a conclusion from this result for this case"
            st.markdown(f"- Test result entered: **{t['test']}** = `{t['result']}` - {used}")
        if rep["recommended_tests"]:
            st.dataframe(pd.DataFrame([{"test": t["test"], "type": t["kind"], "measures": t["measures"],
                                        "requested by": ", ".join(t["why"])} for t in rep["recommended_tests"]]),
                         hide_index=True)
        else:
            st.write("No diagnostic tests requested.")
        if rep["information_needed"]:
            st.markdown("**Information needed** (unknown is never treated as absent)")
            st.markdown("\n".join(f"- {o['needed']} ({o['for_rule']})" for o in rep["information_needed"]))
    with tabs[4]:
        if rep["maintenance_actions"]:
            st.caption("Ordered by maintenance priority (P1 immediate, P2 high, P3 planned), a project policy based on "
                       "safety warnings, action purpose and diagnostic status. Cost and downtime are qualitative "
                       "classes inherited from the legacy knowledge base. Both are Unvalidated and do not affect "
                       "the diagnosis.")
            st.dataframe(pd.DataFrame([{"priority": a["maintenance_priority"]["level"], "action": a["action"],
                                        "for": ", ".join(f["name"] for f in a["for"]),
                                        "purpose": a["purpose"], "competence": a["competence"],
                                        "cost": a["cost_downtime"]["cost_class"],
                                        "downtime": a["cost_downtime"]["downtime_class"],
                                        "knowledge support": ", ".join(k["support"] for k in a["knowledge_support"]),
                                        "precautions": "; ".join(p["message"] for p in a["precautions"])}
                                       for a in rep["maintenance_actions"]]), hide_index=True)
        else:
            st.write("No maintenance actions recommended.")
    with tabs[5]:
        st.caption("The complete report as plain text, for printing or attaching to a work order.")
        text = render_text(rep)
        st.code(text, language=None)
        st.download_button("Download report (.txt)", text, file_name="pump_diagnostic_report.txt")
    with tabs[6]:
        st.caption("For comparison only: the old weighted-scoring engine on the same inputs. It ran after the new "
                   "diagnosis was complete and has no influence on it.")
        if saved["legacy"] is None:
            st.write("Legacy comparison not requested.")
        elif not saved["legacy"]["ok"]:
            st.warning(f"The legacy engine failed on these inputs ({saved['legacy']['error']}). "
                       "The new diagnosis above is unaffected.")
        else:
            results, evidence, notes = saved["legacy"]["data"]
            st.markdown("**Legacy engine** (`src/inference_engine.py`, unchanged): weighted single-pass scoring.")
            st.write("Legacy evidence: " + (", ".join(evidence) if evidence else "none"))
            if evidence:
                st.dataframe(pd.DataFrame([{"fault": r_["fault"],
                                            "legacy evidence score % (not a probability)": r_["confidence"],
                                            "safety_priority": r_["safety_priority"]} for r_ in results]),
                             hide_index=True)
            for n in notes:
                st.caption(n)
