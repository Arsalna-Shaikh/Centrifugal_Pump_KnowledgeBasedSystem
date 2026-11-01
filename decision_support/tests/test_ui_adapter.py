"""Tests for the SI-1 UI adapter (input validation, case building, legacy comparison mapping)."""
from __future__ import annotations

import unittest

from decision_support import ui_adapter as ua
from kbs_engine import InferenceEngine, KnowledgeBase

KB = KnowledgeBase()
ENGINE = InferenceEngine(KB)
EQ = {"PAR-02": 100.0, "PAR-03": 5.0, "PAR-04": 50.0}
HEALTHY = {"IND-01": 2.0, "IND-02": 55.0, "IND-03": 50.0, "IND-04": 65.0, "IND-05": 95.0, "IND-07": 1.5,
           "IND-12": 6.6, "IND-08": 47.0, "IND-09": 2.0}


def build(pump="radial", eq=None, meas=None, obs=None, tests=None, est=None):
    return ua.build_case(KB, pump, EQ if eq is None else eq, HEALTHY if meas is None else meas,
                         obs or {}, tests or {}, est)


class TestBuildCase(unittest.TestCase):
    def test_blank_inputs_stay_unknown(self):
        case, errors, _ = build(meas={"IND-01": None, "IND-02": "", "IND-05": 50.0}, obs={"SYM-13": "unknown"},
                                tests={"TST-01": ua.TEST_NOT_DONE})
        self.assertEqual(errors, [])
        self.assertEqual(case.measurements, {"IND-05": 50.0})
        self.assertEqual(case.observations, {})
        self.assertEqual(case.test_results, {})

    def test_pump_design_not_specified_is_omitted(self):
        case, _, _ = build(pump="not specified")
        self.assertNotIn("PAR-01", case.equipment)

    def test_invalid_inputs_reported(self):
        _, errors, _ = build(eq={"PAR-02": 0}, meas={"IND-05": -5.0, "IND-01": "abc"},
                             obs={"SYM-13": "maybe"}, tests={"TST-02": "bogus"})
        joined = " | ".join(errors)
        for frag in ("greater than zero", "outside the accepted input range", "not a number",
                     "must be one of", "invalid result"):
            self.assertIn(frag, joined)

    def test_warnings(self):
        _, _, w = build(meas=dict(HEALTHY, **{"IND-12": 1.0}))
        self.assertTrue(any("below suction" in x for x in w))
        _, _, w = build(eq={}, meas=HEALTHY)
        self.assertTrue(any("No rated or baseline reference" in x for x in w))
        _, _, w = build(meas={})
        self.assertTrue(any("can only be Unknown" in x for x in w))

    def test_estimated_values_marked(self):
        case, _, _ = build(est=["IND-02", "IND-99"])
        self.assertEqual(case.imputed, {"IND-02"})


class TestRunNewKbs(unittest.TestCase):
    def test_no_data_gives_unknown(self):
        case, _, _ = build(eq={}, meas={})
        _, rep = ua.run_new_kbs(ENGINE, case)
        self.assertEqual(rep["outcome"], "OUT-U")

    def test_healthy_gives_normal(self):
        case, _, _ = build()
        _, rep = ua.run_new_kbs(ENGINE, case)
        self.assertEqual(rep["outcome"], "OUT-N")

    def test_evidence_summary_counts_every_symptom(self):
        case, _, _ = build(meas={"IND-05": 3.0})
        _, rep = ua.run_new_kbs(ENGINE, case)
        self.assertEqual(sum(rep["evidence_summary"].values()), len(KB.symptoms))
        self.assertGreater(rep["evidence_summary"]["unknown"], 0)


class TestLegacyComparison(unittest.TestCase):
    def test_mapping(self):
        case, _, _ = build(obs={"SYM-18": "present", "SYM-15": "present", "SYM-21": "present"})
        sensor, manual, notes = ua.legacy_inputs(case)
        self.assertIs(sensor["prime_ok"], False)
        self.assertEqual(sensor["flow_percent_of_baseline"], 95.0)
        self.assertIn("seal_leakage", manual)
        self.assertIn("efficiency_low", manual)
        self.assertTrue(any("% of rated" in n for n in notes))
        case, _, _ = build()
        self.assertIsNone(ua.legacy_inputs(case)[0]["prime_ok"])

    def test_baseline_preferred_for_legacy_flow(self):
        case, _, _ = build(eq=dict(EQ, **{"PAR-08": 80.0}), meas={"IND-05": 40.0})
        self.assertEqual(ua.legacy_inputs(case)[0]["flow_percent_of_baseline"], 50.0)

    def test_legacy_engine_runs_unchanged(self):
        case, _, _ = build(meas=dict(HEALTHY, **{"IND-01": 8.5, "IND-02": 90.0}), obs={"SYM-14": "present"})
        results, evidence, _ = ua.run_legacy(case)
        self.assertIn("vibration_high", evidence)
        self.assertEqual(results[0]["fault_id"], "F01")


if __name__ == "__main__":
    unittest.main()
