"""Functional audit of the New KBS Diagnosis page (Streamlit AppTest): every input reaches the engine and changes
the result as the knowledge base says, every tab shows its content, the legacy comparison is isolated, and the
15 manual scenarios give their recorded outcomes through the real page.

Skipped automatically when Streamlit is not installed in the running interpreter.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock

from decision_support import ui_adapter as ua
from kbs_engine import KnowledgeBase

ROOT = Path(__file__).resolve().parents[2]
PAGE = str(ROOT / "src" / "pages" / "1_New_KBS_Diagnosis.py")
SUBMIT = "FormSubmitter:diagnosis_form-Run new KBS diagnosis"
HAS_STREAMLIT = importlib.util.find_spec("streamlit") is not None
KB = KnowledgeBase()
if HAS_STREAMLIT:
    from streamlit.testing.v1 import AppTest

# manual-scenario fixture (same as test_manual_scenarios.py)
BASE_EQ = {"PAR-08": 100.0, "PAR-09": 3.75, "PAR-10": 32.0}
BASE_M = {"IND-01": 2.5, "IND-02": 60.0, "IND-03": 55.0, "IND-05": 100.0, "IND-12": 5.0, "IND-07": 1.25,
          "IND-08": 32.0, "IND-04": 63.0, "IND-09": 2.0}
CHECKBOXES = ["SYM-14", "SYM-13", "SYM-17", "SYM-15", "SYM-16", "SYM-20", "SYM-21", "SYM-19"]


class PageCase(unittest.TestCase):
    def page(self):
        at = AppTest.from_file(PAGE, default_timeout=120).run()
        self.assertFalse(at.exception)
        return at

    def run_page(self, design=None, eq=None, m=None, obs=None, tests=None, limits=None, est=None,
                 legacy_thresholds=None, compare=None):
        at = self.page()
        if design:
            at.selectbox(key="eq_pump_design").set_value(design)
        for k, v in (eq or {}).items():
            at.number_input(key=f"eq_{k}").set_value(v)
        for k, v in (m or {}).items():
            at.number_input(key=f"m_{k}").set_value(v)
        for k, v in (obs or {}).items():
            at.radio(key=f"obs_{k}").set_value(v)
        for k, v in (tests or {}).items():
            at.selectbox(key=f"test_{k}").set_value(v)
        for k, v in (limits or {}).items():
            at.number_input(key=f"lim_{k}").set_value(v)
        if est is not None:
            at.multiselect(key="est").set_value(est)
        if legacy_thresholds is not None:
            at.checkbox(key="opt_legacy_thresholds").set_value(legacy_thresholds)
        if compare is not None:
            at.checkbox(key="opt_compare").set_value(compare)
        at.button(key=SUBMIT).click().run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    # ---- readers
    @staticmethod
    def outcome(at):
        return next((m.value for m in at.metric if m.label == "Outcome"), None)

    @staticmethod
    def status(at, fault_name):
        """Diagnostic status shown in the hypothesis expander label, or None if the fault is not shown."""
        for e in at.expander:
            if f" {fault_name} - status: " in f" {e.label.split('. ', 1)[-1]}":
                return e.label.split("status: ")[1].split(" |")[0]
        return None

    @staticmethod
    def evidence(at):
        df = next(d.value for d in at.dataframe if "reading / threshold" in d.value.columns)
        return {r["symptom"]: (r["state"], r["reading / threshold"]) for _, r in df.iterrows()}

    @staticmethod
    def full_report(at):
        return next(c.value for c in at.code if "CENTRIFUGAL PUMP DIAGNOSTIC REPORT" in c.value)

    @staticmethod
    def texts(at):
        return [x.value for kind in (at.markdown, at.warning, at.error, at.info, at.caption) for x in kind]


@unittest.skipUnless(HAS_STREAMLIT, "streamlit not installed in this interpreter")
class TestInputsReachEngine(PageCase):
    def test_removed_and_offered_fields(self):
        at = self.page()
        keys = {w.key for w in at.number_input}
        self.assertNotIn("eq_PAR-05", keys)                       # rated speed: no rule or threshold uses it
        self.assertNotIn("eq_PAR-06", keys)                       # Qmin: no rule or threshold uses it
        self.assertEqual({w.key for w in at.selectbox if w.key.startswith("test_")},
                         {f"test_{t}" for t in ("TST-01", "TST-02", "TST-04", "TST-08", "TST-11", "TST-12")})
        self.assertEqual({k for k in keys if k.startswith("lim_")},
                         {f"lim_{t}" for t in ("THR-03", "THR-14", "THR-22", "THR-23", "THR-25")})

    def test_every_input_has_help(self):
        at = self.page()
        for w in list(at.number_input) + list(at.radio) + [s for s in at.selectbox if s.key != "example_choice"] \
                + list(at.checkbox) + list(at.multiselect):
            self.assertTrue(w.help, f"{w.key} has no help text")

    def test_pump_design_changes_result(self):
        args = dict(eq={"PAR-02": 100.0, "PAR-04": 50.0}, m={"IND-05": 40.0, "IND-08": 60.0}, obs={"SYM-19": "present"})
        at = self.run_page(**args)
        self.assertEqual(self.status(at, "Discharge restriction / low-flow operation"), "likely")
        at = self.run_page(design="radial", **args)                # N-01: radial pump with high current
        self.assertEqual(self.status(at, "Discharge restriction / low-flow operation"), "possible")

    def test_rated_and_baseline_flow(self):
        at = self.run_page(eq={"PAR-02": 100.0}, m={"IND-05": 50.0})
        self.assertEqual(self.evidence(at)["Low flow"][0], "present")
        self.assertIn("% of rated", self.evidence(at)["Low flow"][1])
        at = self.run_page(eq={"PAR-02": 100.0, "PAR-08": 60.0}, m={"IND-05": 50.0})   # baseline preferred
        self.assertEqual(self.evidence(at)["Low flow"][0], "absent")
        self.assertIn("% of baseline", self.evidence(at)["Low flow"][1])

    def test_rated_head_and_current(self):
        at = self.run_page(eq={"PAR-03": 5.0, "PAR-04": 50.0}, m={"IND-12": 4.0, "IND-07": 1.0, "IND-08": 60.0})
        ev = self.evidence(at)
        self.assertEqual(ev["Low pump head (differential pressure)"][0], "present")      # 3 bar = 60 % of rated
        self.assertEqual(ev["High motor current"][0], "present")                         # 120 % of rated

    def test_baseline_vibration_needs_site_limit(self):
        args = dict(eq={"PAR-11": 2.0}, m={"IND-01": 5.0})
        at = self.run_page(**args)
        self.assertEqual(self.evidence(at)["High overall vibration"][0], "absent")       # absolute 6.0 used
        self.assertTrue(any("baseline vibration was entered" in w.value.lower() for w in at.warning))
        at = self.run_page(limits={"THR-03": 200.0}, **args)                             # 250 % of baseline
        state, reading = self.evidence(at)["High overall vibration"]
        self.assertEqual(state, "present")
        self.assertIn("site limit entered by the user", reading)

    def test_baseline_head_and_current_with_site_limits(self):
        at = self.run_page(eq={"PAR-09": 4.0, "PAR-10": 40.0}, m={"IND-12": 3.0, "IND-07": 1.0, "IND-08": 50.0},
                           limits={"THR-14": 85.0, "THR-22": 110.0})
        ev = self.evidence(at)
        self.assertEqual(ev["Low pump head (differential pressure)"][0], "present")      # 2 bar = 50 % of baseline
        self.assertEqual(ev["High motor current"][0], "present")                         # 125 % of baseline

    def test_low_current_site_limit_enables_r_dis_2(self):
        args = dict(design="radial", eq={"PAR-02": 100.0, "PAR-04": 50.0}, m={"IND-05": 40.0, "IND-08": 20.0})
        at = self.run_page(**args)
        self.assertNotIn("possible", [self.status(at, "Discharge restriction / low-flow operation")])
        at = self.run_page(limits={"THR-23": 60.0}, **args)
        self.assertEqual(self.status(at, "Discharge restriction / low-flow operation"), "possible")
        self.assertIn("R-DIS-2", self.full_report(at))

    def test_flow_fluctuation_site_limit_enables_r_air_2(self):
        args = dict(m={"IND-09": 15.0, "IND-10": 15.0}, obs={"SYM-17": "present"})
        at = self.run_page(**args)                                  # R-AIR-2 waits for flow fluctuation
        self.assertEqual(self.status(at, "Air / gas ingress"), "pending")
        self.assertTrue(any("Flow fluctuating" in t for t in self.texts(at)))
        self.assertTrue(any("flow fluctuation was entered" in w.value.lower() for w in at.warning))
        at = self.run_page(limits={"THR-25": 10.0}, **args)
        self.assertEqual(self.status(at, "Air / gas ingress"), "possible")              # R-AIR-2 (Unvalidated)

    def test_design_liquid_temperature(self):
        at = self.run_page(eq={"PAR-12": 40.0}, m={"IND-11": 60.0, "IND-07": 0.5}, obs={"SYM-13": "present"})
        self.assertEqual(self.evidence(at)["Liquid temperature above design value"][0], "present")
        self.assertIn("Liquid temperature above design", self.full_report(at))           # cause rule R-C-01

    def test_estimated_values_make_evidence_unknown(self):
        args = dict(eq={"PAR-02": 100.0}, m={"IND-05": 3.0}, obs={"SYM-18": "present"})
        at = self.run_page(**args)
        self.assertEqual(self.status(at, "Dry running / loss of prime"), "likely")
        at = self.run_page(est=["IND-05"], **args)
        self.assertNotEqual(self.status(at, "Dry running / loss of prime"), "likely")
        state, reading = self.evidence(at)["Low flow"]
        self.assertEqual(state, "unknown")
        self.assertIn("NOT USED: input value is imputed/estimated", reading)

    def test_absent_differs_from_unknown(self):
        args = dict(eq={"PAR-02": 100.0}, m={"IND-05": 95.0})
        at = self.run_page(obs={"SYM-18": "absent"}, **args)                           # N-02 needs known absence
        self.assertEqual(self.status(at, "Dry running / loss of prime"), "blocked")
        at = self.run_page(**args)
        self.assertIsNone(self.status(at, "Dry running / loss of prime"))

    def test_test_result_confirms_and_is_reported(self):
        at = self.run_page(obs={"SYM-13": "present"}, tests={"TST-01": "NPSHA_below_NPSH3_plus_margin"})
        self.assertEqual(self.status(at, "Cavitation"), "confirmed")
        self.assertTrue(any("NPSH margin check" in t and "R-CAV-2" in t for t in self.texts(at)))
        at = self.run_page(obs={"SYM-13": "present"}, tests={"TST-01": "margin_adequate"})
        self.assertTrue(any("no rule drew a conclusion" in t for t in self.texts(at)))

    def test_root_cause_test(self):
        at = self.run_page(m={"IND-01": 7.0, "IND-02": 85.0}, tests={"TST-04": "lubricant_degraded"})
        df = next(d.value for d in at.dataframe if "cause" in d.value.columns and "status" in d.value.columns)
        self.assertIn("Inadequate or wrong lubrication", list(df["cause"]))

    def test_legacy_thresholds_checkbox(self):
        args = dict(m={"IND-12": 3.0, "IND-07": 1.0, "IND-08": 45.0})
        at = self.run_page(**args)
        self.assertNotIn("Low pump head (differential pressure)", self.evidence(at))
        at = self.run_page(legacy_thresholds=True, **args)
        self.assertEqual(self.evidence(at)["Low pump head (differential pressure)"][0], "present")
        self.assertEqual(self.evidence(at)["High motor current"][0], "present")

    def test_invalid_site_limit_blocks_diagnosis(self):
        at = self.run_page(m={"IND-01": 3.0}, limits={"THR-03": -5.0})
        self.assertIsNone(self.outcome(at))
        self.assertTrue(any("Site limit THR-03" in e.value for e in at.error))


@unittest.skipUnless(HAS_STREAMLIT, "streamlit not installed in this interpreter")
class TestTabsAndIsolation(PageCase):
    def test_all_tabs_have_content(self):
        at = self.run_page(eq=BASE_EQ, m=dict(BASE_M, **{"IND-01": 7.0, "IND-02": 85.0}), obs={"SYM-14": "present"})
        self.assertEqual([t.label for t in at.tabs], ["Diagnoses", "Root causes", "Evidence",
                                                      "Tests & information needed", "Maintenance actions",
                                                      "Full report", "Legacy comparison"])
        self.assertEqual(self.status(at, "Bearing failure"), "likely")                               # Diagnoses
        self.assertTrue(any("Candidate root causes" in t for t in self.texts(at)))                  # Root causes
        self.assertEqual(self.evidence(at)["High bearing temperature"][0], "present")               # Evidence
        maint = next(d.value for d in at.dataframe if "priority" in d.value.columns)               # Maintenance
        self.assertEqual(list(maint["priority"]), ["P2-high"])
        self.assertIn("Bearing failure", self.full_report(at))                                      # Full report
        self.assertTrue(at.get("download_button"))
        legacy = next(d.value for d in at.dataframe
                      if "legacy evidence score % (not a probability)" in d.value.columns)        # Legacy
        self.assertGreater(len(legacy), 0)
        self.assertTrue(any("How to read this report" in e.label for e in at.expander))

    def test_compare_checkbox_does_not_change_new_diagnosis(self):
        args = dict(eq=BASE_EQ, m=dict(BASE_M, **{"IND-01": 7.0, "IND-02": 85.0, "IND-03": 90.0}),
                    obs={"SYM-14": "present", "SYM-15": "present"})
        on, off = self.run_page(compare=True, **args), self.run_page(compare=False, **args)
        self.assertEqual(self.full_report(on), self.full_report(off))
        self.assertTrue(any("Legacy comparison not requested" in t for t in self.texts(off)))

    def test_legacy_failure_cannot_break_new_diagnosis(self):
        case, _, _ = ua.build_case(KB, "radial", {"PAR-02": 100.0}, {"IND-05": 50.0}, {}, {})
        with mock.patch.object(ua, "run_legacy", side_effect=RuntimeError("boom")):
            res = ua.run_legacy_isolated(case)
        self.assertEqual((res["ok"], res["error"]), (False, "RuntimeError: boom"))
        before = dict(case.measurements)
        ua.run_legacy_isolated(case)
        self.assertEqual(case.measurements, before)                     # the comparison works on a copy


@unittest.skipUnless(HAS_STREAMLIT, "streamlit not installed in this interpreter")
class TestManualScenariosThroughPage(PageCase):
    """Recorded outcomes of the 15 manual scenarios (report Table 18), reproduced through the real page."""

    def scenario(self, measure=None, present=(), primed=True):
        obs = {s: ("present" if s in present else "absent") for s in CHECKBOXES}
        obs["SYM-18"] = "absent" if primed else "present"
        return self.run_page(eq=BASE_EQ, m=dict(BASE_M, **(measure or {})), obs=obs)

    def test_t02_cavitation_pending_with_npsh_test(self):
        at = self.scenario(present={"SYM-13", "SYM-21"})
        self.assertEqual((self.outcome(at), self.status(at, "Cavitation")), ("Unknown", "pending"))
        self.assertTrue(any("NPSH margin check" in str(list(d.value["test"])) for d in at.dataframe
                            if "test" in d.value.columns))

    def test_t03_not_primed_with_normal_flow(self):
        at = self.scenario(primed=False)
        self.assertEqual((self.outcome(at), self.status(at, "Air / gas ingress")), ("Unknown", "pending"))

    def test_t03b_dry_running(self):
        at = self.scenario({"IND-05": 3.0}, primed=False)
        self.assertEqual(self.status(at, "Dry running / loss of prime"), "likely")
        maint = next(d.value for d in at.dataframe if "priority" in d.value.columns)
        self.assertEqual(maint.iloc[0]["priority"], "P1-immediate")

    def test_t04_air_bubbles_unexplained(self):
        at = self.scenario(present={"SYM-17"})
        self.assertEqual(self.outcome(at), "Unknown")
        self.assertTrue(any("Air bubbles" in t and "Air / gas ingress" in t for t in self.texts(at)))

    def test_t05_bearing(self):
        at = self.scenario({"IND-01": 7.0, "IND-02": 85.0}, present={"SYM-14"})
        self.assertEqual(self.status(at, "Bearing failure"), "likely")

    def test_t06_seal(self):
        at = self.scenario({"IND-03": 90.0}, present={"SYM-15"})
        self.assertEqual(self.status(at, "Mechanical seal failure"), "likely")

    def test_t07_low_flow_stays_open(self):
        at = self.scenario({"IND-05": 40.0})
        self.assertEqual(self.outcome(at), "Unknown")
        self.assertEqual(self.status(at, "Impeller blockage / fouling"), "pending")
        self.assertIsNone(self.status(at, "Dry running / loss of prime"))

    def test_t08_discharge_restriction(self):
        at = self.scenario({"IND-05": 40.0}, present={"SYM-19"})
        self.assertEqual(self.status(at, "Discharge restriction / low-flow operation"), "likely")
        self.assertTrue(any(e.value.startswith("SAFETY:") for e in at.error))

    def test_t09_coupling_vibration_unexplained(self):
        at = self.scenario({"IND-01": 7.0}, present={"SYM-16"})
        self.assertEqual(self.outcome(at), "Unknown")
        self.assertTrue(any("Coupling-dominant vibration" in t for t in self.texts(at)))

    def test_t10_reduced_performance(self):
        at = self.scenario({"IND-05": 60.0}, present={"SYM-21"})
        self.assertEqual((self.status(at, "Wear-ring wear"), self.status(at, "Impeller blockage / fouling")),
                         ("possible", "pending"))

    def test_t13_competing(self):
        at = self.scenario({"IND-01": 7.0, "IND-02": 85.0, "IND-03": 90.0}, present={"SYM-14", "SYM-15"})
        self.assertEqual((self.status(at, "Bearing failure"), self.status(at, "Mechanical seal failure")),
                         ("likely", "likely"))
        self.assertTrue(any("Competing diagnoses" in w.value for w in at.warning))


if __name__ == "__main__":
    unittest.main()
