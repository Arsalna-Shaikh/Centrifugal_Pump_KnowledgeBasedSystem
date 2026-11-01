"""Tests for Step 1: maintenance cost, downtime and maintenance priority (stdlib unittest; also runs under pytest).

Covers the knowledge-base attributes, their legacy provenance, the decision-support report, and that the new
attributes do not change any diagnostic result.
"""
from __future__ import annotations

import copy
import csv
import importlib.util
import json
import unittest
from pathlib import Path

from decision_support import build_report, render_text
from kbs_engine import Case, InferenceEngine, KnowledgeBase
from kbs_engine import dataset_cases as dc
from kbs_engine.knowledge import split

ROOT = Path(__file__).resolve().parents[2]
LEGACY = ROOT / "data"
KB = KnowledgeBase()
ENGINE = InferenceEngine(KB)
CLASSES = set(KB.meta["vocabularies"]["cost_downtime_class"])
PRIORITIES = list(KB.meta["vocabularies"]["maintenance_priority"])
RADIAL = {"pump_design": "radial", "rated_flow": 100, "rated_differential_pressure": 5.0,
          "rated_motor_current": 50, "design_liquid_temperature": 40}
HEALTHY = {"vibration_velocity": 2.0, "bearing_temperature": 55, "seal_area_temperature": 50,
           "motor_temperature": 65, "flow_rate": 95, "differential_pressure": 5.1, "suction_pressure": 1.5,
           "motor_current": 47, "pressure_fluctuation": 2, "liquid_temperature": 30}
SECTIONS = ("diagnoses", "also_possible", "under_investigation", "ruled_out_or_argued_against")
CAV = ({"suction_pressure": 0.5, "differential_pressure": 3.9}, {"crackling_noise": "present"})
DRY = ({"flow_rate": 3, "differential_pressure": 0.4}, {"prime_failure": "present"})
RESTRICTION = ({"flow_rate": 30, "differential_pressure": 6.2, "motor_current": 35}, {"rapid_temp_rise": "present"})


def analyse(measure=None, obs=None, engine=ENGINE, kb=KB):
    m = dict(HEALTHY)
    m.update(measure or {})
    result = engine.run(Case(equipment=dict(RADIAL), measurements=m, observations=obs or {}))
    return result, build_report(result, kb)


def find(report, fid):
    return next(h for s in SECTIONS for h in report["hypotheses"][s] if h["id"] == fid)


def action(report, aid):
    return next(a for a in report["maintenance_actions"] if a["action_id"] == aid)


def legacy(name, key):
    with open(LEGACY / name, encoding="utf-8", newline="") as f:
        return {r[key]: r for r in csv.DictReader(f)}


class TestKnowledgeBaseAttributes(unittest.TestCase):
    def test_every_action_and_fault_has_a_class_or_explicit_unknown(self):
        for table in (KB.actions, KB.faults):
            for rid, row in table.items():
                for col in ("cost_class", "downtime_class"):
                    self.assertIn(row[col], CLASSES, f"{rid} {col}")
        for fid, row in KB.faults.items():
            outcome = row["entity_type"] == "outcome"
            self.assertEqual(row["cost_class"] == "NOT_APPLICABLE", outcome, fid)

    def test_values_are_unvalidated_with_provenance(self):
        for table in (KB.actions, KB.faults):
            for rid, row in table.items():
                if row.get("entity_type") == "outcome":
                    continue
                self.assertEqual(row["cost_downtime_support_level"], "Unvalidated", rid)
                self.assertEqual(row["cost_downtime_validation_status"], "unvalidated", rid)
                self.assertTrue(split(row["cost_downtime_source_ids"]), rid)
                self.assertTrue(row["cost_downtime_source_locator"], rid)

    def test_inherited_values_equal_legacy(self):
        order = ["LOW", "MEDIUM", "HIGH"]
        for table, name, key, cc, dc_ in ((KB.actions, "maintenance_actions.csv", "action_id", "cost", "downtime"),
                                          (KB.faults, "faults.csv", "fault_id", "repair_cost", "downtime")):
            leg = legacy(name, key)
            for rid, row in table.items():
                lids = split(row["legacy_ids"])
                if not lids:
                    continue
                self.assertEqual(split(row["cost_downtime_source_ids"]), ["P-01"], rid)
                for col, lcol in (("cost_class", cc), ("downtime_class", dc_)):
                    vals = sorted({leg[x][lcol].upper() for x in lids}, key=order.index)
                    exp = vals[0] if len(vals) == 1 else f"{vals[0]}-{vals[-1]}"
                    self.assertEqual(row[col], exp, f"{rid} {col}")
                for x in lids:
                    self.assertIn(f"({x})", row["cost_downtime_source_locator"], rid)

    def test_no_value_invented_without_legacy_record(self):
        for table in (KB.actions, KB.faults):
            for rid, row in table.items():
                if not split(row["legacy_ids"]) and row.get("entity_type") != "outcome":
                    self.assertEqual((row["cost_class"], row["downtime_class"]), ("UNKNOWN", "UNKNOWN"), rid)
        self.assertEqual({a for a, r in KB.actions.items() if r["cost_class"] == "UNKNOWN"},
                         {"ACT-05", "ACT-06", "ACT-13", "ACT-17"})
        self.assertEqual(KB.faults["FLT-10"]["cost_class"], "UNKNOWN")

    def test_merged_records_show_a_range(self):
        self.assertEqual(KB.actions["ACT-02"]["cost_class"], "MEDIUM-HIGH")      # A04 MEDIUM + A12 HIGH
        self.assertEqual(KB.actions["ACT-07"]["downtime_class"], "LOW-MEDIUM")   # A01 LOW + A02 MEDIUM
        self.assertEqual(KB.faults["FLT-11"]["cost_class"], "MEDIUM")            # F08 and F14 agree

    def test_no_numeric_values(self):
        for table in (KB.actions, KB.faults):
            for row in table.values():
                for col in ("cost_class", "downtime_class"):
                    self.assertFalse(any(ch.isdigit() for ch in row[col]))

    def test_hazard_class_unchanged(self):
        self.assertEqual({f: r["hazard_class"] for f, r in KB.faults.items()},
                         {"FLT-01": "HIGH", "FLT-02": "CRITICAL", "FLT-03": "HIGH", "FLT-04": "HIGH",
                          "FLT-05": "HIGH", "FLT-06": "HIGH", "FLT-07": "HIGH", "FLT-08": "MEDIUM",
                          "FLT-09": "HIGH", "FLT-10": "UNASSIGNED", "FLT-11": "HIGH", "FLT-12": "HIGH",
                          "OUT-N": "NONE", "OUT-U": "NONE"})

    def test_priority_policy_declared_unvalidated(self):
        pol = KB.meta["policies"]["maintenance_priority"]
        self.assertEqual(pol["support_level"], "Unvalidated")
        self.assertEqual(PRIORITIES, ["P1-immediate", "P2-high", "P3-planned"])


class TestReport(unittest.TestCase):
    def test_cavitation_attributes_kept_separate(self):
        _, rep = analyse(*CAV)
        h = find(rep, "FLT-01")
        self.assertEqual(h["diagnostic_status"], "likely")
        self.assertEqual(h["knowledge_support"], "Strong")
        self.assertEqual(h["hazard"]["class"], "HIGH")
        mi = h["maintenance_impact"]
        self.assertEqual((mi["cost_class"], mi["downtime_class"]), ("LOW", "MEDIUM"))
        self.assertEqual(mi["knowledge_support"], "Unvalidated")
        self.assertEqual(mi["sources"], ["P-01"])
        a = action(rep, "ACT-01")
        self.assertEqual(a["maintenance_priority"]["level"], "P2-high")
        self.assertEqual(a["maintenance_priority"]["knowledge_support"], "Unvalidated")
        self.assertEqual((a["cost_downtime"]["cost_class"], a["cost_downtime"]["downtime_class"]), ("LOW", "MEDIUM"))
        self.assertEqual(a["cost_downtime"]["knowledge_support"], "Unvalidated")

    def test_make_safe_action_is_immediate_and_first(self):
        _, rep = analyse(*DRY)
        self.assertEqual(rep["maintenance_actions"][0]["action_id"], "ACT-03")
        self.assertEqual(action(rep, "ACT-03")["maintenance_priority"]["level"], "P1-immediate")

    def test_safety_warning_makes_action_immediate(self):
        _, rep = analyse(*RESTRICTION)
        self.assertIn("SAF-02", [w["safety_id"] for w in rep["safety_warnings"]])
        self.assertEqual(action(rep, "ACT-12")["purpose"], "correct")
        self.assertEqual(action(rep, "ACT-12")["maintenance_priority"]["level"], "P1-immediate")

    def test_unknown_outcome_investigation(self):
        _, rep = analyse({"flow_rate": 65})
        a = action(rep, "ACT-17")
        self.assertEqual(a["maintenance_priority"]["level"], "P3-planned")
        self.assertEqual(a["cost_downtime"]["cost_class"], "UNKNOWN")

    def test_rendered_text_labels_unvalidated(self):
        _, rep = analyse(*CAV)
        text = render_text(rep)
        self.assertIn("Repair cost/downtime: LOW / MEDIUM (qualitative; support Unvalidated)", text)
        self.assertIn("[P2-high] Restore NPSH", text)
        self.assertIn("maintenance priority - a project policy, Unvalidated", text)
        self.assertTrue(any("Cost and downtime" in x for x in rep["limitations"]))

    def test_priority_follows_policy_on_dataset_cases(self):
        """Priority uses only warnings, purpose and status; actions are sorted by it and none are dropped."""
        reg = dc.load_register()
        for row in dc.load_rows()[::10]:
            res = ENGINE.run(dc.case_from_row(row, reg, KB))
            rep = build_report(res, KB)
            self.assertEqual(sorted(a["action_id"] for a in rep["maintenance_actions"]),
                             sorted(a["action_id"] for a in res["actions"]))
            levels = [PRIORITIES.index(a["maintenance_priority"]["level"]) for a in rep["maintenance_actions"]]
            self.assertEqual(levels, sorted(levels))
            status = {h["id"]: h["status"] for h in res["faults"] + res["causes"]}
            warned = {f for w in rep["safety_warnings"] for f in split(KB.safety[w["safety_id"]]["trigger_fault_ids"])}
            for a in rep["maintenance_actions"]:
                ids = {x["id"] for x in a["for"]}
                exp = ("P1-immediate" if a["purpose"] == "make_safe" or ids & warned else
                       "P2-high" if any(status.get(i) in ("confirmed", "likely") for i in ids) else "P3-planned")
                self.assertEqual(a["maintenance_priority"]["level"], exp, a["action_id"])
            for s in SECTIONS:
                for h in rep["hypotheses"][s]:
                    self.assertEqual(h["diagnostic_status"], status[h["id"]])


class TestDiagnosisUnaffected(unittest.TestCase):
    def test_changing_cost_downtime_does_not_change_engine_result(self):
        altered = copy.deepcopy(KB)
        for table in (altered.actions, altered.faults):
            for row in table.values():
                row["cost_class"] = row["downtime_class"] = "HIGH"
        eng2 = InferenceEngine(altered)
        for case in ({}, CAV, DRY, RESTRICTION, ({"vibration_velocity": 9, "bearing_temperature": 92}, {})):
            m = dict(HEALTHY)
            m.update(case[0] if case else {})
            obs = case[1] if case else {}
            r1 = ENGINE.run(Case(equipment=dict(RADIAL), measurements=m, observations=obs))
            r2 = eng2.run(Case(equipment=dict(RADIAL), measurements=m, observations=obs))
            self.assertEqual(json.dumps(r1, sort_keys=True, default=str), json.dumps(r2, sort_keys=True, default=str))


HAS_STREAMLIT = importlib.util.find_spec("streamlit") is not None
if HAS_STREAMLIT:
    from streamlit.testing.v1 import AppTest


@unittest.skipUnless(HAS_STREAMLIT, "streamlit not installed in this interpreter")
class TestStreamlitPage(unittest.TestCase):
    def test_cavitation_shows_cost_downtime_and_priority(self):
        at = AppTest.from_file(str(ROOT / "src" / "pages" / "1_New_KBS_Diagnosis.py"), default_timeout=60).run()
        at.selectbox(key="example_choice").set_value("Cavitation").run()
        at.sidebar.button[0].click().run()
        at.button(key="FormSubmitter:diagnosis_form-Run new KBS diagnosis").click().run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        self.assertTrue(any("Repair cost / downtime:** LOW / MEDIUM" in m.value for m in at.markdown))
        df = next(d.value for d in at.dataframe if "priority" in d.value.columns)
        self.assertTrue({"priority", "cost", "downtime"} <= set(df.columns))
        row = df[df["action"] == "Restore NPSH"].iloc[0]
        self.assertEqual((row["priority"], row["cost"], row["downtime"]), ("P2-high", "LOW", "MEDIUM"))


if __name__ == "__main__":
    unittest.main()
