"""Tests for the DS-1 decision-support report (stdlib unittest; also runs under pytest)."""
from __future__ import annotations

import unittest

from decision_support import build_report, render_text
from kbs_engine import Case, InferenceEngine, KnowledgeBase
from kbs_engine import dataset_cases as dc

KB = KnowledgeBase()
ENGINE = InferenceEngine(KB)
RADIAL = {"pump_design": "radial", "rated_flow": 100, "rated_differential_pressure": 5.0,
          "rated_motor_current": 50, "design_liquid_temperature": 40}
HEALTHY = {"vibration_velocity": 2.0, "bearing_temperature": 55, "seal_area_temperature": 50,
           "motor_temperature": 65, "flow_rate": 95, "differential_pressure": 5.1, "suction_pressure": 1.5,
           "motor_current": 47, "pressure_fluctuation": 2, "liquid_temperature": 30}
SECTIONS = ("diagnoses", "also_possible", "under_investigation", "ruled_out_or_argued_against")


def analyse(measure=None, obs=None, tests=None, equipment=None):
    m = dict(HEALTHY)
    m.update(measure or {})
    result = ENGINE.run(Case(equipment=dict(equipment or RADIAL), measurements=m, observations=obs or {},
                             test_results=tests or {}))
    return result, build_report(result, KB)


def all_hyps(report):
    return [h for s in SECTIONS for h in report["hypotheses"][s]]


def find(report, fid):
    for s in SECTIONS:
        for h in report["hypotheses"][s]:
            if h["id"] == fid:
                return s, h
    return None, None


CAV = ({"suction_pressure": 0.5, "differential_pressure": 3.9}, {"crackling_noise": "present"})


class TestNormal(unittest.TestCase):
    def test_normal_report(self):
        _, rep = analyse()
        self.assertEqual(rep["outcome"], "OUT-N")
        self.assertTrue(rep["headline"].startswith("No fault indicated"))
        self.assertEqual(rep["hypotheses"]["diagnoses"], [])
        self.assertEqual(rep["safety_warnings"], [])
        self.assertEqual(rep["maintenance_actions"], [])
        self.assertEqual(rep["evidence_summary"]["present"], 0)


class TestMajorFaults(unittest.TestCase):
    def test_cavitation_report_contents(self):
        res, rep = analyse(*CAV)
        top = rep["hypotheses"]["diagnoses"][0]
        self.assertEqual((top["id"], top["rank"]), ("FLT-01", 1))
        self.assertEqual(top["diagnostic_status"], "likely")
        self.assertEqual(top["knowledge_support"], "Strong")
        ev = {e["symptom_id"]: e for e in top["supporting_evidence"]}
        self.assertIn("SYM-13", ev)
        self.assertIn("THR-18", ev["SYM-09"]["reading"])
        ex = top["explanation"][0]
        self.assertEqual(ex["rule_id"], "R-CAV-1")
        self.assertIn("S-01", [s["id"] for s in ex["sources"]])
        self.assertIn("ACT-01", [a["action_id"] for a in rep["maintenance_actions"]])
        self.assertIn("CAU-01", [c["cause_id"] for c in rep["candidate_root_causes"]])

    def test_bearing_failure(self):
        _, rep = analyse({"vibration_velocity": 9, "bearing_temperature": 92})
        self.assertEqual(rep["hypotheses"]["diagnoses"][0]["id"], "FLT-04")
        self.assertIn("ACT-07", [a["action_id"] for a in rep["maintenance_actions"]])

    def test_dry_running_severity_and_safety(self):
        _, rep = analyse({"flow_rate": 3, "differential_pressure": 0.4}, {"prime_failure": "present"})
        _, h = find(rep, "FLT-02")
        self.assertEqual(h["hazard"]["class"], "CRITICAL")
        self.assertIsNone(h["case_severity"])
        self.assertIn("SAF-01", [w["safety_id"] for w in rep["safety_warnings"]])
        self.assertIn("FLT-02", [c["id"] for c in rep["critical_hazard_hypotheses"]])
        self.assertTrue(rep["headline"].startswith("SAFETY WARNING"))

    def test_root_cause_with_unvalidated_knowledge(self):
        _, rep = analyse({"motor_current": 60, "motor_temperature": 98}, tests={"TST-12": "phase_imbalance"})
        cause = next(c for c in rep["root_causes"] if c["id"] == "CAU-39")
        self.assertEqual(cause["diagnostic_status"], "possible")
        self.assertEqual(cause["knowledge_support"], "Unvalidated")
        self.assertTrue(cause["explanation"][0]["capped_because_unvalidated"])

    def test_confirmed_by_test(self):
        _, rep = analyse(tests={"TST-02": "out_of_tolerance"})
        top = rep["hypotheses"]["diagnoses"][0]
        self.assertEqual((top["id"], top["diagnostic_status"]), ("FLT-05", "confirmed"))
        self.assertIn("TST-02", [e.get("test_id") for e in top["supporting_evidence"]])


class TestCompetingFaults(unittest.TestCase):
    def test_competing_diagnoses_preserved_with_discriminating_tests(self):
        _, rep = analyse({"suction_pressure": 0.5, "flow_rate": 65},
                         {"crackling_noise": "present", "prime_failure": "present"})
        ids = {h["id"] for h in rep["hypotheses"]["diagnoses"]}
        self.assertTrue({"FLT-01", "FLT-03"} <= ids)
        self.assertTrue(rep["competing_diagnoses"])
        first = rep["recommended_tests"][:3]
        self.assertTrue(all(t["kind"] == "discriminating" for t in first))
        self.assertEqual({t["test_id"] for t in first}, {"TST-01", "TST-07", "TST-08"})

    def test_contradicting_evidence_shown(self):
        _, rep = analyse({"flow_rate": 30, "motor_current": 60}, {"rapid_temp_rise": "present"})
        section, h = find(rep, "FLT-09")
        self.assertEqual(section, "also_possible")
        c = h["contradicting_evidence"][0]
        self.assertEqual((c["rule_id"], c["effect"]), ("N-01", "lowered"))
        self.assertIn("SYM-10", [e["symptom_id"] for e in c["evidence"]])
        self.assertEqual(h["rule_likelihood_before_adjustment"], "likely")

    def test_ruled_out_hypothesis_kept_visible(self):
        _, rep = analyse(obs={"prime_failure": "absent"})
        section, h = find(rep, "FLT-02")
        self.assertEqual(section, "ruled_out_or_argued_against")
        self.assertEqual(h["contradicting_evidence"][0]["effect"], "ruled out")


class TestMissingEvidence(unittest.TestCase):
    def test_unknown_preserved_and_information_requested(self):
        res, rep = analyse({"suction_pressure": None, "differential_pressure": None}, {"crackling_noise": "present"})
        self.assertEqual(rep["outcome"], "OUT-U")
        section, h = find(rep, "FLT-01")
        self.assertEqual(section, "under_investigation")
        self.assertTrue(h["missing_evidence"])
        self.assertTrue(rep["information_needed"])
        for o in rep["information_needed"]:                     # readable names, IDs kept in brackets
            self.assertRegex(o["needed"], r"[A-Za-z].*\((SYM|PAR|TST)-\d{2}\)")
        self.assertIn("ACT-17", [a["action_id"] for a in rep["maintenance_actions"]])
        self.assertGreater(rep["evidence_summary"]["unknown"], 0)

    def test_missing_measurement_blocks_normal_verdict(self):
        _, rep = analyse({"bearing_temperature": None})
        self.assertEqual(rep["outcome"], "OUT-U")
        self.assertNotIn("No fault indicated", rep["headline"])


class TestUncertaintyExplanation(unittest.TestCase):
    """Regression (final evaluation, defect D5): present evidence must never silently disappear."""

    def test_pending_hypothesis_shows_partial_evidence(self):
        _, rep = analyse({"suction_pressure": None, "differential_pressure": None}, {"crackling_noise": "present"})
        _, h = find(rep, "FLT-01")
        ev = {e["symptom_id"]: e for e in h["supporting_evidence"]}
        self.assertTrue(ev["SYM-13"]["partial"])
        self.assertEqual(ev["SYM-13"]["for_rule"], "R-CAV-1")

    def test_unexplained_evidence_listed_with_kb_links_not_diagnoses(self):
        _, rep = analyse(obs={"air_bubbles": "present", "prime_failure": "absent"})
        self.assertEqual(rep["outcome"], "OUT-U")
        self.assertFalse(rep["hypotheses"]["diagnoses"])
        u = next(x for x in rep["unexplained_evidence"] if x["symptom_id"] == "SYM-17")
        link = next(x for x in u["linked_to"] if x["id"] == "FLT-03")
        self.assertEqual(link["knowledge_support"], "Unvalidated")
        self.assertIn("EVIDENCE NOT EXPLAINED BY ANY RULE", render_text(rep))

    def test_explained_evidence_not_repeated_as_unexplained(self):
        _, rep = analyse({"vibration_velocity": 9, "bearing_temperature": 92})
        self.assertNotIn("SYM-01", [u["symptom_id"] for u in rep["unexplained_evidence"]])


class TestSafetyWarnings(unittest.TestCase):
    def test_warning_for_non_top_hypothesis(self):
        _, rep = analyse({"vibration_velocity": 9, "bearing_temperature": 92, "flow_rate": 3,
                          "seal_area_temperature": 95, "differential_pressure": 0.5})
        self.assertEqual(rep["hypotheses"]["diagnoses"][0]["id"], "FLT-04")
        self.assertIn("SAF-01", [w["safety_id"] for w in rep["safety_warnings"]])

    def test_warning_for_pending_dry_running(self):
        _, rep = analyse({"flow_rate": 3, "differential_pressure": 0.5})
        self.assertEqual(rep["hypotheses"]["diagnoses"], [])
        ids = [w["safety_id"] for w in rep["safety_warnings"]]
        self.assertIn("SAF-01", ids)
        self.assertIn("SAF-02", ids)

    def test_work_precaution_separate_from_operating_warning(self):
        _, rep = analyse({"vibration_velocity": 7.5}, {"performance_decline": "present"})
        self.assertIn("SAF-03", [w["safety_id"] for w in rep["work_precautions"]])
        self.assertNotIn("SAF-03", [w["safety_id"] for w in rep["safety_warnings"]])
        act = next(a for a in rep["maintenance_actions"] if a["action_id"] == "ACT-02")
        self.assertIn("SAF-03", [p["safety_id"] for p in act["precautions"]])

    def test_no_zero_flow_warning_for_low_flow_only(self):
        _, rep = analyse({"flow_rate": 65})
        self.assertNotIn("SAF-02", [w["safety_id"] for w in rep["safety_warnings"]])


class TestNoInventionAndRendering(unittest.TestCase):
    CASES = [({}, {}, {}), CAV + ({},), ({"flow_rate": 3, "differential_pressure": 0.4}, {"prime_failure": "present"}, {}),
             ({"suction_pressure": 0.5, "flow_rate": 65}, {"crackling_noise": "present", "prime_failure": "present"}, {}),
             ({"motor_current": 60, "motor_temperature": 98}, {}, {"TST-12": "phase_imbalance"}),
             ({"flow_rate": 30, "motor_current": 60}, {"rapid_temp_rise": "present"}, {})]

    def test_everything_traces_to_engine_or_kb(self):
        for m, o, t in self.CASES:
            res, rep = analyse(m, o, t)
            self.assertEqual({a["action_id"] for a in rep["maintenance_actions"]},
                             {a["action_id"] for a in res["actions"]})
            self.assertEqual({x["test_id"] for x in rep["recommended_tests"]},
                             {x["test_id"] for x in res["test_requests"]})
            self.assertEqual({w["safety_id"] for w in rep["safety_warnings"] + rep["work_precautions"]},
                             {s["safety_id"] for s in res["safety"]})
            for h in all_hyps(rep):
                self.assertIsNone(h["case_severity"])
                self.assertEqual(h["hazard"]["class"], KB.faults[h["id"]]["hazard_class"])
            # every engine hypothesis (incl. unknown/pending/ruled-out) is preserved
            self.assertEqual(sorted(h["id"] for h in all_hyps(rep)), sorted(h["id"] for h in res["faults"]))

    def test_text_rendering(self):
        _, rep = analyse({"suction_pressure": 0.5, "flow_rate": 65},
                         {"crackling_noise": "present", "prime_failure": "present"})
        text = render_text(rep)
        for token in ("DIAGNOSES", "Diagnostic status", "Knowledge support", "COMPETING DIAGNOSES",
                      "RECOMMENDED DIAGNOSTIC TESTS", "MAINTENANCE ACTIONS", "LIMITATIONS", "R-CAV-1"):
            self.assertIn(token, text)

    def test_dataset_cases_build_valid_reports(self):
        rows = [r for r in dc.load_rows() if r["Diagnostic_Status"] in ("Confirmed", "No Fault Detected")][::4]
        reg = dc.load_register()
        for row in rows:
            res = ENGINE.run(dc.case_from_row(row, reg, KB))
            rep = build_report(res, KB)
            self.assertEqual(len(all_hyps(rep)), len(res["faults"]), row["Record_ID"])
            render_text(rep)


if __name__ == "__main__":
    unittest.main()
