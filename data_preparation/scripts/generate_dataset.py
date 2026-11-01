"""Phase 1 + 2: generate a SYNTHETIC centrifugal-pump dataset, then inject data-quality issues.

Outputs
  data/raw/pump_asset_register.csv          clean equipment master data (nameplate ratings)
  data/raw/raw_pump_dataset.csv             the deliberately DIRTY dataset (never edited afterwards)
  data/generation_log/clean_reference_dataset.csv   pre-corruption truth (evaluation only)
  data/generation_log/injected_issues.csv           one row per injected issue
  data/generation_log/generation_log.json           seed, counts, checksums

The raw file is write-once: if it already exists the script refuses to overwrite it
unless --force is given.  All records are synthetic and must not be presented as plant data.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd

from common import (COLUMNS, FAULTS, GENLOG, MANUFACTURERS, NO_SYMPTOM_TEXT, PUMP_TYPES,
                    RAW_FILE, REGISTER_FILE, SEED, SENSOR_COLS, SYMPTOMS, sha256)

N_PUMPS = 40
START, END = date(2023, 1, 2), date(2025, 12, 31)

# Rated envelope per pump type: (flow m3/h, differential bar, speeds, current A)
TYPE_SPEC = {
    "End Suction":     ((50, 250), (3.5, 7.0), (2950, 1475), (30, 120)),
    "Split Case":      ((300, 900), (4.0, 8.0), (1475,), (90, 250)),
    "Multistage":      ((20, 120), (10.0, 28.0), (2950,), (40, 150)),
    "Vertical Inline": ((30, 200), (2.5, 6.0), (2950, 1475), (20, 90)),
}

# Relative occurrence of each fault (before wear adjustment) and episode lengths.
FAULT_WEIGHTS = {"BRG": .16, "CAV": .11, "SEAL": .15, "IMP": .07, "MIS": .11, "BLK": .09,
                 "DRY": .07, "AIR": .08, "DIS": .07, "MOT": .08, "UNK": .03}
WEAR_FAULTS = {"BRG", "SEAL", "IMP"}

ROOT_CAUSES = {
    "BRG": ["Lubrication deficiency", "Contaminated lubricant", "Bearing fatigue (end of life)",
            "Overload from shaft misalignment"],
    "CAV": ["Insufficient NPSH available (low suction level)", "Partially clogged suction strainer",
            "Elevated liquid temperature", "Operation far right of best efficiency point"],
    "SEAL": ["Seal face wear", "Seal flush failure", "Elastomer degradation",
             "Excessive shaft vibration"],
    "IMP": ["Cavitation erosion", "Abrasive solids erosion", "Foreign object impact", "Corrosion"],
    "MIS": ["Improper installation alignment", "Thermal growth not compensated", "Pipe strain",
            "Soft foot / foundation settling"],
    "BLK": ["Debris accumulation in impeller", "Scaling / fouling deposits", "Clogged suction strainer"],
    "DRY": ["Loss of suction supply (empty tank)", "Suction valve closed", "Failed priming",
            "Level control failure"],
    "AIR": ["Leaking suction flange gasket", "Vortexing at low sump level", "Worn suction-side packing"],
    "DIS": ["Discharge valve partially closed", "Blocked discharge line", "Check valve stuck"],
    "MOT": ["Supply phase imbalance", "Overload from high-density fluid", "Winding insulation degradation",
            "Motor cooling fan blocked"],
}

INSPECTION_FINDING = {
    "BRG": ["Spectrum shows bearing defect frequencies", "Oil sample contains metal particles",
            "Outer race spalling found on inspection"],
    "CAV": ["Crackling noise near suction eye", "Pitting on impeller inlet vanes", "NPSH margin calculated below 1 m"],
    "SEAL": ["Drip leakage at seal gland", "Seal faces scored on inspection", "Seal flush line found blocked"],
    "IMP": ["Impeller vane tips eroded", "Impeller crack found during overhaul", "Performance test below curve"],
    "MIS": ["Dominant 2x running-speed vibration", "Laser check: offset exceeds tolerance", "Coupling insert worn unevenly"],
    "BLK": ["Rags and debris removed from impeller", "Scale deposits in volute", "Strainer differential pressure high"],
    "DRY": ["Suction tank found empty", "Seal faces heat-checked", "Casing hot to touch with no flow"],
    "AIR": ["Air bubbles visible in sight glass", "Vortex observed at sump inlet", "Suction flange leak found with soap test"],
    "DIS": ["Discharge valve found 20% open", "Blockage in discharge line", "Check valve seized partly closed"],
    "MOT": ["Phase current imbalance above 5%", "Motor winding insulation resistance low", "Motor fan cowl blocked"],
}

ACTIONS = {
    "BRG": "Replace bearings and renew lubrication",
    "CAV": "Restore suction conditions and clean strainer",
    "SEAL": "Replace mechanical seal",
    "IMP": "Repair or replace impeller",
    "MIS": "Laser realign pump and motor shafts",
    "BLK": "Clear blockage and clean impeller and strainer",
    "DRY": "Stop pump, restore liquid supply and re-prime",
    "AIR": "Seal suction-side leaks and re-prime",
    "DIS": "Open or repair discharge valve and clear line",
    "MOT": "Inspect motor and correct electrical fault",
    "UNK": "Further investigation scheduled",
    "PM": "Routine preventive maintenance",
    "NONE": "No action required",
}
DOWNTIME_MEDIAN = {"BRG": 10, "CAV": 6, "SEAL": 8, "IMP": 24, "MIS": 5, "BLK": 5, "DRY": 12,
                   "AIR": 4, "DIS": 3, "MOT": 20, "UNK": 2, "PM": 2}
COST_MEDIAN = {"BRG": 2500, "CAV": 1200, "SEAL": 3000, "IMP": 7000, "MIS": 900, "BLK": 800,
               "DRY": 4000, "AIR": 600, "DIS": 700, "MOT": 5000, "UNK": 300, "PM": 350}


# ===========================================================================
# Phase 1 — clean, engineering-informed data
# ===========================================================================
def make_register(rng):
    rows = []
    for i in range(1, N_PUMPS + 1):
        ptype = rng.choice(PUMP_TYPES, p=[.45, .2, .2, .15])
        (q_lo, q_hi), (dp_lo, dp_hi), speeds, (i_lo, i_hi) = TYPE_SPEC[ptype]
        inst = date(2010, 1, 1) + timedelta(days=int(rng.integers(0, 365 * 13)))
        rows.append({
            "Pump_ID": f"P-{i:03d}",
            "Pump_Type": ptype,
            "Manufacturer": rng.choice(MANUFACTURERS),
            "Installation_Date": inst.isoformat(),
            "Rated_Flow_m3h": round(float(rng.uniform(q_lo, q_hi)), 0),
            "Rated_Differential_bar": round(float(rng.uniform(dp_lo, dp_hi)), 2),
            "Nominal_Suction_bar_a": round(float(rng.uniform(1.0, 2.2)), 2),
            "Rated_Speed_RPM": int(rng.choice(speeds)),
            "Rated_Current_A": round(float(rng.uniform(i_lo, i_hi)), 0),
            "Utilisation": round(float(rng.uniform(0.55, 0.95)), 2),
        })
    return pd.DataFrame(rows)


def severity_label(s):
    return "Low" if s < .35 else "Medium" if s < .6 else "High" if s < .85 else "Critical"


def priority_for(code, sev):
    if code == "DRY" or sev == "Critical":
        return "P1 - Emergency"
    return {"High": "P2 - High", "Medium": "P3 - Medium", "Low": "P4 - Low"}.get(sev, "P4 - Low")


def simulate_reading(rng, pump, code, s, blend=None):
    """Return sensor dict for one observation. s in [0,1] is fault intensity."""
    q = float(np.clip(rng.normal(0.92, 0.06), 0.6, 1.12))   # flow as fraction of rated
    dp_factor = 1.0                                        # head degradation multiplier
    suction = pump.Nominal_Suction_bar_a + rng.normal(0, 0.06)
    vib = max(0.4, rng.normal(1.9 if pump.Pump_Type != "Split Case" else 1.5, 0.45))
    bt = 52 + rng.normal(0, 3.5)
    seal_t = 48 + rng.normal(0, 3.5)
    mot_t = 68 + rng.normal(0, 4)
    fluct = abs(rng.normal(2.0, 0.7))
    noise = 77 + rng.normal(0, 2)
    cur_mult = 1.0
    speed_drop = 0.0
    dry = False

    effects = [(code, s)] if blend is None else blend
    for c, k in effects:
        if c == "BRG":
            vib += 2 + 7 * k; bt += 8 + 35 * k; noise += 3 + 9 * k; cur_mult *= 1 + .04 * k
        elif c == "CAV":
            suction = min(suction, 0.25 + 0.5 * (1 - k) + rng.normal(0, .04))
            vib += 1.5 + 4 * k; noise += 5 + 10 * k; q -= .05 + .2 * k; dp_factor *= 1 - .15 * k
            fluct += 5 + 15 * k
        elif c == "SEAL":
            seal_t += 10 + 40 * k; vib += .5 * k
        elif c == "IMP":
            q -= .08 + .22 * k; dp_factor *= 1 - .08 - .22 * k; vib += 1.5 + 4.5 * k; cur_mult *= 1 + .05 * k
        elif c == "MIS":
            vib += 2.5 + 6 * k; bt += 4 + 16 * k; cur_mult *= 1 + .03 + .05 * k; noise += 2 + 4 * k
        elif c == "BLK":
            q -= .15 + .4 * k; dp_factor *= 1 - .05 - .25 * k; vib += .8 + 2 * k
            suction -= rng.uniform(0, .1 + .3 * k)
        elif c == "DRY":
            dry = True; seal_t += 25 + 55 * k; bt += 10 + 30 * k; noise += 4 + 8 * k; vib += 1 + 3 * k
        elif c == "AIR":
            fluct += 8 + 18 * k; q -= .08 + .22 * k; dp_factor *= 1 - .05 - .2 * k
            vib += .8 + 2.5 * k; noise += 1 + 3 * k
        elif c == "DIS":
            q *= 1 - .4 - .5 * k; dp_factor *= 1 + .03 * k; bt += 3 + 10 * k; seal_t += 4 + 16 * k
            vib += 1 + 2.5 * k; fluct += 2 + 5 * k
        elif c == "MOT":
            mot_t += 12 + 45 * k; cur_mult *= 1 + .08 + .25 * k; speed_drop += .004 + .03 * k
            vib += .8 + 2.5 * k; noise += 2 + 4 * k

    q = max(q, 0.02)
    # Simple radial-pump curve: differential rises towards shut-off, power falls with flow.
    diff = pump.Rated_Differential_bar * (1.25 - .25 * q ** 2) * dp_factor * (1 + rng.normal(0, .02))
    current = pump.Rated_Current_A * (.45 + .5 * q) * cur_mult * (1 + rng.normal(0, .02))
    if dry:
        q = rng.uniform(0, .08)
        suction = rng.uniform(.2, .6)
        diff = pump.Rated_Differential_bar * rng.uniform(.05, .25)
        current = pump.Rated_Current_A * rng.uniform(.35, .5)
    speed = pump.Rated_Speed_RPM * (1 + .004 * (1 - current / pump.Rated_Current_A) - speed_drop) \
        + rng.normal(0, 1.5)
    return {
        "Vibration_mm_s": round(vib, 2),
        "Bearing_Temperature_C": round(bt, 1),
        "Seal_Temperature_C": round(seal_t, 1),
        "Motor_Temperature_C": round(mot_t, 1),
        "Flow_Rate": round(pump.Rated_Flow_m3h * q, 1),
        "Suction_Pressure": round(max(suction, .05), 2),
        "Discharge_Pressure": round(max(suction, .05) + diff, 2),
        "Motor_Current": round(current, 1),
        "Motor_Speed_RPM": round(speed, 0),
        "Pressure_Fluctuation": round(fluct, 1),
        "Noise_Level": round(noise, 1),
    }


def observed_symptoms(rng, pump, r, code, s, blend=None):
    """Operator/technician-recorded symptoms: sensor-visible ones are logged ~85% of the time,
    non-instrumented observations are logged with fault-dependent probability."""
    q = r["Flow_Rate"] / pump.Rated_Flow_m3h
    rated_dis = pump.Nominal_Suction_bar_a + pump.Rated_Differential_bar
    checks = {
        "vibration_high": r["Vibration_mm_s"] > 4.5,
        "bearing_temp_high": r["Bearing_Temperature_C"] > 80,
        "seal_temp_high": r["Seal_Temperature_C"] > 80,
        "motor_temp_high": r["Motor_Temperature_C"] > 95,
        "flow_low": .1 <= q < .75,
        "no_flow": q < .1,
        "discharge_pressure_low": r["Discharge_Pressure"] < .85 * rated_dis,
        "discharge_pressure_high": r["Discharge_Pressure"] > 1.12 * rated_dis,
        "suction_pressure_low": r["Suction_Pressure"] < .8,
        "motor_current_high": r["Motor_Current"] > 1.1 * pump.Rated_Current_A,
        "pressure_fluctuation": r["Pressure_Fluctuation"] > 8,
        "noise_high": r["Noise_Level"] > 88,
    }
    found = [k for k, hit in checks.items() if hit and rng.random() < .85]
    effects = [(code, s)] if blend is None else blend
    manual = {"BRG": [("grinding_noise", .3 + .6 * s)], "CAV": [("crackling_noise", .5 + .4 * s)],
              "SEAL": [("seal_leakage", .6 + .4 * s)], "MIS": [("coupling_vibration", .5 + .4 * s)],
              "DRY": [("prime_failure", .7), ("rapid_temp_rise", .6)],
              "AIR": [("air_bubbles", .5 + .4 * s), ("prime_failure", .15)],
              "DIS": [("rapid_temp_rise", .3 + .5 * s)], "MOT": [("speed_unstable", .3 + .5 * s)],
              "IMP": [("grinding_noise", .2)]}
    for c, k in effects:
        for key, p in manual.get(c, []):
            if rng.random() < p and key not in found:
                found.append(key)
    if code == "NOR" and rng.random() < .03:            # occasional false operator report
        found.append(rng.choice(["noise_high", "vibration_high"]))
    return "; ".join(SYMPTOMS[k] for k in dict.fromkeys(found)) or NO_SYMPTOM_TEXT


def generate_clean(rng, register):
    rows = []
    rid = 0
    for pump in register.itertuples(index=False):
        inst = date.fromisoformat(pump.Installation_Date)
        d = START + timedelta(days=int(rng.integers(0, 5)))
        hours_at_last_pm = None
        last_hours = 0
        episode = []            # queued (code, s, is_last, blend, cause, sev_floor)
        while d <= END:
            hours = int((d - inst).days * 24 * pump.Utilisation + rng.normal(0, 15))
            hours = last_hours = max(hours, last_hours + 1)        # hour meters never run backwards
            if hours_at_last_pm is None:
                hours_at_last_pm = hours - int(rng.integers(0, 2000))
            if not episode and rng.random() < .21:
                w = {c: FAULT_WEIGHTS[c] * ((1 + hours / 60000) if c in WEAR_FAULTS else 1)
                     for c in FAULT_WEIGHTS}
                codes, p = list(w), np.array(list(w.values()))
                code = rng.choice(codes, p=p / p.sum())
                n = int(rng.integers(1, 3)) if code == "DRY" else int(rng.integers(1, 5))
                start_s, end_s = rng.uniform(.15, .5), rng.uniform(.55, 1.0)
                if code == "DRY":
                    start_s, end_s = max(start_s, .6), max(end_s, .75)
                blend = None
                if code == "UNK":
                    a, b = rng.choice([c for c in FAULT_WEIGHTS if c != "UNK"], size=2, replace=False)
                    blend = [(a, rng.uniform(.15, .45)), (b, rng.uniform(.15, .45))]
                cause = None if code == "UNK" else rng.choice(ROOT_CAUSES[code])
                if code == "BRG" and cause == "Overload from shaft misalignment" and blend is None:
                    blend = [("BRG", None), ("MIS", .3)]     # secondary-damage chain
                episode = [(code, float(sv), i == n - 1, blend, cause)
                           for i, sv in enumerate(np.linspace(start_s, end_s, n))]

            rid += 1
            rec = {"Record_ID": f"R-{rid:06d}", "Pump_ID": pump.Pump_ID, "Pump_Type": pump.Pump_Type,
                   "Manufacturer": pump.Manufacturer, "Installation_Date": pump.Installation_Date,
                   "Observation_Date": d.isoformat(), "Operating_Hours": hours}
            if episode:
                code, s, last, blend, cause = episode.pop(0)
                eff_blend = None if blend is None else [(c, s if k is None else k) for c, k in blend]
                r = simulate_reading(rng, pump, code, s, eff_blend)
                rec.update(r)
                rec["Observed_Symptoms"] = observed_symptoms(rng, pump, r, code, s, eff_blend)
                sev = severity_label(s) if code != "UNK" else rng.choice(["Low", "Medium"])
                confirmed = last and code != "UNK" and rng.random() < .9
                rec["Fault_Type"] = FAULTS[code]["label"]
                rec["Root_Cause"] = cause if confirmed else ("Unknown" if code == "UNK" else
                                                             (cause if rng.random() < .5 else "Under investigation"))
                evidence = f"Vibration {r['Vibration_mm_s']:.1f} mm/s; bearing {r['Bearing_Temperature_C']:.0f} C"
                if code != "UNK":
                    evidence += "; " + rng.choice(INSPECTION_FINDING[code])
                    if confirmed:
                        evidence += "; confirmed on inspection"
                else:
                    evidence += "; mixed indications, no single fault pattern"
                rec["Supporting_Evidence"] = evidence
                rec["Fault_Severity"] = sev
                rec["Diagnostic_Status"] = "Inconclusive" if code == "UNK" else ("Confirmed" if confirmed else "Suspected")
                rec["Maintenance_Priority"] = priority_for(code, sev)
                maint_code = code if confirmed else ("UNK" if code == "UNK" and last else None)
                if code in WEAR_FAULTS and confirmed:
                    hours_at_last_pm = hours
            else:
                r = simulate_reading(rng, pump, "NOR", 0.0)
                rec.update(r)
                rec["Observed_Symptoms"] = observed_symptoms(rng, pump, r, "NOR", 0.0)
                rec.update({"Fault_Type": "Normal", "Root_Cause": "Not Applicable",
                            "Supporting_Evidence": "All readings within normal operating band",
                            "Fault_Severity": "No Fault", "Diagnostic_Status": "No Fault Detected",
                            "Maintenance_Priority": "Not Applicable"})
                maint_code = None
                if hours - hours_at_last_pm > 2000:
                    maint_code = "PM"; hours_at_last_pm = hours
                    rec["Maintenance_Priority"] = "P4 - Low"

            if maint_code:
                pr = rec["Maintenance_Priority"]
                lag = {"P1 - Emergency": (0, 2), "P2 - High": (1, 5), "P3 - Medium": (3, 11)}.get(pr, (7, 22))
                lag = (0, 1) if maint_code == "PM" else lag
                s_eff = s if maint_code not in ("PM", "UNK") else .3
                size = (pump.Rated_Current_A / 80) ** .5
                rec["Maintenance_Action"] = ACTIONS[maint_code]
                rec["Maintenance_Date"] = (d + timedelta(days=int(rng.integers(*lag)))).isoformat()
                rec["Downtime_Hours"] = round(DOWNTIME_MEDIAN[maint_code] * (.7 + .6 * s_eff)
                                              * rng.lognormal(0, .3), 1)
                rec["Maintenance_Cost"] = round(COST_MEDIAN[maint_code] * size * (.7 + .6 * s_eff)
                                                * rng.lognormal(0, .3), 2)
            else:
                rec.update({"Maintenance_Action": ACTIONS["NONE"], "Maintenance_Date": "",
                            "Downtime_Hours": np.nan, "Maintenance_Cost": np.nan})
            rows.append(rec)
            d += timedelta(days=int(rng.integers(3, 10)))
    df = pd.DataFrame(rows)[COLUMNS]
    return df.sort_values(["Observation_Date", "Pump_ID"], kind="stable").reset_index(drop=True)


# ===========================================================================
# Phase 2 — deliberate data-quality problems
# ===========================================================================
LABEL_VARIANTS = {
    "Bearing Failure": ["bearing failure", "BEARING FAILURE", "Bearing fault", "Brg failure", "Bearing Failure "],
    "Cavitation": ["cavitation", "CAVITATION", " Cavitation", "Cavitation (suction)"],
    "Mechanical Seal Leakage": ["Seal Leak", "mech. seal leakage", "Seal leakage", "MECHANICAL SEAL LEAKAGE"],
    "Impeller Damage": ["impeller damage", "Impeller damaged", "IMPELLER DAMAGE"],
    "Shaft Misalignment": ["Misalignment", "shaft misalignment", "Shaft mis-alignment", "MISALIGNMENT"],
    "Pump Blockage": ["Blockage", "pump blockage", "Clogged pump", "PUMP BLOCKAGE"],
    "Dry Running": ["dry running", "Dry-running", "DRY RUN", "Dry run"],
    "Air Ingress": ["air ingress", "Air entrainment", "AIR INGRESS", "Air leak (suction)"],
    "Discharge Restriction": ["discharge restriction", "Restricted discharge", "DISCHARGE RESTRICTION"],
    "Motor Fault": ["motor fault", "Motor failure", "Electrical motor fault", "MOTOR FAULT"],
    "Normal": ["normal", "NORMAL", "Normal operation", "OK"],
}
TYPO_VARIANTS = {
    "Bearing Failure": ["Bearing Faliure", "Bearng Failure"], "Cavitation": ["Cavitaton", "Cavitiation"],
    "Mechanical Seal Leakage": ["Mechanical Seal Leakge", "Mechancal Seal Leakage"],
    "Impeller Damage": ["Impeller Damge", "Impellor Damage"],
    "Shaft Misalignment": ["Shaft Misalignmnet", "Shaft Missalignment"],
    "Pump Blockage": ["Pump Blokage", "Pump Blockge"], "Dry Running": ["Dry Runing", "Dry Runnning"],
    "Air Ingress": ["Air Ingres", "Air Ingrees"], "Discharge Restriction": ["Discharge Restricton"],
    "Motor Fault": ["Moter Fault", "Motor Falut"],
}
UNKNOWN_VARIANTS = ["unknown", "UNKNOWN", "?", "TBD", "Undiagnosed", "N.D.", "unk"]
SYMPTOM_SYNONYMS = {
    "High vibration": ["high vib", "Excessive vibration", "VIBRATION HIGH", "vibration high"],
    "High bearing temperature": ["Bearing hot", "brg temp high", "HIGH BEARING TEMP"],
    "High seal temperature": ["seal hot", "Seal temp high"],
    "High motor temperature": ["Motor hot", "motor overheating"],
    "Low flow": ["low flow", "Reduced flow", "LOW FLOW"],
    "No flow": ["no flow", "Zero flow"],
    "Low discharge pressure": ["low disch press", "Low head", "Discharge pressure low"],
    "High discharge pressure": ["high disch press", "Discharge pressure high"],
    "Low suction pressure": ["low suction", "Suction pressure low"],
    "High motor current": ["high amps", "Motor current high", "Overcurrent"],
    "Pressure fluctuating": ["pressure surging", "Unstable pressure", "pressure fluctuation"],
    "High noise level": ["noisy", "Loud noise", "noise high"],
    "Grinding noise": ["grinding sound", "Rumbling noise"],
    "Crackling noise": ["gravel noise", "crackling sound", "Popping noise"],
    "Visible seal leakage": ["seal leaking", "Leak at seal", "seal leak"],
    "Coupling vibration": ["coupling vib", "Vibration at coupling"],
    "Air bubbles in discharge": ["air bubbles", "Frothy discharge"],
    "Loss of prime": ["lost prime", "Pump not primed"],
    "Rapid temperature rise": ["temp rising fast", "Rapid temp rise"],
    "Motor speed unstable": ["speed hunting", "Unstable speed"],
    "No abnormal symptoms": ["none", "nil", "NO ISSUES", "Normal"],
}
CAT_VARIANTS = {
    "Pump_Type": {"End Suction": ["end suction", "END SUCTION", "End-Suction", "Endsuction"],
                  "Split Case": ["split case", "Split-case", "SPLIT CASE", "Horizontal split case"],
                  "Multistage": ["multistage", "Multi-stage", "MULTISTAGE", "Multi Stage"],
                  "Vertical Inline": ["vertical inline", "Vertical In-line", "VERTICAL INLINE", "Inline"]},
    "Manufacturer": {m: [m.lower(), m.upper(), m.replace(" ", ""), m + "."] for m in MANUFACTURERS},
    "Fault_Severity": {"Low": ["low", "L", "1", "LOW"], "Medium": ["medium", "Med", "M", "2"],
                       "High": ["high", "H", "3", "HIGH"], "Critical": ["critical", "CRIT", "4", "Severe"],
                       "No Fault": ["none", "N/A", "0", "no fault"]},
    "Diagnostic_Status": {"Confirmed": ["confirmed", "CONF", "Confirmed by inspection"],
                          "Suspected": ["suspected", "Susp.", "Possible"],
                          "Inconclusive": ["inconclusive", "Unclear", "Pending"],
                          "No Fault Detected": ["no fault", "NFD", "Healthy"]},
    "Maintenance_Priority": {"P1 - Emergency": ["P1", "Priority 1", "Emergency", "p1-emergency"],
                             "P2 - High": ["P2", "Priority 2", "high"],
                             "P3 - Medium": ["P3", "Priority 3", "medium"],
                             "P4 - Low": ["P4", "Priority 4", "low"],
                             "Not Applicable": ["NA", "n/a", "-"]},
    "Maintenance_Action": {v: [v.lower(), v.upper(), v.replace(" and ", " & ")] for v in ACTIONS.values()},
}
INVALID_TOKENS = ["N/A", "--", "ERR", "sensor fault", "#VALUE!", "null", "?"]


class Injector:
    def __init__(self, rng, df):
        self.rng, self.df, self.log = rng, df, []

    def sample(self, frac, mask=None):
        idx = self.df.index if mask is None else self.df.index[mask]
        k = int(round(len(idx) * frac))
        return list(self.rng.choice(idx, size=k, replace=False)) if k else []

    def set(self, i, col, new, issue):
        old = self.df.at[i, col]
        self.df.at[i, col] = new
        self.log.append({"Record_ID": self.df.at[i, "Record_ID"], "column": col, "issue_type": issue,
                         "clean_value": old, "injected_value": new})


def fmt_date(rng, iso):
    d = date.fromisoformat(iso)
    style = rng.integers(0, 4)
    return [d.strftime("%d/%m/%Y"), d.strftime("%d-%b-%Y"), d.strftime("%Y%m%d"), d.strftime("%Y/%m/%d")][style]


def inject(rng, clean, register):
    df = clean.astype(object).where(clean.notna(), "")        # raw export: everything is text
    for c in SENSOR_COLS + ["Operating_Hours", "Downtime_Hours", "Maintenance_Cost"]:
        df[c] = clean[c].map(lambda v: "" if pd.isna(v) else (str(int(v)) if float(v).is_integer()
                                                                and c in ("Operating_Hours", "Motor_Speed_RPM")
                                                                else str(v)))
    inj = Injector(rng, df)
    faulty = clean.Fault_Type.isin([v["label"] for k, v in FAULTS.items() if k not in ("NOR", "UNK")])
    has_maint = clean.Maintenance_Date != ""
    rated = register.set_index("Pump_ID")

    # 11. inconsistent categorical values (incl. Pump_ID formats)
    for col, variants in CAT_VARIANTS.items():
        frac = {"Pump_Type": .03, "Manufacturer": .03, "Fault_Severity": .04, "Diagnostic_Status": .03,
                "Maintenance_Priority": .03, "Maintenance_Action": .04}[col]
        for i in inj.sample(frac, clean[col].isin(variants)):
            inj.set(i, col, rng.choice(variants[clean.at[i, col]]), "inconsistent_categorical")
    for i in inj.sample(.015):
        n = int(clean.at[i, "Pump_ID"][2:])
        inj.set(i, "Pump_ID", rng.choice([f"p{n:03d}", f"P{n}", f"PUMP-{n:03d}", f"P-{n:03d} "]),
                "inconsistent_identifier")

    # 4/5. inconsistent fault labels and typos
    for i in inj.sample(.10, faulty | (clean.Fault_Type == "Normal") & (rng.random(len(clean)) < .05)):
        inj.set(i, "Fault_Type", rng.choice(LABEL_VARIANTS[clean.at[i, "Fault_Type"]]), "inconsistent_fault_label")
    for i in inj.sample(.02, faulty):
        if df.at[i, "Fault_Type"] == clean.at[i, "Fault_Type"]:
            inj.set(i, "Fault_Type", rng.choice(TYPO_VARIANTS[clean.at[i, "Fault_Type"]]), "typo_fault_label")
    # 12. unknown classifications written many ways
    for i in inj.sample(.4, clean.Fault_Type == "Unknown"):
        inj.set(i, "Fault_Type", rng.choice(UNKNOWN_VARIANTS), "unknown_label_variant")

    # 13. inconsistent free text
    for i in inj.sample(.12, clean.Observed_Symptoms != ""):
        parts = clean.at[i, "Observed_Symptoms"].split("; ")
        parts = [rng.choice(SYMPTOM_SYNONYMS[p]) if rng.random() < .6 else p for p in parts]
        sep = rng.choice([", ", " | ", " / ", ";", " and "])
        inj.set(i, "Observed_Symptoms", sep.join(parts) + rng.choice(["", " ", "."]), "inconsistent_text")
    for i in inj.sample(.03):
        v = df.at[i, "Supporting_Evidence"]
        inj.set(i, "Supporting_Evidence", rng.choice([v.upper(), v.lower(), "  " + v + "  "]), "inconsistent_text")

    # 6. inconsistent date formats
    for col, frac in (("Observation_Date", .06), ("Installation_Date", .04), ("Maintenance_Date", .06)):
        for i in inj.sample(frac, clean[col] != ""):
            inj.set(i, col, fmt_date(rng, clean.at[i, col]), "inconsistent_date_format")

    # 7. mixed measurement units (value converted and suffixed)
    for col in ["Bearing_Temperature_C", "Seal_Temperature_C", "Motor_Temperature_C"]:
        for i in inj.sample(.015):
            f = float(clean.at[i, col]) * 9 / 5 + 32
            inj.set(i, col, f"{f:.1f}{rng.choice([' °F', 'F', ' degF'])}", "mixed_units")
    for col in ["Suction_Pressure", "Discharge_Pressure"]:
        for i in inj.sample(.015):
            v = float(clean.at[i, col])
            inj.set(i, col, rng.choice([f"{v * 14.5038:.1f} psi", f"{v * 100:.0f} kPa"]), "mixed_units")
    for i in inj.sample(.015):
        v = float(clean.at[i, "Flow_Rate"])
        inj.set(i, "Flow_Rate", rng.choice([f"{v / .2271247:.0f} gpm", f"{v / 3.6:.1f} L/s"]), "mixed_units")

    # 10. data-entry outliers inside the physical range (decimal shift) — hard case
    for col in ["Vibration_mm_s", "Motor_Current", "Pressure_Fluctuation"]:
        for i in inj.sample(.002, clean.Fault_Type == "Normal"):
            inj.set(i, col, str(round(float(clean.at[i, col]) * 10, 2)), "outlier_decimal_shift")

    # 9. physically implausible values
    for i in inj.sample(.004):
        col = rng.choice(SENSOR_COLS)
        v = float(clean.at[i, col])
        bad = {"Vibration_mm_s": 250.0, "Bearing_Temperature_C": 999.0, "Seal_Temperature_C": -99.0,
               "Motor_Temperature_C": 999.0, "Flow_Rate": -abs(v), "Suction_Pressure": -0.5,
               "Discharge_Pressure": 9999.0, "Motor_Current": 0.0, "Motor_Speed_RPM": v * 10,
               "Pressure_Fluctuation": 250.0, "Noise_Level": 0.0}[col]
        inj.set(i, col, str(round(bad, 2)), "implausible_value")

    # 8. invalid data types
    for col in SENSOR_COLS:
        for i in inj.sample(.004):
            inj.set(i, col, rng.choice(INVALID_TOKENS), "invalid_type_token")
        for i in inj.sample(.005):
            v = str(df.at[i, col])
            if v.replace(".", "", 1).isdigit() and "." in v:
                inj.set(i, col, v.replace(".", ","), "invalid_type_comma_decimal")
    for i in inj.sample(.02):
        h = int(clean.at[i, "Operating_Hours"])
        inj.set(i, "Operating_Hours", rng.choice([f"{h:,}", f"{h} h", f"{h} hrs"]), "invalid_type_unit_text")
    for i in inj.sample(.08, has_maint):
        inj.set(i, "Maintenance_Cost", f"${float(clean.at[i, 'Maintenance_Cost']):,.2f}", "invalid_type_unit_text")
    for i in inj.sample(.05, has_maint):
        inj.set(i, "Downtime_Hours", f"{clean.at[i, 'Downtime_Hours']} hrs", "invalid_type_unit_text")

    # 1. missing numerical values (MCAR) + a sensor outage block (structured missingness)
    for col in SENSOR_COLS:
        for i in inj.sample(.015):
            inj.set(i, col, "", "missing_numeric")
    for i in inj.sample(.01):
        inj.set(i, "Operating_Hours", "", "missing_numeric")
    for i in inj.sample(.03, has_maint):
        inj.set(i, rng.choice(["Downtime_Hours", "Maintenance_Cost"]), "", "missing_numeric")
    for pid, (d0, d1) in {"P-007": ("2024-03-01", "2024-05-15"), "P-023": ("2025-06-01", "2025-07-20")}.items():
        m = (clean.Pump_ID == pid) & clean.Observation_Date.between(d0, d1)
        for i in clean.index[m]:
            inj.set(i, "Seal_Temperature_C", "", "missing_numeric_sensor_outage")

    # 2. missing categorical values
    for col, frac, mask in (("Pump_Type", .02, None), ("Manufacturer", .02, None),
                            ("Root_Cause", .04, faulty), ("Fault_Severity", .015, None),
                            ("Maintenance_Priority", .02, None), ("Diagnostic_Status", .01, None),
                            ("Observed_Symptoms", .015, None), ("Fault_Type", .007, None)):
        for i in inj.sample(frac, mask):
            inj.set(i, col, "", "missing_categorical" if col != "Fault_Type" else "missing_fault_label")

    # 3. duplicates — exact re-uploads and near-duplicates (same reading re-keyed)
    dirty = inj.df
    exact_idx = inj.sample(.015)
    near_idx = inj.sample(.005)
    extra = [dirty.loc[exact_idx]]
    for i in exact_idx:
        inj.log.append({"Record_ID": dirty.at[i, "Record_ID"], "column": "*", "issue_type": "exact_duplicate",
                        "clean_value": "", "injected_value": "row copied"})
    near = dirty.loc[near_idx].copy()
    for j, i in enumerate(near_idx):
        new_id = f"R-{900001 + j:06d}"
        near.at[i, "Record_ID"] = new_id
        near.at[i, "Observation_Date"] = fmt_date(rng, clean.at[i, "Observation_Date"])
        near.at[i, "Fault_Type"] = str(dirty.at[i, "Fault_Type"]).upper()
        inj.log.append({"Record_ID": new_id, "column": "*", "issue_type": "near_duplicate",
                        "clean_value": clean.at[i, "Record_ID"], "injected_value": "re-keyed copy"})
    extra.append(near)
    out = pd.concat([dirty, *extra], ignore_index=True)
    key = np.arange(len(out), dtype=float)                 # export stays roughly chronological,
    key[len(dirty):] = rng.uniform(0, len(dirty), len(out) - len(dirty))   # copies land anywhere
    out = out.iloc[np.argsort(key, kind="stable")].reset_index(drop=True)
    return out, pd.DataFrame(inj.log)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true", help="overwrite an existing raw dataset")
    args = ap.parse_args()
    if RAW_FILE.exists() and not args.force:
        log = json.loads((GENLOG / "generation_log.json").read_text(encoding="utf-8"))
        ok = sha256(RAW_FILE) == log["raw_sha256"]
        print(f"Raw dataset already exists - not overwritten (checksum {'OK' if ok else 'MISMATCH'}). "
              "Use --force to regenerate.")
        sys.exit(0 if ok else 1)

    rng = np.random.default_rng(SEED)
    register = make_register(rng)
    clean = generate_clean(rng, register)
    raw, log = inject(rng, clean, register)

    register.to_csv(REGISTER_FILE, index=False)
    raw.to_csv(RAW_FILE, index=False)
    clean.to_csv(GENLOG / "clean_reference_dataset.csv", index=False)
    log.to_csv(GENLOG / "injected_issues.csv", index=False)
    summary = {
        "seed": SEED,
        "synthetic_disclosure": "All records are synthetic, generated by scripts/generate_dataset.py. "
                                "They are not plant measurements.",
        "pumps": N_PUMPS,
        "clean_records": len(clean),
        "raw_records": len(raw),
        "raw_columns": raw.shape[1],
        "fault_distribution_clean": clean.Fault_Type.value_counts().to_dict(),
        "issue_counts": log.issue_type.value_counts().to_dict(),
        "issue_counts_by_column": log.groupby(["issue_type", "column"]).size()
                                     .rename("n").reset_index().to_dict("records"),
        "raw_sha256": sha256(RAW_FILE),
        "register_sha256": sha256(REGISTER_FILE),
    }
    (RAW_FILE.parent / "CHECKSUMS.sha256").write_text(
        f"{summary['raw_sha256']}  {RAW_FILE.name}\n{summary['register_sha256']}  {REGISTER_FILE.name}\n",
        encoding="utf-8")
    (GENLOG / "generation_log.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"Generated {len(clean)} clean records -> {len(raw)} raw rows ({raw.shape[1]} columns); "
          f"{len(log)} logged issues.")


if __name__ == "__main__":
    main()
