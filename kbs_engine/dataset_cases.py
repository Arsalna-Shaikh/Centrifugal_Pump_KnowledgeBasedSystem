"""Build engine cases from the SYNTHETIC cleaned dataset (data_preparation/), read-only.

Used for test-case preparation and a consistency check only.  The dataset's labels were produced by
the project's own generator, so agreement with them is NOT evidence of diagnostic accuracy.
"""
from __future__ import annotations

import csv
from pathlib import Path

from .engine import Case
from .knowledge import KnowledgeBase, split

ROOT = Path(__file__).resolve().parents[1]
CLEANED = ROOT / "data_preparation" / "data" / "interim" / "cleaned_pump_dataset.csv"
REGISTER = ROOT / "data_preparation" / "data" / "raw" / "pump_asset_register.csv"

COLUMN_TO_INDICATOR = {
    "Vibration_mm_s": "IND-01", "Bearing_Temperature_C": "IND-02", "Seal_Temperature_C": "IND-03",
    "Motor_Temperature_C": "IND-04", "Flow_Rate": "IND-05", "Suction_Pressure": "IND-07",
    "Discharge_Pressure": "IND-12", "Motor_Current": "IND-08", "Pressure_Fluctuation": "IND-09",
}
LABEL_TO_KB = {
    "Normal": "OUT-N", "Unknown": "OUT-U", "Cavitation": "FLT-01", "Dry Running": "FLT-02",
    "Air Ingress": "FLT-03", "Bearing Failure": "FLT-04", "Shaft Misalignment": "FLT-05",
    "Mechanical Seal Leakage": "FLT-06", "Impeller Damage": "FLT-07", "Pump Blockage": "FLT-08",
    "Discharge Restriction": "FLT-09", "Motor Fault": "FLT-11",
}


def load_rows(path: Path = CLEANED) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_register(path: Path = REGISTER) -> dict:
    with open(path, encoding="utf-8", newline="") as f:
        return {r["Pump_ID"]: r for r in csv.DictReader(f)}


def case_from_row(row: dict, register: dict, kb: KnowledgeBase) -> Case:
    pump = register[row["Pump_ID"]]
    equipment = {
        # Assumption (KA-3 section 3.1): all dataset pump types are radial-flow designs.
        "PAR-01": "radial",
        "PAR-02": float(pump["Rated_Flow_m3h"]),
        "PAR-03": float(pump["Rated_Differential_bar"]),
        "PAR-04": float(pump["Rated_Current_A"]),
        "PAR-05": float(pump["Rated_Speed_RPM"]),
    }
    measurements = {ind: (float(row[col]) if row[col] != "" else None) for col, ind in COLUMN_TO_INDICATOR.items()}
    imputed = {COLUMN_TO_INDICATOR[c] for c in split(row["Imputed_Columns"]) if c in COLUMN_TO_INDICATOR}
    if {"Suction_Pressure", "Discharge_Pressure"} & set(split(row["Imputed_Columns"])):
        imputed.add("IND-06")
    observations = {}
    if row["Observed_Symptoms"] != "Not Recorded":
        recorded = set(split(row["Symptom_Keys"]))
        for sid, s in kb.symptoms.items():
            # only non-instrumented symptoms come from the operator; sensor symptoms are derived from measurements
            if s["kind"] in ("observed", "trend") and s["key"] in recorded:
                observations[sid] = "present"
            # a symptom the operator did not record stays UNKNOWN (not absent)
    return Case(equipment=equipment, measurements=measurements, observations=observations, imputed=imputed)
