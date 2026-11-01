"""Shared paths, seed and controlled vocabulary for the data-preparation pipeline.

Everything here lives under data_preparation/ so the pipeline can never touch the
existing KBS files in ../data, ../src or ../tests.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

SEED = 359

PREP = Path(__file__).resolve().parents[1]          # .../data_preparation
DATA = PREP / "data"
RAW = DATA / "raw"
GENLOG = DATA / "generation_log"                    # ground truth, used ONLY for evaluation
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
REPORTS = PREP / "reports"
VIS = PREP / "visualizations"

RAW_FILE = RAW / "raw_pump_dataset.csv"
REGISTER_FILE = RAW / "pump_asset_register.csv"
CLEAN_FILE = INTERIM / "cleaned_pump_dataset.csv"
PROCESSED_FILE = PROCESSED / "preprocessed_pump_dataset.csv"

for _d in (RAW, GENLOG, INTERIM, PROCESSED, REPORTS, VIS):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Controlled vocabulary (domain knowledge, not derived from the data)
# ---------------------------------------------------------------------------
# code -> canonical fault label.  kbs_fault_id maps onto ../data/faults.csv.
FAULTS = {
    "NOR": {"label": "Normal", "kbs_fault_id": None},
    "BRG": {"label": "Bearing Failure", "kbs_fault_id": "F01"},
    "CAV": {"label": "Cavitation", "kbs_fault_id": "F02"},
    "SEAL": {"label": "Mechanical Seal Leakage", "kbs_fault_id": "F05"},
    "IMP": {"label": "Impeller Damage", "kbs_fault_id": "F10"},
    "MIS": {"label": "Shaft Misalignment", "kbs_fault_id": "F03"},
    "BLK": {"label": "Pump Blockage", "kbs_fault_id": "F04/F06"},
    "DRY": {"label": "Dry Running", "kbs_fault_id": "F07"},
    "AIR": {"label": "Air Ingress", "kbs_fault_id": "F12"},
    "DIS": {"label": "Discharge Restriction", "kbs_fault_id": "F11"},
    "MOT": {"label": "Motor Fault", "kbs_fault_id": "F08/F14"},
    "UNK": {"label": "Unknown", "kbs_fault_id": None},
}
FAULT_LABELS = [v["label"] for v in FAULTS.values()]
LABEL_TO_CODE = {v["label"]: k for k, v in FAULTS.items()}

# Symptom keys reuse the vocabulary of ../data/symptoms.csv where one exists.
SYMPTOMS = {
    "vibration_high": "High vibration",
    "bearing_temp_high": "High bearing temperature",
    "seal_temp_high": "High seal temperature",
    "motor_temp_high": "High motor temperature",
    "flow_low": "Low flow",
    "no_flow": "No flow",
    "discharge_pressure_low": "Low discharge pressure",
    "discharge_pressure_high": "High discharge pressure",
    "suction_pressure_low": "Low suction pressure",
    "motor_current_high": "High motor current",
    "pressure_fluctuation": "Pressure fluctuating",
    "noise_high": "High noise level",
    "grinding_noise": "Grinding noise",
    "crackling_noise": "Crackling noise",
    "seal_leakage": "Visible seal leakage",
    "coupling_vibration": "Coupling vibration",
    "air_bubbles": "Air bubbles in discharge",
    "prime_failure": "Loss of prime",
    "rapid_temp_rise": "Rapid temperature rise",
    "speed_unstable": "Motor speed unstable",
}
NO_SYMPTOM_TEXT = "No abnormal symptoms"

PUMP_TYPES = ["End Suction", "Split Case", "Multistage", "Vertical Inline"]
MANUFACTURERS = ["Vendor A", "Vendor B", "Vendor C", "Vendor D"]   # anonymised on purpose
SEVERITIES = ["No Fault", "Low", "Medium", "High", "Critical"]
STATUSES = ["No Fault Detected", "Suspected", "Confirmed", "Inconclusive"]
PRIORITIES = ["Not Applicable", "P4 - Low", "P3 - Medium", "P2 - High", "P1 - Emergency"]

SENSOR_COLS = [
    "Vibration_mm_s", "Bearing_Temperature_C", "Seal_Temperature_C", "Motor_Temperature_C",
    "Flow_Rate", "Suction_Pressure", "Discharge_Pressure", "Motor_Current",
    "Motor_Speed_RPM", "Pressure_Fluctuation", "Noise_Level",
]
UNITS = {
    "Operating_Hours": "h", "Vibration_mm_s": "mm/s RMS", "Bearing_Temperature_C": "°C",
    "Seal_Temperature_C": "°C", "Motor_Temperature_C": "°C", "Flow_Rate": "m³/h",
    "Suction_Pressure": "bar(a)", "Discharge_Pressure": "bar(a)", "Motor_Current": "A",
    "Motor_Speed_RPM": "rpm", "Pressure_Fluctuation": "% of mean", "Noise_Level": "dB(A)",
    "Downtime_Hours": "h", "Maintenance_Cost": "USD",
}

# Physical plausibility limits (engineering judgement, in canonical units).  A value outside
# these limits cannot come from a running centrifugal pump/sensor and is treated as an
# entry/sensor error.  Values inside the limits are never deleted, however extreme.
PLAUSIBLE = {
    "Operating_Hours": (0, 200_000),
    "Vibration_mm_s": (0.05, 50),
    "Bearing_Temperature_C": (-10, 150),
    "Seal_Temperature_C": (-10, 200),
    "Motor_Temperature_C": (-10, 180),
    "Flow_Rate": (0, 2_000),
    "Suction_Pressure": (0.01, 10),
    "Discharge_Pressure": (0.01, 60),
    "Motor_Current": (0.5, 400),
    "Motor_Speed_RPM": (300, 3_600),
    "Pressure_Fluctuation": (0, 100),
    "Noise_Level": (30, 130),
    "Downtime_Hours": (0, 2_000),
    "Maintenance_Cost": (0, 500_000),
}

COLUMNS = [
    "Record_ID", "Pump_ID", "Pump_Type", "Manufacturer", "Installation_Date",
    "Observation_Date", "Operating_Hours",
    *SENSOR_COLS,
    "Observed_Symptoms", "Fault_Type", "Root_Cause", "Supporting_Evidence",
    "Fault_Severity", "Diagnostic_Status",
    "Maintenance_Action", "Maintenance_Date", "Downtime_Hours", "Maintenance_Cost",
    "Maintenance_Priority",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def md_table(df, index=False, floatfmt=".2f") -> str:
    """Small markdown table writer (avoids the optional `tabulate` dependency)."""
    d = df.reset_index() if index else df
    def fmt(v):
        if isinstance(v, float):
            return "" if v != v else format(v, floatfmt)
        return str(v).replace("|", "\\|").replace("\n", " ")
    head = "| " + " | ".join(map(str, d.columns)) + " |"
    sep = "|" + "|".join("---" for _ in d.columns) + "|"
    rows = ["| " + " | ".join(fmt(v) for v in r) + " |" for r in d.itertuples(index=False)]
    return "\n".join([head, sep, *rows])
