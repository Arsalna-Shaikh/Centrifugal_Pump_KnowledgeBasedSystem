"""Phase 5: turn the cleaned dataset into an analysis/knowledge-engineering-ready table.

Input   data/interim/cleaned_pump_dataset.csv + data/raw/pump_asset_register.csv
Output  data/processed/preprocessed_pump_dataset.csv   (original engineering units preserved)
        data/processed/scaler_params.json              (fitted on the TRAIN partition only)
        data/processed/schema_validation.csv
        reports/preprocessing_report.md

No model is trained here and the KBS inference engine is not replaced.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from common import (CLEAN_FILE, FAULTS, LABEL_TO_CODE, MANUFACTURERS, PROCESSED, PROCESSED_FILE,
                    PUMP_TYPES, REGISTER_FILE, REPORTS, SEED, SENSOR_COLS, SYMPTOMS, md_table)

SEVERITY_LEVEL = {"No Fault": 0, "Low": 1, "Medium": 2, "High": 3, "Critical": 4}
PRIORITY_LEVEL = {"Not Applicable": 0, "P4 - Low": 1, "P3 - Medium": 2, "P2 - High": 3, "P1 - Emergency": 4}

# Sensor -> symptom thresholds (engineering defaults; all documented in preprocessing_report.md)
THRESHOLDS = [
    # key, source columns, rule, justification
    ("vibration_high", ["Vibration_mm_s"], lambda d: d.Vibration_mm_s > 4.5,
     "> 4.5 mm/s RMS — upper limit of zone C in ISO 10816-3-style severity zones for medium machines "
     "(rigid mounting); verify against the standard/OEM before real use"),
    ("bearing_temp_high", ["Bearing_Temperature_C"], lambda d: d.Bearing_Temperature_C >= 80,
     "≥ 80 °C — same threshold as the existing KBS (src/inference_engine.py)"),
    ("seal_temp_high", ["Seal_Temperature_C"], lambda d: d.Seal_Temperature_C >= 80,
     "≥ 80 °C — prototype alarm level, ~30 °C above the normal band in this data"),
    ("motor_temp_high", ["Motor_Temperature_C"], lambda d: d.Motor_Temperature_C >= 95,
     "≥ 95 °C frame temperature — prototype alarm level"),
    ("flow_low", ["Flow_Rate"], lambda d: d.Flow_Pct_Rated.between(10, 75, inclusive="left"),
     "10–75 % of rated flow — same 75 % threshold as the existing KBS, but relative to each pump's rating"),
    ("no_flow", ["Flow_Rate"], lambda d: d.Flow_Pct_Rated < 10, "< 10 % of rated flow — as in the existing KBS"),
    ("discharge_pressure_low", ["Discharge_Pressure", "Suction_Pressure"], lambda d: d.Head_Pct_Rated < 85,
     "pump differential < 85 % of rated (relative, so it works for 3 bar and 28 bar pumps alike)"),
    ("discharge_pressure_high", ["Discharge_Pressure", "Suction_Pressure"], lambda d: d.Head_Pct_Rated > 115,
     "pump differential > 115 % of rated — approaching shut-off head"),
    ("suction_pressure_low", ["Suction_Pressure"], lambda d: d.Suction_Pressure < 0.8,
     "< 0.8 bar(a) — sub-atmospheric suction, cavitation risk"),
    ("motor_current_high", ["Motor_Current"], lambda d: d.Current_Pct_Rated > 110, "> 110 % of rated current"),
    ("pressure_fluctuation", ["Pressure_Fluctuation"], lambda d: d.Pressure_Fluctuation >= 10,
     "≥ 10 % — same as the existing KBS"),
    ("noise_high", ["Noise_Level"], lambda d: d.Noise_Level > 85,
     "> 85 dB(A) — common occupational upper exposure action value; used as an abnormal-noise proxy"),
    ("speed_deviation", ["Motor_Speed_RPM"], lambda d: d.Speed_Deviation_Pct.abs() > 1.5,
     "|speed − rated| > 1.5 % — larger than normal slip variation; new key, not yet in the KBS vocabulary"),
]
DERIVED_FROM = {
    "Differential_Pressure_bar": ["Discharge_Pressure", "Suction_Pressure"],
    "Head_Pct_Rated": ["Discharge_Pressure", "Suction_Pressure"],
    "Flow_Pct_Rated": ["Flow_Rate"], "Current_Pct_Rated": ["Motor_Current"],
    "Speed_Deviation_Pct": ["Motor_Speed_RPM"], "Current_per_Flow_Index": ["Motor_Current", "Flow_Rate"],
    "Vibration_Zone": ["Vibration_mm_s"],
}
Z_COLS = ["Vibration_mm_s", "Bearing_Temperature_C", "Seal_Temperature_C", "Motor_Temperature_C",
          "Flow_Pct_Rated", "Head_Pct_Rated", "Current_Pct_Rated", "Speed_Deviation_Pct",
          "Pressure_Fluctuation", "Noise_Level", "Operating_Hours", "Pump_Age_Years"]


def load():
    text = ("Observed_Symptoms", "Symptom_Keys", "Imputed_Columns", "Converted_Columns", "Invalid_Columns",
            "Suspect_Outlier_Columns", "Merged_Record_IDs", "DQ_Flags", "Maintenance_Date")
    df = pd.read_csv(CLEAN_FILE, keep_default_na=False, na_values=[""], dtype={c: str for c in text})
    for c in text:
        df[c] = df[c].fillna("")
    reg = pd.read_csv(REGISTER_FILE)
    return df, reg


def date_features(df):
    obs = pd.to_datetime(df.Observation_Date)
    inst = pd.to_datetime(df.Installation_Date)
    mnt = pd.to_datetime(df.Maintenance_Date.replace("", np.nan))
    df["Obs_Year"] = obs.dt.year
    df["Obs_Month"] = obs.dt.month
    df["Obs_Quarter"] = obs.dt.quarter
    df["Pump_Age_Years"] = ((obs - inst).dt.days / 365.25).round(2)
    df["Days_To_Maintenance"] = (mnt - obs).dt.days.astype("Int64")
    df["Has_Maintenance_Event"] = df.Maintenance_Action != "No action required"
    # Hours since the last *earlier* maintenance event on the same pump (only past information is used)
    df = df.sort_values(["Pump_ID", "Observation_Date"], kind="stable")
    last_hours = df.Operating_Hours.where(df.Has_Maintenance_Event)
    prev = last_hours.groupby(df.Pump_ID).transform(lambda s: s.shift(1).ffill())
    df["Hours_Since_Last_Maintenance"] = (df.Operating_Hours - prev).astype("Float64")
    return df


def engineering_features(df, reg):
    r = reg.set_index("Pump_ID")
    for c in ("Rated_Flow_m3h", "Rated_Differential_bar", "Nominal_Suction_bar_a", "Rated_Speed_RPM",
              "Rated_Current_A"):
        df[c] = df.Pump_ID.map(r[c])
    df["Differential_Pressure_bar"] = (df.Discharge_Pressure - df.Suction_Pressure).round(3)
    df["Flow_Pct_Rated"] = (100 * df.Flow_Rate / df.Rated_Flow_m3h).round(2)
    df["Head_Pct_Rated"] = (100 * df.Differential_Pressure_bar / df.Rated_Differential_bar).round(2)
    df["Current_Pct_Rated"] = (100 * df.Motor_Current / df.Rated_Current_A).round(2)
    df["Speed_Deviation_Pct"] = (100 * (df.Motor_Speed_RPM - df.Rated_Speed_RPM) / df.Rated_Speed_RPM).round(3)
    # energy-per-flow proxy: >1 means more current per unit flow than at the rating (efficiency loss)
    df["Current_per_Flow_Index"] = (df.Current_Pct_Rated / df.Flow_Pct_Rated.clip(lower=5)).round(3)
    df["Vibration_Zone"] = pd.cut(df.Vibration_mm_s, [0, 1.4, 2.8, 4.5, np.inf], labels=list("ABCD")).astype(str)
    df["Any_Sensor_Imputed"] = df.Imputed_Columns.str.contains("|".join(SENSOR_COLS))
    # A derived feature is only as real as its inputs: if any input was imputed, the derived value is unknown.
    # (Per-pump median imputation produced e.g. suction 1.7 bar > measured discharge 0.9 bar in dry-running
    # records -> a negative pump head. Schema validation caught this.)
    imputed = df.Imputed_Columns.str.split(";")
    for col, srcs in DERIVED_FROM.items():
        unknown = imputed.map(lambda s: any(c in s for c in srcs))
        df[col] = df[col].astype("Float64") if col != "Vibration_Zone" else df[col]
        df.loc[unknown, col] = "Unknown" if col == "Vibration_Zone" else pd.NA
    return df


def symptom_features(df):
    imputed = df.Imputed_Columns.str.split(";")
    for key, cols, rule, _ in THRESHOLDS:
        unknown = imputed.map(lambda s: any(c in s for c in cols))
        df[f"sens_{key}"] = pd.array(rule(df).fillna(False).astype(int), dtype="Int64")
        df.loc[unknown, f"sens_{key}"] = pd.NA          # never derive evidence from an imputed value
    not_recorded = df.Observed_Symptoms == "Not Recorded"
    keys = df.Symptom_Keys.str.split(";")
    for key in SYMPTOMS:
        col = pd.array(keys.map(lambda ks: int(key in ks)), dtype="Int64")
        df[f"obs_{key}"] = col
        df.loc[not_recorded, f"obs_{key}"] = pd.NA
    df["Observed_Symptom_Count"] = keys.map(lambda ks: len([k for k in ks if k])).where(~not_recorded)
    return df


def encodings(df):
    df["Fault_Code"] = df.Fault_Type.map(LABEL_TO_CODE)
    df["KBS_Fault_ID"] = df.Fault_Code.map(lambda c: FAULTS[c]["kbs_fault_id"] or "")
    df["Is_Fault"] = ~df.Fault_Type.isin(["Normal", "Unknown"])
    df["Severity_Level"] = df.Fault_Severity.map(SEVERITY_LEVEL).astype("Int64")      # Unknown -> <NA>
    df["Priority_Level"] = df.Maintenance_Priority.map(PRIORITY_LEVEL).astype("Int64")
    for c, vocab in (("Pump_Type", PUMP_TYPES), ("Manufacturer", MANUFACTURERS)):
        for v in vocab:
            df[f"{c}__{v.replace(' ', '_')}"] = (df[c] == v).astype(int)
    for v in ["No Fault Detected", "Suspected", "Confirmed", "Inconclusive", "Unknown"]:
        df[f"Diagnostic_Status__{v.replace(' ', '_')}"] = (df.Diagnostic_Status == v).astype(int)
    return df


def partition(df):
    """Group-aware, stratified split: all records of a pump land in exactly one partition."""
    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    fold = pd.Series(-1, index=df.index)
    for i, (_, idx) in enumerate(sgkf.split(df, df.Fault_Type, groups=df.Pump_ID)):
        fold.iloc[idx] = i
    df["Partition"] = fold.map({0: "test", 1: "validation"}).fillna("train")
    return df


def standardise(df):
    train = df.Partition == "train"
    params = {}
    for c in Z_COLS:
        mu, sd = float(df.loc[train, c].mean()), float(df.loc[train, c].std())
        params[c] = {"mean": mu, "std": sd}
        df[f"z_{c}"] = ((df[c] - mu) / sd).round(4)
    (PROCESSED / "scaler_params.json").write_text(json.dumps(params, indent=2), encoding="utf-8")
    return df, params


# ------------------------------------------------------------------ schema validation
def schema():
    s = {
        "Record_ID": ("str", False, r"^R-\d{6}$"), "Pump_ID": ("str", False, r"^P-\d{3}$"),
        "Pump_Type": ("cat", False, PUMP_TYPES), "Manufacturer": ("cat", False, MANUFACTURERS),
        "Installation_Date": ("date", False, None), "Observation_Date": ("date", False, None),
        "Maintenance_Date": ("date", True, None),
        "Operating_Hours": ("num", False, (0, 200_000)),
        "Fault_Type": ("cat", False, [v["label"] for v in FAULTS.values()]),
        "Fault_Severity": ("cat", False, [*SEVERITY_LEVEL, "Unknown"]),
        "Diagnostic_Status": ("cat", False, ["No Fault Detected", "Suspected", "Confirmed", "Inconclusive", "Unknown"]),
        "Maintenance_Priority": ("cat", False, [*PRIORITY_LEVEL, "Unknown"]),
        "Downtime_Hours": ("num", True, (0, 2000)), "Maintenance_Cost": ("num", True, (0, 500_000)),
        "Flow_Pct_Rated": ("num", True, (0, 160)), "Head_Pct_Rated": ("num", True, (0, 200)),
        "Current_Pct_Rated": ("num", True, (0, 200)), "Partition": ("cat", False, ["train", "validation", "test"]),
        "Vibration_Zone": ("cat", False, [*"ABCD", "Unknown"]),
    }
    from common import PLAUSIBLE
    for c in SENSOR_COLS:
        s[c] = ("num", False, PLAUSIBLE[c])
    for key, *_ in THRESHOLDS:
        s[f"sens_{key}"] = ("flag", True, None)
    for key in SYMPTOMS:
        s[f"obs_{key}"] = ("flag", True, None)
    return s


def validate(df) -> pd.DataFrame:
    rows = []
    for col, (kind, nullable, rule) in schema().items():
        if col not in df:
            rows.append({"column": col, "check": "present", "violations": 1}); continue
        x = df[col]
        nulls = int(x.isna().sum()) if kind != "date" else int((x.astype(str).isin(["", "nan"])).sum())
        rows.append({"column": col, "check": "nulls allowed" if nullable else "no nulls",
                     "violations": 0 if nullable else nulls})
        if kind == "num":
            ok = pd.api.types.is_numeric_dtype(x)
            bad = (~x.dropna().between(*rule)).sum() if ok else len(x)
            rows.append({"column": col, "check": f"numeric in {rule}", "violations": int(bad)})
        elif kind == "cat":
            rows.append({"column": col, "check": "allowed values", "violations": int((~x.dropna().isin(rule)).sum())})
        elif kind == "str":
            rows.append({"column": col, "check": f"matches {rule}",
                         "violations": int((~x.astype(str).str.match(rule)).sum())})
        elif kind == "date":
            v = x[x.astype(str) != ""]
            rows.append({"column": col, "check": "ISO date", "violations":
                         int(pd.to_datetime(v, format="%Y-%m-%d", errors="coerce").isna().sum())})
        elif kind == "flag":
            rows.append({"column": col, "check": "in {0,1,<NA>}", "violations": int((~x.dropna().isin([0, 1])).sum())})
    rows.append({"column": "Record_ID", "check": "unique", "violations": int(df.Record_ID.duplicated().sum())})
    rows.append({"column": "Pump_ID", "check": "in exactly one partition",
                 "violations": int((df.groupby("Pump_ID").Partition.nunique() > 1).sum())})
    return pd.DataFrame(rows)


def write_report(df, params, val):
    part = pd.crosstab(df.Fault_Type, df.Partition)[["train", "validation", "test"]]
    pumps = df.groupby("Partition").Pump_ID.nunique().reindex(["train", "validation", "test"])
    sens_cols = [f"sens_{k}" for k, *_ in THRESHOLDS]
    agree = []
    for k, *_ in THRESHOLDS:
        if f"obs_{k}" in df:
            m = df[f"sens_{k}"].notna() & df[f"obs_{k}"].notna()
            s, o = df.loc[m, f"sens_{k}"].astype(int), df.loc[m, f"obs_{k}"].astype(int)
            agree.append({"symptom": k, "sensor says yes": int(s.sum()), "operator says yes": int(o.sum()),
                          "both yes": int((s & o).sum()), "agreement %": round(100 * (s == o).mean(), 1)})
    L = ["# Preprocessing Report",
         "",
         "_Generated by `scripts/preprocess_dataset.py` from `data/interim/cleaned_pump_dataset.csv`._",
         "",
         f"Output: `data/processed/preprocessed_pump_dataset.csv` — **{len(df):,} rows × {df.shape[1]} columns**.",
         "",
         "## What was done and why",
         "| Operation | Columns created | Justification |",
         "|---|---|---|",
         "| Kept original engineering units | all 11 sensor columns unchanged | KBS rules and engineers reason in "
         "mm/s, °C, bar, A — normalising them away would make rules unreadable. |",
         "| Joined nameplate data from the asset register | `Rated_*`, `Nominal_Suction_bar_a` | Pumps range from "
         "20 to 900 m³/h; absolute thresholds cannot work across them. Register data is known a priori, so it "
         "does not leak labels. |",
         "| Relative performance features | `Flow_Pct_Rated`, `Head_Pct_Rated`, `Current_Pct_Rated`, "
         "`Speed_Deviation_Pct`, `Differential_Pressure_bar`, `Current_per_Flow_Index` | Express each reading as a "
         "position on its own pump's curve — the way pump engineers diagnose. |",
         "| Derived features from imputed inputs → <NA> | all relative features above | Schema validation found "
         "that per-pump median imputation can create impossible combinations (imputed suction above measured "
         "discharge in dry-running records → negative head). Imputed sensor values stay in the sensor columns "
         "(flagged), but nothing is *derived* from them. |",
         "| Vibration severity zone | `Vibration_Zone` (A–D) | ISO 10816-3-style zone boundaries 1.4 / 2.8 / 4.5 "
         "mm/s RMS (verify against the standard before real use). |",
         "| Date features | `Obs_Year/Month/Quarter`, `Pump_Age_Years`, `Days_To_Maintenance`, "
         "`Has_Maintenance_Event`, `Hours_Since_Last_Maintenance` | Age and running hours since the last "
         "intervention are classic wear indicators. Only *earlier* events are used, so there is no look-ahead. |",
         "| Sensor-derived symptoms | `sens_*` (1/0/<NA>) | Converts numbers into the symbolic evidence the KBS "
         "consumes. **<NA> when the source value was imputed** — evidence is never derived from a guess. |",
         "| Operator-recorded symptoms | `obs_*` (1/0/<NA>) | Multi-hot of `Symptom_Keys`; <NA> when symptoms were "
         "not recorded (≠ no symptoms). |",
         "| Ordinal encodings | `Severity_Level` 0–4, `Priority_Level` 0–4 | Natural order; `Unknown` → <NA>, "
         "not a fake level. |",
         "| One-hot encodings | `Pump_Type__*`, `Manufacturer__*`, `Diagnostic_Status__*` | Nominal categories, "
         "few levels. |",
         "| Label codes | `Fault_Code`, `KBS_Fault_ID`, `Is_Fault` | Link each record to the existing KBS fault "
         "IDs in `../data/faults.csv`. |",
         "| Group-aware stratified split | `Partition` | `StratifiedGroupKFold(5)` on `Fault_Type`, grouped by "
         "`Pump_ID`: fold 0 → test, fold 1 → validation, rest → train. Records of one pump (and therefore of one "
         "fault episode / maintenance event) never appear in two partitions. |",
         "| Standardisation | `z_*` for 12 continuous features | Only for optional distance-based evaluation. Mean/"
         "std fitted on **train only** (`scaler_params.json`) to avoid leakage. |",
         "",
         "### Not done (deliberately)",
         "- No normalisation of the original sensor columns; no scaling of flags or ordinal codes.",
         "- No model training, no oversampling, no feature selection — those belong to a later, separate "
         "evaluation and would otherwise leak test information.",
         "- Per-pump medians used during cleaning are computed within a pump; because the split is by pump, they "
         "never mix train and test pumps. The only cross-pump statistic is the global-median fallback for pumps "
         "with no observed value (not triggered in this run unless reported in the cleaning log).",
         "",
         "## Symptom thresholds",
         md_table(pd.DataFrame([(k, ", ".join(c), j) for k, c, _, j in THRESHOLDS],
                               columns=["symptom key", "source column(s)", "rule / justification"])),
         "",
         "## Sensor-derived vs operator-recorded symptoms",
         "Agreement between `sens_*` and `obs_*` where both are known. Disagreement is expected: operators miss "
         "readings, and thresholds here differ from whatever the technicians used. This is useful knowledge-"
         "acquisition evidence about which observations are reliable.",
         "", md_table(pd.DataFrame(agree)), "",
         f"Rows with ≥1 unknown sensor symptom (because the input was imputed): "
         f"**{int(df[sens_cols].isna().any(axis=1).sum()):,}**.",
         "",
         "## Partitions",
         md_table(pumps.rename("pumps").reset_index()), "",
         md_table(part, index=True), "",
         "## Scaler parameters (train only)",
         md_table(pd.DataFrame(params).T.rename_axis("feature"), index=True, floatfmt=".3f"), "",
         "## Schema validation",
         f"Checks run: {len(val)} · violations: **{int(val.violations.sum())}**", "",
         md_table(val[val.violations > 0]) if val.violations.sum() else "All checks passed.",
         ]
    (REPORTS / "preprocessing_report.md").write_text("\n".join(L), encoding="utf-8")


def main():
    df, reg = load()
    df = date_features(df)
    df = engineering_features(df, reg)
    df = symptom_features(df)
    df = encodings(df)
    df = partition(df)
    df, params = standardise(df)
    df = df.sort_values(["Pump_ID", "Observation_Date"]).reset_index(drop=True)
    val = validate(df)
    val.to_csv(PROCESSED / "schema_validation.csv", index=False)
    df.to_csv(PROCESSED_FILE, index=False)
    write_report(df, params, val)
    print(f"Preprocessed: {len(df)} rows x {df.shape[1]} columns; schema violations: {int(val.violations.sum())}")
    if val.violations.sum():
        sys.exit(1)


if __name__ == "__main__":
    main()
