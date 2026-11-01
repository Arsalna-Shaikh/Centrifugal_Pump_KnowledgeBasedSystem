"""The 15 manual evaluation scenarios as regression tests (engine level and Streamlit UI level).

Inputs follow the manual test sheet.  Mapping to the new KBS (documented fixture):
- the legacy page's healthy defaults are used as the healthy baseline: flow 100 m3/h (so 'flow %' = m3/h),
  pump head 5.0 - 1.25 = 3.75 bar, motor current 32 A; pump design 'not specified';
- a ticked checkbox -> observation 'present'; an unticked one -> 'absent' (the sheet says "No");
  'Pump primed: Yes' -> loss of prime 'absent';  Test 11 leaves everything blank / unknown.

Assertions encode what the knowledge base and rules imply for these inputs - they do not force a
ranking.  Several scenarios are not diagnostic enough to separate faults; for those the tests assert
that the uncertainty is preserved and visible (see the final evaluation report).
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from decision_support import ui_adapter as ua
from kbs_engine import InferenceEngine, KnowledgeBase

KB = KnowledgeBase()
ENGINE = InferenceEngine(KB)
DEFAULTS = {"IND-01": 2.5, "IND-02": 60.0, "IND-03": 55.0, "IND-05": 100.0, "IND-12": 5.0, "IND-07": 1.25,
            "IND-08": 32.0, "IND-04": 63.0, "IND-09": 2.0}
EQUIPMENT = {"PAR-08": 100.0, "PAR-09": 3.75, "PAR-10": 32.0}
CHECKBOX_SYMPTOMS = ["SYM-14", "SYM-13", "SYM-17", "SYM-15", "SYM-16", "SYM-20", "SYM-21", "SYM-19"]


def inputs(measure=None, present=(), primed=True):
    m = dict(DEFAULTS, **(measure or {}))
    obs = {s: ("present" if s in present else "absent") for s in CHECKBOX_SYMPTOMS}
    obs["SYM-18"] = "absent" if primed else "present"
    return dict(EQUIPMENT), m, obs


def diagnose(measure=None, present=(), primed=True):
    eq, m, obs = inputs(measure, present, primed)
    case, errors, warnings = ua.build_case(KB, "not specified", eq, m, obs, {}, [])
    if errors:
        return None, errors, warnings
    _, rep = ua.run_new_kbs(ENGINE, case)
    return rep, errors, warnings


def status(rep, fid):
    for sec in rep["hypotheses"].values():
        for h in sec:
            if h["id"] == fid:
                return h["diagnostic_status"]
    return None


def likely_or_better(rep):
    return [h["id"] for h in rep["hypotheses"]["diagnoses"]]


def visible_symptoms(rep):
    """Every symptom shown to the user as supporting (incl. partial) or unexplained evidence."""
    seen = {e["symptom_id"] for u in rep["unexplained_evidence"] for e in [u]}
    for sec in rep["hypotheses"].values():
        for h in sec:
            seen |= {e["symptom_id"] for e in h["supporting_evidence"] if "symptom_id" in e}
    return seen


class TestManualScenariosEngine(unittest.TestCase):
    def test_01_healthy_pump_is_normal(self):
        rep, _, _ = diagnose()
        self.assertEqual(rep["outcome"], "OUT-N")
        self.assertEqual(likely_or_better(rep), [])
        self.assertEqual(rep["safety_warnings"], [])

    def test_02_cavitation_is_under_investigation_with_npsh_test(self):
        # crackling + reduced performance; suction pressure normal, head not assessable from baseline
        rep, _, _ = diagnose(present={"SYM-13", "SYM-21"})
        self.assertEqual(status(rep, "FLT-01"), "pending")
        self.assertIn("TST-01", [t["test_id"] for t in rep["recommended_tests"]])
        self.assertEqual(likely_or_better(rep), [])          # not enough evidence for a confident diagnosis
        self.assertIn("SYM-13", visible_symptoms(rep))

    def test_03_loss_of_prime_with_normal_flow_is_not_forced_to_dry_running(self):
        # 'not primed' while delivering 100 % flow is contradictory input; KB requires no-flow for dry running
        rep, _, _ = diagnose(primed=False)
        self.assertNotIn(status(rep, "FLT-02"), ("likely", "confirmed"))
        self.assertEqual(rep["outcome"], "OUT-U")
        self.assertIn("SYM-18", visible_symptoms(rep))       # the observation is shown, not ignored

    def test_03b_genuine_dry_running_gives_critical_warning_and_stop_action(self):
        rep, _, _ = diagnose({"IND-05": 3.0}, primed=False)
        self.assertEqual(status(rep, "FLT-02"), "likely")
        self.assertIn("SAF-01", [w["safety_id"] for w in rep["safety_warnings"]])
        self.assertIn("ACT-03", [a["action_id"] for a in rep["maintenance_actions"]])

    def test_04_air_bubbles_alone_are_shown_but_not_diagnosed(self):
        rep, _, _ = diagnose(present={"SYM-17"})
        self.assertEqual(likely_or_better(rep), [])
        u = next(x for x in rep["unexplained_evidence"] if x["symptom_id"] == "SYM-17")
        self.assertIn("FLT-03", [x["id"] for x in u["linked_to"]])

    def test_05_bearing_failure(self):
        rep, _, _ = diagnose({"IND-01": 7.0, "IND-02": 85.0}, present={"SYM-14"})
        top = rep["hypotheses"]["diagnoses"][0]
        self.assertEqual((top["id"], top["diagnostic_status"], top["knowledge_support"]), ("FLT-04", "likely", "Strong"))

    def test_06_seal_failure_uses_visible_leakage(self):
        rep, _, _ = diagnose({"IND-03": 90.0}, present={"SYM-15"})
        top = rep["hypotheses"]["diagnoses"][0]
        self.assertEqual(top["id"], "FLT-06")
        self.assertIn("SYM-15", [e["symptom_id"] for e in top["supporting_evidence"]])
        self.assertIn("SYM-03", [e["symptom_id"] for e in top["supporting_evidence"]])

    def test_07_low_flow_without_discriminating_evidence_stays_open(self):
        rep, _, _ = diagnose({"IND-05": 40.0})
        self.assertNotIn(status(rep, "FLT-02"), ("possible", "likely", "confirmed"))   # no false dry running
        self.assertEqual(likely_or_better(rep), [])
        self.assertEqual(rep["outcome"], "OUT-U")
        self.assertTrue({"FLT-08", "FLT-09"} <= {h["id"] for h in rep["hypotheses"]["under_investigation"]})

    def test_08_discharge_restriction_with_safety(self):
        rep, _, _ = diagnose({"IND-05": 40.0}, present={"SYM-19"})
        self.assertEqual(status(rep, "FLT-09"), "likely")
        self.assertIn("SAF-02", [w["safety_id"] for w in rep["safety_warnings"]])

    def test_09_coupling_vibration_shown_with_kb_links(self):
        rep, _, _ = diagnose({"IND-01": 7.0}, present={"SYM-16"})
        self.assertEqual(likely_or_better(rep), [])
        u = next(x for x in rep["unexplained_evidence"] if x["symptom_id"] == "SYM-16")
        self.assertTrue({"FLT-05", "FLT-12"} <= {x["id"] for x in u["linked_to"]})

    def test_10_reduced_performance_low_flow_keeps_competing_causes(self):
        rep, _, _ = diagnose({"IND-05": 60.0}, present={"SYM-21"})
        self.assertEqual(likely_or_better(rep), [])
        self.assertEqual((status(rep, "FLT-10"), status(rep, "FLT-08")), ("possible", "pending"))
        self.assertIn("TST-11", [t["test_id"] for t in rep["recommended_tests"]])

    def test_11_incomplete_information_is_unknown(self):
        case, errors, warnings = ua.build_case(KB, "not specified", {}, {i: None for i in DEFAULTS}, {}, {}, [])
        self.assertEqual(errors, [])
        self.assertEqual(case.measurements, {})              # blanks are not turned into zeros
        _, rep = ua.run_new_kbs(ENGINE, case)
        self.assertEqual(rep["outcome"], "OUT-U")
        self.assertFalse(any(rep["hypotheses"].values()))
        self.assertTrue(any("can only be Unknown" in w for w in warnings))

    def test_12_conflicting_pressures_detected_not_normal(self):
        rep, _, warnings = diagnose({"IND-12": 1.0})
        self.assertNotEqual(rep["outcome"], "OUT-N")
        self.assertIn("inconsistent_measurements", [c["type"] for c in rep["data_conflicts"]])
        self.assertTrue(any("below suction" in w for w in warnings))

    def test_13_competing_faults_both_kept_with_separate_explanations(self):
        rep, _, _ = diagnose({"IND-01": 7.0, "IND-02": 85.0, "IND-03": 90.0}, present={"SYM-14", "SYM-15"})
        diag = {h["id"]: h for h in rep["hypotheses"]["diagnoses"]}
        self.assertTrue({"FLT-04", "FLT-06"} <= set(diag))
        self.assertTrue(rep["competing_diagnoses"])
        self.assertTrue(all(r["rule_id"].startswith("R-BRG") for r in diag["FLT-04"]["explanation"]))
        self.assertTrue(all(r["rule_id"].startswith("R-SEAL") for r in diag["FLT-06"]["explanation"]))

    def test_14_invalid_input_rejected_before_diagnosis(self):
        rep, errors, _ = diagnose({"IND-01": -5.0, "IND-05": -20.0, "IND-02": -100.0})
        self.assertIsNone(rep)
        self.assertEqual(len(errors), 3)

    def test_15_zero_flow_raises_saf02_without_forcing_restriction(self):
        rep, _, _ = diagnose({"IND-05": 0.0})
        self.assertIn("SAF-02", [w["safety_id"] for w in rep["safety_warnings"]])
        self.assertNotIn(status(rep, "FLT-09"), ("likely", "confirmed"))
        self.assertNotIn(status(rep, "FLT-02"), ("likely", "confirmed"))   # primed -> not dry running
        self.assertEqual(rep["outcome"], "OUT-U")


HAS_STREAMLIT = importlib.util.find_spec("streamlit") is not None
ROOT = Path(__file__).resolve().parents[2]
SUBMIT = "FormSubmitter:diagnosis_form-Run new KBS diagnosis"
if HAS_STREAMLIT:
    from streamlit.testing.v1 import AppTest


@unittest.skipUnless(HAS_STREAMLIT, "streamlit not installed in this interpreter")
class TestManualScenariosUI(unittest.TestCase):
    def page(self):
        return AppTest.from_file(str(ROOT / "src" / "pages" / "1_New_KBS_Diagnosis.py"), default_timeout=120).run()

    def fill(self, at, measure=None, present=(), primed=True, blank=False):
        if not blank:
            eq, m, obs = inputs(measure, present, primed)
            for k, v in eq.items():
                at.number_input(key=f"eq_{k}").set_value(v)
            for k, v in m.items():
                at.number_input(key=f"m_{k}").set_value(v)
            for k, v in obs.items():
                at.radio(key=f"obs_{k}").set_value(v)
        at.button(key=SUBMIT).click().run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    @staticmethod
    def outcome(at):
        return next((m.value for m in at.metric if m.label == "Outcome"), None)

    def test_ui_01_healthy_shows_explicit_normal(self):
        at = self.fill(self.page())
        self.assertEqual(self.outcome(at), "Normal")
        self.assertTrue(any("No fault indicated" in s.value for s in at.success))

    def test_ui_11_blank_inputs_show_unknown(self):
        at = self.fill(self.page(), blank=True)
        self.assertEqual(self.outcome(at), "Unknown")
        self.assertIsNone(at.session_state["m_IND-05"])

    def test_ui_14_invalid_values_reach_validator_and_clear_previous_result(self):
        at = self.fill(self.page(), {"IND-01": 7.0, "IND-02": 85.0}, present={"SYM-14"})
        self.assertEqual(self.outcome(at), "Diagnosis")
        at = self.fill(at, {"IND-01": -5.0, "IND-05": -20.0, "IND-02": -100.0})
        self.assertIsNone(self.outcome(at))                   # no stale report shown
        errors = [e.value for e in at.error]
        self.assertTrue(any("Diagnosis NOT run" in e for e in errors))
        self.assertEqual(sum("Invalid input" in e for e in errors), 3)
        self.assertEqual(at.session_state["m_IND-01"], -5.0)  # not clamped by the widget

    def test_ui_15_zero_flow_safety_rendered(self):
        at = self.fill(self.page(), {"IND-05": 0.0})
        self.assertTrue(any(e.value.startswith("SAFETY:") and "zero flow" in e.value for e in at.error))
        self.assertEqual(next(m.value for m in at.metric if m.label == "Safety warnings"), "1")

    def test_ui_12_inconsistent_pressures_not_normal(self):
        at = self.fill(self.page(), {"IND-12": 1.0})
        self.assertNotEqual(self.outcome(at), "Normal")
        self.assertTrue(any("below suction" in w.value for w in at.warning))

    def test_ui_report_states_which_submission_it_belongs_to(self):
        at = self.fill(self.page())
        self.assertTrue(any("Report for submission #1" in c.value for c in at.caption))

    def test_ui_legacy_comparison_score_not_called_probability(self):
        at = self.fill(self.page(), {"IND-01": 7.0, "IND-02": 85.0}, present={"SYM-14"})
        cols = [list(df.value.columns) for df in at.dataframe]
        self.assertTrue(any("legacy evidence score % (not a probability)" in c for c in cols))
        self.assertFalse(any("confidence" in c for c in cols))

    def test_ui_legacy_page_labelled_and_working(self):
        at = AppTest.from_file(str(ROOT / "src" / "app.py"), default_timeout=60).run()
        self.assertTrue(any("LEGACY ENGINE" in i.value for i in at.info))
        at.button[0].click().run()
        self.assertFalse(at.exception)


if __name__ == "__main__":
    unittest.main()
