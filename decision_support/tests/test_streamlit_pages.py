"""Headless UI tests for the Streamlit app (SI-1) using streamlit.testing.AppTest.

Skipped automatically when Streamlit is not installed in the running interpreter.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NEW_PAGE = str(ROOT / "src" / "pages" / "1_New_KBS_Diagnosis.py")
LEGACY_APP = str(ROOT / "src" / "app.py")
HAS_STREAMLIT = importlib.util.find_spec("streamlit") is not None
SUBMIT = "FormSubmitter:diagnosis_form-Run new KBS diagnosis"

if HAS_STREAMLIT:
    from streamlit.testing.v1 import AppTest


def metric(at, label):
    return next(m.value for m in at.metric if m.label == label)


@unittest.skipUnless(HAS_STREAMLIT, "streamlit not installed in this interpreter")
class TestNewKbsPage(unittest.TestCase):
    def load(self, example=None):
        at = AppTest.from_file(NEW_PAGE, default_timeout=60).run()
        self.assertFalse(at.exception)
        if example:
            at.selectbox(key="example_choice").set_value(example).run()
            at.sidebar.button[0].click().run()
        return at

    def submit(self, at):
        at.button(key=SUBMIT).click().run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    def test_page_loads_with_blank_unknown_inputs(self):
        at = self.load()
        self.assertIsNone(at.number_input(key="m_IND-05").value)
        self.assertEqual(at.radio(key="obs_SYM-13").value, "unknown")

    def test_empty_submission_shows_unknown(self):
        at = self.submit(self.load())
        self.assertEqual(metric(at, "Outcome"), "Unknown")
        self.assertTrue(any("can only be Unknown" in w.value for w in at.warning))

    def test_healthy_example_is_normal(self):
        at = self.submit(self.load("Healthy pump"))
        self.assertEqual(metric(at, "Outcome"), "Normal")

    def test_cavitation_example_diagnosed(self):
        at = self.submit(self.load("Cavitation"))
        self.assertEqual(metric(at, "Outcome"), "Diagnosis")
        self.assertTrue(any("Cavitation" in e.label for e in at.expander))

    def test_dry_running_example_shows_safety_and_unknown(self):
        at = self.submit(self.load("Dry running (incomplete data)"))
        self.assertEqual(metric(at, "Outcome"), "Unknown")
        self.assertTrue(any("SAFETY" in e.value for e in at.error))

    def test_competing_example(self):
        at = self.submit(self.load("Competing: cavitation vs air ingress"))
        self.assertTrue(any("Competing diagnoses" in w.value for w in at.warning))

    def test_invalid_input_rejected(self):
        at = self.load("Healthy pump")
        # inside a form, an edited value is only committed together with the submit click
        at.number_input(key="eq_PAR-02").set_value(0.0)
        at = self.submit(at)
        self.assertTrue(any("Invalid input" in e.value for e in at.error))
        self.assertFalse([m for m in at.metric if m.label == "Outcome"])


@unittest.skipUnless(HAS_STREAMLIT, "streamlit not installed in this interpreter")
class TestLegacyPagePreserved(unittest.TestCase):
    def test_legacy_app_still_diagnoses(self):
        at = AppTest.from_file(LEGACY_APP, default_timeout=60).run()
        self.assertFalse(at.exception)
        at.number_input[0].set_value(8.5)          # vibration
        at.number_input[1].set_value(90.0)         # bearing temperature
        at.checkbox[0].check()                     # grinding noise
        at.button[0].click().run()
        self.assertFalse(at.exception)
        self.assertTrue(any("Bearing" in (w.value if hasattr(w, "value") else "") for w in at.warning))


if __name__ == "__main__":
    unittest.main()
