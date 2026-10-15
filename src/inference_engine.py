from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

SAFETY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def load_knowledge():
    faults = pd.read_csv(DATA / "faults.csv")
    weights = pd.read_csv(DATA / "symptom_fault_weights.csv")
    actions = pd.read_csv(DATA / "maintenance_actions.csv")
    symptoms = pd.read_csv(DATA / "symptoms.csv")
    with open(DATA / "rules.json", encoding="utf-8") as f:
        rules = json.load(f)
    return faults, weights, actions, symptoms, rules


def derive_symptoms(sensor):
    """Convert numeric readings into symbolic evidence.
    Thresholds are prototype defaults for this academic demo, not OEM safety limits.
    """
    e = set()
    v = sensor.get
    if v("vibration_mm_s_rms") is not None and v("vibration_mm_s_rms") >= 6.0: e.add("vibration_high")
    if v("bearing_temp_c") is not None and v("bearing_temp_c") >= 80: e.add("bearing_temp_high")
    if v("motor_temp_c") is not None and v("motor_temp_c") >= 80: e.add("motor_temp_high")
    if v("flow_percent_of_baseline") is not None and v("flow_percent_of_baseline") < 75: e.add("flow_low")
    if v("flow_percent_of_baseline") is not None and v("flow_percent_of_baseline") < 10: e.add("no_flow")
    if v("discharge_pressure_bar") is not None and v("discharge_pressure_bar") < 4.2: e.add("discharge_pressure_low")
    if v("discharge_pressure_bar") is not None and v("discharge_pressure_bar") > 6.0: e.add("discharge_pressure_high")
    if v("suction_pressure_bar_abs") is not None and v("suction_pressure_bar_abs") < 0.70: e.add("suction_pressure_low")
    if v("motor_current_a") is not None and v("motor_current_a") > 38: e.add("motor_current_high")
    if v("seal_temp_c") is not None and v("seal_temp_c") >= 85: e.add("seal_temp_high")
    if v("pressure_fluctuation_percent") is not None and v("pressure_fluctuation_percent") >= 10:
        e.update(["pressure_fluctuation","flow_fluctuation"])
    if v("abnormal_noise"): e.add("grinding_noise")
    if v("crackling_noise"): e.add("crackling_noise")
    if v("air_bubbles"): e.add("air_bubbles")
    if v("seal_leakage"): e.add("seal_leakage")
    if v("coupling_vibration"): e.add("coupling_vibration")
    if v("base_vibration"): e.add("base_vibration")
    if v("speed_unstable"): e.add("speed_unstable")
    if v("efficiency_low"): e.add("efficiency_low")
    if v("rapid_temp_rise"): e.add("rapid_temp_rise")
    if v("prime_ok") is False: e.add("prime_failure")
    return e


def diagnose(evidence, top_n=5):
    faults, weights, actions, symptoms, rules = load_knowledge()
    evidence = set(evidence)
    results = []
    trace = []
    for _, fault in faults.iterrows():
        fid = fault.fault_id
        fw = weights[weights.fault_id == fid]
        max_score = fw.weight.clip(lower=0).sum() + sum(r.get("bonus",0) for r in rules if r["fault_id"] == fid)
        score = 0.0
        matched = []
        for _, row in fw.iterrows():
            if row.symptom_key in evidence:
                score += float(row.weight)
                matched.append((row.symptom_key, float(row.weight)))
        fired = []
        for rule in rules:
            if rule["fault_id"] == fid and all(c in evidence for c in rule["conditions"]):
                score += float(rule.get("bonus",0))
                fired.append(rule)
        confidence = 0 if max_score <= 0 else min(100.0, 100.0 * score / max_score)
        coverage = 0 if len(fw)==0 else 100.0 * len(matched)/len(fw)
        result = {
            "fault_id": fid,
            "fault": fault.fault_name,
            "component": fault.component_id,
            "safety_priority": fault.safety_priority,
            "repair_cost": fault.repair_cost,
            "downtime": fault.downtime,
            "score": round(score,2),
            "confidence": round(confidence,1),
            "coverage": round(coverage,1),
            "matched_evidence": [m[0] for m in sorted(matched,key=lambda x:x[1], reverse=True)],
            "fired_rules": [r["id"] for r in fired],
            "rule_explanations": [r["explanation"] for r in fired],
        }
        results.append(result)
    results.sort(key=lambda r: (r["confidence"], SAFETY_RANK.get(r["safety_priority"],0), r["score"]), reverse=True)
    for r in results[:top_n]:
        fa = actions[actions.fault_id == r["fault_id"]].sort_values("sequence")
        r["actions"] = fa[["action","cost","downtime","details"]].to_dict("records")
        trace.append({"fault":r["fault"],"evidence":r["matched_evidence"],"rules":r["fired_rules"],"confidence":r["confidence"]})
    return results[:top_n], trace


def diagnose_from_sensor(sensor, manual_evidence=None, top_n=5):
    evidence = derive_symptoms(sensor)
    if manual_evidence:
        evidence.update(manual_evidence)
    return diagnose(evidence, top_n=top_n), evidence
