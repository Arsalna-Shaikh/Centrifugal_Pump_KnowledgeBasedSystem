"""SI-1 adapter between the Streamlit page and the new KBS (no Streamlit import - unit-testable).

- Declares the input fields offered in the UI (taken from knowledge_base/ IDs).
- Validates raw inputs and builds a kbs_engine Case (blank = unknown, never a default value).
- Maps the same inputs onto the legacy engine (src/inference_engine.py) for side-by-side comparison.
"""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

from kbs_engine import Case, InferenceEngine, KnowledgeBase

from .report import build_report

ROOT = Path(__file__).resolve().parents[1]
LEGACY_ENGINE = ROOT / "src" / "inference_engine.py"

# (parameter id, label) - equipment parameters offered in the UI.  Only parameters that a threshold or rule
# uses are offered (rated speed PAR-05, Qmin PAR-06 and NPSH3 PAR-07 are used by no rule or threshold).
EQUIPMENT_FIELDS = [
    ("PAR-02", "Rated flow (m³/h)"), ("PAR-03", "Rated differential pressure (bar)"),
    ("PAR-04", "Rated motor current (A)"), ("PAR-08", "Healthy-baseline flow (m³/h)"),
    ("PAR-09", "Healthy-baseline differential pressure (bar)"), ("PAR-10", "Healthy-baseline motor current (A)"),
    ("PAR-11", "Healthy-baseline vibration (mm/s RMS)"), ("PAR-12", "Design liquid temperature (°C)"),
]
PUMP_DESIGNS = ["not specified", "radial", "mixed", "axial"]

# (indicator id, label, input sanity range) - ranges only reject impossible INPUT values (e.g. negative
# flow); they are not engineering thresholds and play no part in diagnosis.
MEASUREMENT_FIELDS = [
    ("IND-01", "Vibration (mm/s RMS)", 0.0, 100.0), ("IND-02", "Bearing temperature (°C)", -50.0, 300.0),
    ("IND-03", "Seal-area temperature (°C)", -50.0, 300.0), ("IND-04", "Motor temperature (°C)", -50.0, 300.0),
    ("IND-05", "Flow (m³/h)", 0.0, 100000.0), ("IND-07", "Suction pressure (bar abs)", 0.0, 100.0),
    ("IND-12", "Discharge pressure (bar abs)", 0.0, 500.0), ("IND-08", "Motor current (A)", 0.0, 10000.0),
    ("IND-09", "Pressure fluctuation (% of mean)", 0.0, 100.0), ("IND-10", "Flow fluctuation (% of mean)", 0.0, 100.0),
    ("IND-11", "Liquid temperature (°C)", -50.0, 400.0),
]
OBSERVATION_STATES = ["unknown", "present", "absent"]
TEST_NOT_DONE = "not done"


def observed_symptoms(kb: KnowledgeBase) -> list[tuple[str, str]]:
    """Symptoms a person reports (observed/trend kinds) - offered as present/absent/unknown."""
    return [(sid, s["name"]) for sid, s in kb.symptoms.items() if s["kind"] in ("observed", "trend")]


def rule_test_uses(kb: KnowledgeBase) -> dict[str, list[tuple[str, str]]]:
    """test id -> [(result value, rule id)] for every rule condition that interprets a test result."""
    uses = {}
    for r in kb.rules:
        for t in r["conditions"].get("tests", []):
            uses.setdefault(t["test_id"], []).append((t["result"], r["rule_id"]))
    return uses


def test_options(kb: KnowledgeBase) -> dict[str, list[str]]:
    """Result choices for the tests that at least one rule interprets (other results would have no effect)."""
    uses = rule_test_uses(kb)
    return {tid: [TEST_NOT_DONE] + [v for v in t["result_values"].split(";") if v]
            for tid, t in kb.tests.items() if tid in uses}


def site_limits(kb: KnowledgeBase) -> list[dict]:
    """Default thresholds that have no sourced value in the knowledge base.  The engine skips them unless an
    equipment-specific value (threshold override) is supplied, so the UI offers them as optional site limits."""
    return [t for t in kb.thresholds.values()
            if t["default_for_basis"] == "yes" and not t["value"] and not t["value_parameter_id"]]


# ------------------------------------------------------------------ help texts (generated from the knowledge base)
_OP = {"<": "below", "<=": "at or below", ">": "above", ">=": "at or above"}


def _threshold_text(kb: KnowledgeBase, t: dict) -> str:
    sym = kb.name(t["symptom_id"])
    if t["value_parameter_id"]:
        return f"{sym}: {_OP[t['operator']]} the {kb.parameters[t['value_parameter_id']]['name'].replace('_', ' ')}"
    if not t["value"]:
        return f"{sym}: only with a site limit (no sourced value in the knowledge base)"
    unit = {"pct_rated": "% of rated", "pct_baseline": "% of baseline"}.get(t["basis"], t["unit"])
    return f"{sym}: {_OP[t['operator']]} {t['value']} {unit} ({t['support_level'].lower()} limit)"


def measurement_help(kb: KnowledgeBase, iid: str) -> str:
    ths = [t for t in kb.thresholds.values() if t["indicator_id"] == iid and t["default_for_basis"] == "yes"]
    if iid in ("IND-07", "IND-12"):
        ths += [t for t in kb.thresholds.values() if t["indicator_id"] == "IND-06" and t["default_for_basis"] == "yes"]
    lines = [_threshold_text(kb, t) for t in ths]
    if iid in ("IND-07", "IND-12"):
        lines.insert(0, "Pump head = discharge minus suction pressure; both are needed for the head symptoms")
    lo, hi = next((lo, hi) for i, _, lo, hi in MEASUREMENT_FIELDS if i == iid)
    return "Used for: " + "; ".join(lines) + f". Accepted input range {lo:g} to {hi:g}."


def parameter_help(kb: KnowledgeBase, pid: str) -> str:
    p = kb.parameters[pid]
    role = {"rated_reference": "Rated value from the pump data sheet.",
            "baseline_reference": "Value measured when this pump was known to be healthy.",
            "limit": "Design value from the data sheet."}.get(p["role"], "")
    used = []
    for t in kb.thresholds.values():
        ind = kb.indicators[t["indicator_id"]]
        ref = {"pct_rated": ind["rated_parameter_id"], "pct_baseline": ind["baseline_parameter_id"]}.get(t["basis"])
        if t["default_for_basis"] == "yes" and pid in (ref, t["value_parameter_id"]):
            used.append(_threshold_text(kb, t))
    return f"{role} Used for: " + "; ".join(used) + ". Leave blank if not known."


def legacy_threshold_help(kb: KnowledgeBase) -> str:
    """The non-default (legacy absolute) limits that can actually take effect: only for symptoms that have no
    default absolute threshold, and only when no rated/baseline reference is available."""
    has_abs = {t["symptom_id"] for t in kb.thresholds.values()
               if t["default_for_basis"] == "yes" and t["basis"] == "absolute" and t["value"]}
    usable = [t for t in kb.thresholds.values()
              if t["default_for_basis"] == "no" and t["value"] and t["symptom_id"] not in has_abs]
    return ("Uses the legacy prototype's absolute limits when no rated or baseline value is given: "
            + "; ".join(f"{_threshold_text(kb, t)} [{t['threshold_id']} on {kb.indicators[t['indicator_id']]['name']}]"
                        for t in usable)
            + ". They were set for one prototype pump and are Unvalidated.")


def test_help(kb: KnowledgeBase, tid: str) -> str:
    uses = rule_test_uses(kb).get(tid, [])
    return (f"Measures: {kb.tests[tid]['measures']}. Interpreted by: "
            + "; ".join(f"'{res}' -> rule {rid}" for res, rid in uses)
            + ". Other results are recorded but no rule draws a conclusion from them.")


def test_usage(kb: KnowledgeBase, case: Case, result: dict) -> list[dict]:
    """For each entered test result, the fired rules that used it (empty list = no rule drew a conclusion)."""
    fired = {ev["rule_id"] for ev in result["agenda"]}
    rules = {r["rule_id"]: r for r in kb.rules}
    out = []
    for tid, res in case.test_results.items():
        used = sorted(rid for rid in fired
                      if any(t["test_id"] == tid and t["result"] == res for t in rules[rid]["conditions"].get("tests", [])))
        out.append({"test_id": tid, "test": kb.tests[tid]["name"], "result": res, "used_by": used})
    return out


def _num(value, label, errors):
    if value is None or value == "":
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        errors.append(f"{label}: '{value}' is not a number")
        return None
    if x != x or x in (float("inf"), float("-inf")):
        errors.append(f"{label}: not a finite number")
        return None
    return x


def build_case(kb: KnowledgeBase, pump_design: str, equipment: dict, measurements: dict, observations: dict,
               tests: dict, estimated: list | None = None, limits: dict | None = None):
    """Validate UI inputs and build a Case.  Returns (case, errors, warnings).  Blank inputs stay unknown.
    limits: optional site-specific values for thresholds that have no sourced value (see site_limits)."""
    errors, warnings = [], []
    eq = {}
    if pump_design and pump_design != "not specified":
        if pump_design not in PUMP_DESIGNS:
            errors.append(f"Pump design '{pump_design}' is not one of {PUMP_DESIGNS[1:]}")
        else:
            eq["PAR-01"] = pump_design
    labels = dict(EQUIPMENT_FIELDS)
    for pid, raw in equipment.items():
        x = _num(raw, labels.get(pid, pid), errors)
        if x is None:
            continue
        if x <= 0 and pid != "PAR-12":
            errors.append(f"{labels.get(pid, pid)} must be greater than zero")
            continue
        eq[pid] = x
    meas = {}
    mlabels = {i: (lab, lo, hi) for i, lab, lo, hi in MEASUREMENT_FIELDS}
    for iid, raw in measurements.items():
        lab, lo, hi = mlabels.get(iid, (iid, float("-inf"), float("inf")))
        x = _num(raw, lab, errors)
        if x is None:
            continue
        if not lo <= x <= hi:
            errors.append(f"{lab}: {x} is outside the accepted input range {lo}-{hi}")
            continue
        meas[iid] = x
    if "IND-07" in meas and "IND-12" in meas and meas["IND-12"] < meas["IND-07"]:
        warnings.append("Discharge pressure is below suction pressure - check the readings "
                        "(both are treated as unknown, so a Normal verdict is not possible).")
    obs = {}
    for sid, state in observations.items():
        if state not in OBSERVATION_STATES:
            errors.append(f"Observation {sid}: '{state}' must be one of {OBSERVATION_STATES}")
        elif state != "unknown":
            obs[sid] = state
    tres = {}
    for tid, res in tests.items():
        if res and res != TEST_NOT_DONE:
            if tid not in kb.tests or res not in kb.tests[tid]["result_values"].split(";"):
                errors.append(f"Test {tid}: invalid result '{res}'")
            else:
                tres[tid] = res
    imputed = {i for i in (estimated or []) if i in meas}
    overrides = {}
    open_limits = {t["threshold_id"]: t for t in site_limits(kb)}
    for tid, raw in (limits or {}).items():
        if tid not in open_limits:
            errors.append(f"Site limit {tid}: not an open threshold in the knowledge base")
            continue
        x = _num(raw, f"Site limit {tid}", errors)
        if x is None:
            continue
        if x <= 0:
            errors.append(f"Site limit {tid} ({kb.name(open_limits[tid]['symptom_id'])}) must be greater than zero")
            continue
        overrides[tid] = x
    for tid, t in open_limits.items():
        ind = kb.indicators[t["indicator_id"]]
        ref = {"pct_rated": ind["rated_parameter_id"], "pct_baseline": ind["baseline_parameter_id"]}.get(t["basis"])
        if tid not in overrides and ((ref and ref in eq and t["basis"] == "pct_baseline") or
                                     (not ref and t["indicator_id"] in meas)):
            given = kb.parameters[ref]["name"] if ref else kb.indicators[t["indicator_id"]]["name"]
            warnings.append(f"{given.replace('_', ' ').capitalize()} was entered, but '{kb.name(t['symptom_id'])}' "
                            "has no sourced limit in the knowledge base; enter a site limit (section 5) or this "
                            "value is not used.")
    if not meas and not obs and not tres:
        warnings.append("No measurements, observations or test results entered - the result can only be Unknown.")
    for pid_needed, iid, what in (("PAR-02", "IND-05", "flow"), ("PAR-03", "IND-12", "pump head"),
                                  ("PAR-04", "IND-08", "motor current")):
        base = {"PAR-02": "PAR-08", "PAR-03": "PAR-09", "PAR-04": "PAR-10"}[pid_needed]
        if iid in meas and pid_needed not in eq and base not in eq:
            warnings.append(f"No rated or baseline reference for {what}: related symptoms cannot be assessed "
                            "and will stay unknown.")
    case = Case(equipment=eq, measurements=meas, observations=obs, test_results=tres, imputed=imputed,
                threshold_overrides=overrides)
    return case, errors, warnings


def run_new_kbs(engine: InferenceEngine, case: Case, allow_legacy_thresholds: bool = False):
    result = engine.run(case, allow_non_default_thresholds=allow_legacy_thresholds)
    return result, build_report(result, engine.kb)


# ------------------------------------------------------------------ legacy engine (comparison only)
_legacy = None


def legacy_module():
    """Load src/inference_engine.py (unchanged) by path, without altering sys.path."""
    global _legacy
    if _legacy is None:
        spec = importlib.util.spec_from_file_location("legacy_inference_engine", LEGACY_ENGINE)
        _legacy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_legacy)
    return _legacy


def legacy_inputs(case: Case):
    """Map the new inputs onto the legacy engine's sensor dict.  Returns (sensor, manual, notes)."""
    m, eq, obs = case.measurements, case.equipment, case.observations
    notes = []
    flow_pct = None
    if m.get("IND-05") is not None:
        if eq.get("PAR-08"):
            flow_pct = 100 * m["IND-05"] / eq["PAR-08"]
        elif eq.get("PAR-02"):
            flow_pct = 100 * m["IND-05"] / eq["PAR-02"]
            notes.append("Legacy engine expects flow as % of healthy baseline; % of rated flow was used instead.")
        else:
            notes.append("Legacy engine needs flow as % of baseline; no reference given, so flow was not passed.")
    present = lambda sid: obs.get(sid) == "present"
    sensor = {
        "vibration_mm_s_rms": m.get("IND-01"), "bearing_temp_c": m.get("IND-02"), "seal_temp_c": m.get("IND-03"),
        "motor_temp_c": m.get("IND-04"), "flow_percent_of_baseline": flow_pct,
        "discharge_pressure_bar": m.get("IND-12"), "suction_pressure_bar_abs": m.get("IND-07"),
        "motor_current_a": m.get("IND-08"), "pressure_fluctuation_percent": m.get("IND-09"),
        "abnormal_noise": present("SYM-14"), "crackling_noise": present("SYM-13"), "air_bubbles": present("SYM-17"),
        "prime_ok": (False if obs.get("SYM-18") == "present" else True if obs.get("SYM-18") == "absent" else None),
    }
    manual = [k for sid, k in (("SYM-15", "seal_leakage"), ("SYM-16", "coupling_vibration"),
                               ("SYM-20", "speed_unstable"), ("SYM-19", "rapid_temp_rise"),
                               ("SYM-21", "efficiency_low")) if present(sid)]
    notes.append("Legacy engine uses absolute thresholds (e.g. 4.2/6.0 bar, 38 A) designed for one prototype pump "
                 "and treats every missing value as normal.")
    if case.imputed:
        notes.append("Legacy engine cannot mark values as estimated; they are used as measured.")
    return sensor, manual, notes


def run_legacy(case: Case, top_n: int = 5):
    sensor, manual, notes = legacy_inputs(case)
    (results, _trace), evidence = legacy_module().diagnose_from_sensor(sensor, manual, top_n=top_n)
    return results, sorted(evidence), notes


def run_legacy_isolated(case: Case):
    """Legacy comparison that can never affect the new diagnosis: it receives a copy of the case and any
    failure is returned as a message instead of being raised."""
    try:
        return {"ok": True, "data": run_legacy(copy.deepcopy(case))}
    except Exception as exc:                  # noqa: BLE001 - comparison only; report, never propagate
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
