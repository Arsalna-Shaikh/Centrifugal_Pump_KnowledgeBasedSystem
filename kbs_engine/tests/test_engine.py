"""Automated tests for the KR-2 inference engine (stdlib unittest; also runs under pytest).

Assertions check that the engine applies the knowledge base correctly.  Dataset-derived tests only
use the synthetic records to build realistic cases and to check invariants; they never treat the
synthetic labels as proof of diagnostic accuracy.
"""
from __future__ import annotations

import unittest

from kbs_engine import Case, InferenceEngine, KnowledgeBase, explain
from kbs_engine import dataset_cases as dc
from kbs_engine.engine import STATUS_ORDER

KB = KnowledgeBase()
ENGINE = InferenceEngine(KB)

RADIAL = {"pump_design": "radial", "rated_flow": 100, "rated_differential_pressure": 5.0,
          "rated_motor_current": 50, "design_liquid_temperature": 40}
HEALTHY = {"vibration_velocity": 2.0, "bearing_temperature": 55, "seal_area_temperature": 50,
           "motor_temperature": 65, "flow_rate": 95, "differential_pressure": 5.1, "suction_pressure": 1.5,
           "motor_current": 47, "pressure_fluctuation": 2, "liquid_temperature": 30}


def run(measure=None, obs=None, tests=None, equipment=None, **kw):
    m = dict(HEALTHY)
    m.update(measure or {})
    case = Case(equipment=dict(RADIAL if equipment is None else equipment), measurements=m,
                observations=obs or {}, test_results=tests or {}, imputed=kw.pop("imputed", set()),
                threshold_overrides=kw.pop("overrides", {}))
    return ENGINE.run(case, **kw)


def hyp(result, eid):
    for h in result["faults"] + result["causes"]:
        if h["id"] == eid:
            return h
    return None


def status(result, eid):
    h = hyp(result, eid)
    return h["status"] if h else "absent-from-result"


def safety_ids(result):
    return {s["safety_id"] for s in result["safety"]}


def at_least(st, minimum):
    return st in STATUS_ORDER and STATUS_ORDER.index(st) >= STATUS_ORDER.index(minimum)


# =============================================================================== knowledge loading
class TestKnowledgeLoading(unittest.TestCase):
    def test_all_rules_and_layers_loaded(self):
        self.assertEqual(len(KB.rules), 36)
        self.assertEqual({r["layer"] for r in KB.rules},
                         {"L2_fault", "L2_negative", "L3_cause", "L3_chain", "L4_test_request"})

    def test_every_rule_reference_resolves(self):
        for r in KB.rules:
            for x in r["relationship_ids"]:
                self.assertIn(x, KB.relationships, r["rule_id"])


# =============================================================================== L1 evidence
class TestEvidenceDerivation(unittest.TestCase):
    def test_rated_basis_used_when_rating_known(self):
        r = run({"flow_rate": 70})
        d = r["symptoms"]["SYM-05"]["sensor"]
        self.assertEqual(d["basis"], "pct_rated")
        self.assertEqual(r["symptoms"]["SYM-05"]["state"], "present")

    def test_baseline_preferred_over_rated(self):
        eq = dict(RADIAL, baseline_flow=80)
        r = run({"flow_rate": 70}, equipment=eq)       # 87.5 % of baseline, 70 % of rated
        d = r["symptoms"]["SYM-05"]["sensor"]
        self.assertEqual((d["basis"], d["threshold_id"]), ("pct_baseline", "THR-09"))
        self.assertEqual(r["symptoms"]["SYM-05"]["state"], "absent")

    def test_size_dependent_symptom_not_assessable_without_reference(self):
        eq = {"pump_design": "radial"}                 # no rated or baseline values
        r = run({"differential_pressure": 1.0}, equipment=eq)
        self.assertNotIn("SYM-07", r["assessable_symptoms"])
        self.assertNotIn("SYM-07", [s for s, e in r["symptoms"].items() if e["state"] == "present"])

    def test_legacy_absolute_threshold_only_when_allowed(self):
        eq = {"pump_design": "radial"}
        r = run({"differential_pressure": None, "discharge_pressure": 3.0, "suction_pressure": 1.0},
                equipment=eq, allow_non_default_thresholds=True)
        self.assertEqual(r["symptoms"]["SYM-07"]["sensor"]["threshold_id"], "THR-15")
        self.assertEqual(r["symptoms"]["SYM-07"]["state"], "present")

    def test_equipment_specific_threshold_override(self):
        r1 = run({"vibration_velocity": 5.0})
        r2 = run({"vibration_velocity": 5.0}, overrides={"THR-01": 4.0})
        self.assertEqual(r1["symptoms"]["SYM-01"]["state"], "absent")
        self.assertEqual(r2["symptoms"]["SYM-01"]["state"], "present")
        self.assertEqual(r2["symptoms"]["SYM-01"]["sensor"]["limit_origin"], "equipment-specific override")

    def test_differential_pressure_derived_from_discharge_and_suction(self):
        r = run({"differential_pressure": None, "discharge_pressure": 5.0, "suction_pressure": 1.0})
        self.assertTrue(any("IND-06" in n for n in r["notes"]))
        self.assertEqual(r["symptoms"]["SYM-07"]["sensor"]["raw_value"], 4.0)

    def test_imputed_value_gives_unknown_not_evidence(self):
        r = run({"bearing_temperature": 95}, imputed={"bearing_temperature"})
        self.assertEqual(r["symptoms"]["SYM-02"]["state"], "unknown")

    def test_no_flow_implies_low_flow(self):
        r = run({"flow_rate": None}, obs={"no_flow": "present"})
        self.assertEqual(r["symptoms"]["SYM-05"]["state"], "present")

    def test_invalid_inputs_rejected(self):
        with self.assertRaises(ValueError):
            run(obs={"seal_leakage": "yes"})
        with self.assertRaises(ValueError):
            run(tests={"TST-02": "bad_value"})


# =============================================================================== normal operation
class TestNormalOperation(unittest.TestCase):
    def test_healthy_pump_is_normal(self):
        r = run()
        self.assertEqual(r["outcome"], "OUT-N")
        self.assertFalse([h for h in r["faults"] if at_least(h["status"], "possible")])
        self.assertEqual(r["safety"], [])

    def test_missing_measurement_prevents_normal_verdict(self):
        r = run({"bearing_temperature": None})
        self.assertEqual(r["outcome"], "OUT-U")
        self.assertIn("ACT-17", [a["action_id"] for a in r["actions"]])


# =============================================================================== major faults
class TestMajorFaults(unittest.TestCase):
    def test_cavitation(self):
        r = run({"suction_pressure": 0.5, "differential_pressure": 3.9}, {"crackling_noise": "present"})
        self.assertEqual(status(r, "FLT-01"), "likely")
        self.assertEqual(r["faults"][0]["id"], "FLT-01")
        self.assertIn("R-CAV-1", hyp(r, "FLT-01")["fired_rules"])

    def test_cavitation_confirmed_by_npsh_test(self):
        r = run(tests={"TST-01": "NPSHA_below_NPSH3_plus_margin"})
        self.assertEqual(status(r, "FLT-01"), "confirmed")

    def test_bearing_failure(self):
        r = run({"vibration_velocity": 9, "bearing_temperature": 92})
        self.assertEqual(status(r, "FLT-04"), "likely")
        self.assertEqual(hyp(r, "FLT-04")["support"], "Strong")

    def test_mechanical_seal_failure(self):
        r = run(obs={"seal_leakage": "present"})
        self.assertEqual(status(r, "FLT-06"), "likely")

    def test_dry_running(self):
        r = run({"flow_rate": 3, "differential_pressure": 0.4}, {"prime_failure": "present"})
        self.assertEqual(status(r, "FLT-02"), "likely")
        self.assertIn("SAF-01", safety_ids(r))

    def test_air_ingress(self):
        r = run({"flow_rate": 65}, {"prime_failure": "present"})
        self.assertEqual(status(r, "FLT-03"), "likely")

    def test_discharge_restriction(self):
        r = run({"flow_rate": 30, "differential_pressure": 6.2, "motor_current": 35},
                {"rapid_temp_rise": "present"})
        self.assertEqual(status(r, "FLT-09"), "likely")
        self.assertIn("SAF-02", safety_ids(r))

    def test_motor_fault(self):
        r = run({"motor_current": 60, "motor_temperature": 98})
        self.assertEqual(status(r, "FLT-11"), "likely")
        self.assertEqual(hyp(r, "FLT-11")["support"], "Moderate")

    def test_impeller_damage(self):
        r = run({"vibration_velocity": 7.5}, {"performance_decline": "present"})
        self.assertEqual(status(r, "FLT-07"), "likely")

    def test_misalignment_confirmed_by_alignment_check(self):
        r = run(tests={"TST-02": "out_of_tolerance"})
        self.assertEqual(status(r, "FLT-05"), "confirmed")


# =============================================================================== root causes
class TestRootCauses(unittest.TestCase):
    CAV = {"suction_pressure": 0.5, "differential_pressure": 3.9}

    def test_temperature_cause_of_cavitation(self):
        r = run(dict(self.CAV, liquid_temperature=60), {"crackling_noise": "present"})
        self.assertEqual(status(r, "CAU-02"), "likely")

    def test_clogged_strainer_confirmed(self):
        r = run(self.CAV, {"crackling_noise": "present"}, {"TST-11": "strainer_clogged"})
        self.assertEqual(status(r, "CAU-05"), "confirmed")
        self.assertIn("ACT-11", [a["action_id"] for a in r["actions"]])

    def test_low_level_vortex_cause_of_air_ingress(self):
        r = run({"flow_rate": 65}, {"prime_failure": "present"}, {"TST-08": "low_level_or_vortex"})
        self.assertEqual(status(r, "CAU-08"), "confirmed")

    def test_lubrication_cause_of_bearing_failure(self):
        r = run({"vibration_velocity": 9, "bearing_temperature": 92}, tests={"TST-04": "lubricant_degraded"})
        self.assertEqual(status(r, "CAU-12"), "likely")

    def test_supply_imbalance_kept_as_distinct_cause(self):
        r = run({"motor_current": 60, "motor_temperature": 98}, tests={"TST-12": "phase_imbalance"})
        h = hyp(r, "CAU-39")
        self.assertEqual(h["likelihood"], "likely")      # stored rule likelihood
        self.assertEqual(h["status"], "possible")        # display cap: knowledge is unvalidated
        self.assertEqual(h["support"], "Unvalidated")

    def test_cavitation_chain_to_impeller_damage(self):
        r = run(dict(self.CAV, vibration_velocity=7.5),
                {"crackling_noise": "present", "performance_decline": "present"})
        self.assertIn("LT-01", [c["relationship"] for c in r["chains"]])

    def test_candidate_causes_listed_with_confirming_tests(self):
        r = run(self.CAV, {"crackling_noise": "present"})
        cands = {c["cause_id"]: c for c in r["candidate_causes"]["FLT-01"]}
        self.assertIn("CAU-01", cands)
        self.assertIn("TST-01", cands["CAU-01"]["confirming_tests"])


# =============================================================================== missing evidence
class TestMissingEvidence(unittest.TestCase):
    def test_unknown_never_counts_as_absent(self):
        # head low + prime failure, flow not measured -> R-AIR-1 needs no_flow ABSENT -> pending, not fired
        r = run({"flow_rate": None, "differential_pressure": 3.5}, {"prime_failure": "present"})
        self.assertNotIn("R-AIR-1", hyp(r, "FLT-03")["fired_rules"])
        self.assertIn("R-AIR-1", hyp(r, "FLT-03")["pending_rules"])
        self.assertIn("SYM-06 absent", [o["needed"] for o in r["observation_requests"]])

    def test_block_rule_requires_known_absence(self):
        r1 = run()                                   # prime_failure unknown -> FLT-02 not blocked
        self.assertNotEqual(status(r1, "FLT-02"), "blocked")
        r2 = run(obs={"prime_failure": "absent"})    # primed and flow normal -> ruled out
        self.assertEqual(status(r2, "FLT-02"), "blocked")

    def test_partial_evidence_gives_pending_and_requests(self):
        r = run(obs={"crackling_noise": "present"}, measure={"suction_pressure": None,
                                                             "differential_pressure": None})
        self.assertEqual(status(r, "FLT-01"), "pending")
        self.assertEqual(r["outcome"], "OUT-U")
        self.assertTrue(r["observation_requests"])


# =============================================================================== conflicting evidence
class TestConflictingEvidence(unittest.TestCase):
    def test_mutually_exclusive_symptoms(self):
        r = run({"differential_pressure": None}, {"head_low": "present", "head_high": "present"})
        self.assertIn("mutually_exclusive", [c["type"] for c in r["conflicts"]])
        self.assertEqual(r["symptoms"]["SYM-07"]["state"], "unknown")
        self.assertEqual(r["symptoms"]["SYM-08"]["state"], "unknown")

    def test_sensor_disagrees_with_observation(self):
        r = run({"vibration_velocity": 2.0}, {"vibration_high": "present"})
        self.assertIn("sensor_vs_observation", [c["type"] for c in r["conflicts"]])
        self.assertEqual(r["symptoms"]["SYM-01"]["state"], "unknown")

    def test_implication_violation(self):
        r = run({"flow_rate": None}, {"no_flow": "present", "flow_low": "absent"})
        self.assertIn("implication_violated", [c["type"] for c in r["conflicts"]])

    def test_negative_evidence_lowers_radial_discharge_restriction(self):
        m = {"flow_rate": 30, "motor_current": 60}
        r = run(m, {"rapid_temp_rise": "present"})
        h = hyp(r, "FLT-09")
        self.assertEqual(h["likelihood"], "likely")
        self.assertEqual(h["status"], "possible")
        self.assertIn("N-01", h["lowered_by"])
        r_axial = run(m, {"rapid_temp_rise": "present"}, equipment=dict(RADIAL, pump_design="axial"))
        self.assertEqual(status(r_axial, "FLT-09"), "likely")

    def test_competing_hypotheses_request_discriminating_tests(self):
        r = run({"suction_pressure": 0.5, "flow_rate": 65},
                {"crackling_noise": "present", "prime_failure": "present"})
        self.assertTrue(at_least(status(r, "FLT-01"), "possible"))
        self.assertTrue(at_least(status(r, "FLT-03"), "possible"))
        req = {t["test_id"] for t in r["test_requests"]}
        self.assertTrue({"TST-01", "TST-07", "TST-08"} <= req)
        self.assertIn("competing_hypotheses", [c["type"] for c in r["conflicts"]])

    def test_inconsistent_pressures_are_not_used_and_block_normal(self):
        # regression (final evaluation, defect D2): discharge below suction previously still gave 'Normal'
        r = run({"differential_pressure": None, "discharge_pressure": 1.0, "suction_pressure": 1.25})
        self.assertIn("inconsistent_measurements", [c["type"] for c in r["conflicts"]])
        self.assertEqual(r["symptoms"]["SYM-09"]["state"], "unknown")
        self.assertEqual(r["symptoms"]["SYM-07"]["state"], "unknown")
        self.assertNotEqual(r["outcome"], "OUT-N")

    def test_head_high_argues_against_cavitation(self):
        r = run({"suction_pressure": 0.5, "differential_pressure": 6.0}, {"crackling_noise": "present"})
        self.assertIn("N-03", hyp(r, "FLT-01")["lowered_by"])
        self.assertEqual(status(r, "FLT-01"), "possible")


# =============================================================================== safety
class TestSafetyOverrides(unittest.TestCase):
    def test_safety_fires_for_non_top_hypothesis(self):
        r = run({"vibration_velocity": 9, "bearing_temperature": 92, "flow_rate": 3,
                 "seal_area_temperature": 95, "differential_pressure": 0.5})
        self.assertEqual(r["faults"][0]["id"], "FLT-04")              # bearing failure ranks first
        self.assertIn(status(r, "FLT-02"), ("possible", "pending"))    # dry running is not top
        self.assertIn("SAF-01", safety_ids(r))

    def test_safety_fires_for_pending_dry_running(self):
        r = run({"flow_rate": 3, "differential_pressure": 0.5})       # prime state unknown
        self.assertEqual(status(r, "FLT-02"), "pending")
        self.assertIn("SAF-01", safety_ids(r))

    def test_no_dry_running_safety_when_ruled_out(self):
        r = run(obs={"prime_failure": "absent"})
        self.assertNotIn("SAF-01", safety_ids(r))

    def test_zero_flow_safety_not_triggered_by_low_flow_alone(self):
        r = run({"flow_rate": 65})                                     # low flow, not zero flow
        self.assertEqual(status(r, "FLT-09"), "pending")
        self.assertNotIn("SAF-02", safety_ids(r))

    def test_zero_flow_safety_triggered_by_established_zero_flow(self):
        r = run({"flow_rate": 3, "differential_pressure": 0.5})       # no_flow present
        self.assertIn("SAF-02", safety_ids(r))
        r = run({"flow_rate": 30}, {"rapid_temp_rise": "present"})    # FLT-09 likely (near shut-off)
        self.assertEqual(status(r, "FLT-09"), "likely")
        self.assertIn("SAF-02", safety_ids(r))

    def test_action_precaution(self):
        r = run({"vibration_velocity": 7.5}, {"performance_decline": "present"})
        acts = {a["action_id"]: a for a in r["actions"]}
        self.assertIn("SAF-03", acts["ACT-02"]["precautions"])
        self.assertIn("SAF-03", safety_ids(r))


# =============================================================================== support vs likelihood
class TestSupportVersusLikelihood(unittest.TestCase):
    def test_fields_are_separate(self):
        r = run({"flow_rate": 3, "differential_pressure": 0.4}, {"prime_failure": "present"})
        h = hyp(r, "FLT-02")
        self.assertEqual((h["status"], h["support"]), ("likely", "Moderate"))

    def test_unvalidated_rule_keeps_stored_likelihood(self):
        r = run({"pressure_fluctuation": 15},
                {"air_bubbles": "present", "flow_fluctuation": "present"})
        h = hyp(r, "FLT-03")
        self.assertEqual(h["support"], "Unvalidated")
        self.assertEqual(h["status"], "possible")
        ev = next(e for e in r["agenda"] if e["rule_id"] == "R-AIR-2")
        self.assertEqual(ev["likelihood"], "possible")
        self.assertEqual(ev["support"], "Unvalidated")

    def test_strong_knowledge_can_still_be_only_possible(self):
        # R-DIS-2 is Strong knowledge but only 'possible' diagnostically.  motor_current_low has no
        # sourced threshold value, so it is supplied as an observation.
        r = run({"flow_rate": 30, "motor_current": None}, {"motor_current_low": "present"})
        ev = next(e for e in r["agenda"] if e["rule_id"] == "R-DIS-2")
        self.assertEqual((ev["support"], ev["likelihood"]), ("Strong", "possible"))


# =============================================================================== forward chaining
class TestForwardChaining(unittest.TestCase):
    def test_later_layers_use_earlier_conclusions(self):
        r = run({"suction_pressure": 0.5, "differential_pressure": 3.9, "liquid_temperature": 60},
                {"crackling_noise": "present"})
        cycles = {e["rule_id"]: e["cycle"] for e in r["agenda"]}
        self.assertLess(cycles["R-CAV-1"], cycles["R-C-01"])

    def test_three_step_chain_test_to_fault_to_chain(self):
        # test -> confirmed misalignment (L2) ; bearing evidence (L2) ; chain rule (L3) needs both
        r = run({"vibration_velocity": 9, "bearing_temperature": 92}, tests={"TST-02": "out_of_tolerance"})
        layers = [e["layer"] for e in r["agenda"]]
        self.assertIn("L3_chain", layers)
        self.assertIn("LT-09", [c["relationship"] for c in r["chains"]])


# =============================================================================== explanation
class TestExplanation(unittest.TestCase):
    def test_explanation_traces_observations_rules_and_sources(self):
        r = run({"suction_pressure": 0.5, "differential_pressure": 3.9}, {"crackling_noise": "present"})
        text = explain(r, KB)
        for token in ("R-CAV-1", "THR-18", "S-01", "support Strong", "Crackling", "CAU-01"):
            self.assertIn(token, text)


# =============================================================================== dataset-derived cases
class TestDatasetDerivedCases(unittest.TestCase):
    """Synthetic records are used to build realistic inputs and to check invariants only."""

    @classmethod
    def setUpClass(cls):
        cls.rows = [r for r in dc.load_rows() if r["Diagnostic_Status"] in ("Confirmed", "No Fault Detected")]
        cls.register = dc.load_register()
        cls.sample = cls.rows[::4]                    # ~1,100 records, deterministic

    def test_invariants_over_dataset_records(self):
        for row in self.sample:
            case = dc.case_from_row(row, self.register, KB)
            r = ENGINE.run(case)
            states = {s: e["state"] for s, e in r["symptoms"].items()}
            for ev in r["agenda"]:
                rule = next(x for x in KB.rules if x["rule_id"] == ev["rule_id"])
                for s in rule["conditions"].get("symptoms_all", []):
                    self.assertEqual(states.get(s), "present", (row["Record_ID"], ev["rule_id"], s))
                for s in rule["conditions"].get("symptoms_absent", []):
                    self.assertEqual(states.get(s), "absent", (row["Record_ID"], ev["rule_id"], s))
            for h in r["faults"] + r["causes"]:
                if h["support"] == "Unvalidated":
                    self.assertFalse(at_least(h["status"], "likely"), (row["Record_ID"], h))
            if at_least(status(r, "FLT-02"), "pending"):
                self.assertIn("SAF-01", safety_ids(r), row["Record_ID"])
            for ind in case.imputed:
                for s, e in r["symptoms"].items():
                    d = e.get("sensor") or {}
                    if d.get("indicator_id") == ind and e["source"] == "sensor":
                        self.fail(f"{row['Record_ID']}: symptom {s} derived from imputed {ind}")

    def test_dataset_dry_running_record_follows_kb_logic(self):
        for row in self.rows:
            if row["Fault_Type"] == "Dry Running" and "prime_failure" in row["Symptom_Keys"] \
                    and not row["Imputed_Columns"]:
                r = ENGINE.run(dc.case_from_row(row, self.register, KB))
                if r["symptoms"].get("SYM-06", {}).get("state") == "present":
                    self.assertEqual(status(r, "FLT-02"), "likely")
                    self.assertIn("SAF-01", safety_ids(r))
                    return
        self.skipTest("no suitable record")


if __name__ == "__main__":
    unittest.main()
