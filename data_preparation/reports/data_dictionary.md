# Data Dictionary

Units below are the **canonical units after cleaning**. In the raw file every column is text and some values
carry other units (°F, psi, kPa, gpm, L/s) — see `dataset_description.md`.

## 1. Source columns (raw → cleaned; same names in both)

### A. Equipment information
| Column | Type (cleaned) | Unit / format | Description | Allowed values / notes |
|---|---|---|---|---|
| Record_ID | string | `R-nnnnnn` | Unique condition-record key | unique after cleaning; near-duplicate copies used `R-9xxxxx` |
| Pump_ID | string | `P-nnn` | Pump asset tag; join key to the asset register | `P-001` … `P-040` |
| Pump_Type | category | — | Construction type | End Suction, Split Case, Multistage, Vertical Inline |
| Manufacturer | category | — | Anonymised manufacturer | Vendor A–D |
| Installation_Date | date | ISO `YYYY-MM-DD` | Commissioning date | from asset register |
| Observation_Date | date | ISO `YYYY-MM-DD` | Date of the condition record (added: needed to order records) | 2023-01-02 … 2025-12-31 |
| Operating_Hours | integer | h | Cumulative running hours at observation | non-decreasing per pump |

### B. Operating and sensor information
| Column | Type | Unit | Description | Normal band in this data | Physical limit used in cleaning |
|---|---|---|---|---|---|
| Vibration_mm_s | float | mm/s RMS | Overall bearing-housing vibration velocity | ≈1–3 | 0.05–50 |
| Bearing_Temperature_C | float | °C | Bearing housing temperature | ≈45–60 | −10–150 |
| Seal_Temperature_C | float | °C | Mechanical-seal area temperature | ≈40–56 | −10–200 |
| Motor_Temperature_C | float | °C | Motor frame temperature | ≈60–76 | −10–180 |
| Flow_Rate | float | m³/h | Delivered flow | ≈80–110 % of rated | 0–2000 and ≤ 160 % rated |
| Suction_Pressure | float | bar(a) | Absolute suction pressure | ≈1.0–2.3 | 0.01–10 |
| Discharge_Pressure | float | bar(a) | Absolute discharge pressure | suction + rated Δp | 0.01–60 |
| Motor_Current | float | A | Motor line current | ≈85–100 % of rated | 0.5–400 and ≤ 200 % rated |
| Motor_Speed_RPM | integer | rpm | Shaft speed | rated ± 0.5 % | 300–3600 and ± 5 % rated |
| Pressure_Fluctuation | float | % of mean | Peak-to-peak discharge pressure variation | ≈1–4 | 0–100 |
| Noise_Level | float | dB(A) | Sound level near the pump | ≈73–81 | 30–130 |

### C. Diagnostic information
| Column | Type | Description | Allowed values (cleaned) |
|---|---|---|---|
| Observed_Symptoms | text | Technician-recorded symptoms, canonical phrases joined by `; ` | 20 canonical symptoms, `No abnormal symptoms`, or `Not Recorded` (missing in source) |
| Fault_Type | category | Diagnosis | Normal, Bearing Failure, Cavitation, Mechanical Seal Leakage, Impeller Damage, Shaft Misalignment, Pump Blockage, Dry Running, Air Ingress, Discharge Restriction, Motor Fault, Unknown |
| Root_Cause | category | Cause of the fault, when established | 37 specific causes, `Under investigation`, `Unknown`, `Not Applicable` (normal) |
| Supporting_Evidence | text | Key readings + inspection finding | free text |
| Fault_Severity | ordinal | Severity judgement | No Fault, Low, Medium, High, Critical, Unknown |
| Diagnostic_Status | category | Certainty of the diagnosis | No Fault Detected, Suspected, Confirmed, Inconclusive, Unknown |

### D. Maintenance information
| Column | Type | Unit | Description | Notes |
|---|---|---|---|---|
| Maintenance_Action | category | — | Work-order type | 11 corrective/investigative actions, `Routine preventive maintenance`, `No action required` |
| Maintenance_Date | date | ISO | Date work was performed | empty when no maintenance event (structural, never imputed) |
| Downtime_Hours | float | h | Pump unavailable time | empty when no maintenance event |
| Maintenance_Cost | float | USD | Parts + labour | empty when no maintenance event; synthetic |
| Maintenance_Priority | ordinal | — | Planning priority | P1 - Emergency, P2 - High, P3 - Medium, P4 - Low, Not Applicable, Unknown |

## 2. Columns added by cleaning (`data/interim/cleaned_pump_dataset.csv`)
| Column | Description |
|---|---|
| Symptom_Keys | `;`-separated canonical symptom keys (same vocabulary as `../data/symptoms.csv` where it exists) |
| Label_Missing_In_Source | True when Fault_Type was empty in the raw file (kept as Unknown, not guessed) |
| Imputed_Columns | columns whose value in this row was imputed or filled (median, interpolation, per-pump mode, implied, Unknown) |
| Converted_Columns | columns whose value was converted from another unit |
| Invalid_Columns | columns whose raw value was physically implausible and was nullified (then imputed) |
| Suspect_Outlier_Columns | columns with an uncorroborated extreme in a Normal record (treated as entry error) |
| Merged_Record_IDs | Record_IDs of near-duplicate copies merged into this row |
| DQ_Flags | consistency/review flags (e.g. `discharge_not_above_suction`) |
| Raw_Row | spreadsheet row number in the raw file (traceability) |

## 3. Columns added by preprocessing (`data/processed/preprocessed_pump_dataset.csv`)
| Group | Columns | Description |
|---|---|---|
| Nameplate | Rated_Flow_m3h, Rated_Differential_bar, Nominal_Suction_bar_a, Rated_Speed_RPM, Rated_Current_A | joined from the asset register |
| Relative performance | Differential_Pressure_bar, Flow_Pct_Rated, Head_Pct_Rated, Current_Pct_Rated, Speed_Deviation_Pct, Current_per_Flow_Index | position on the pump's own curve; `<NA>` if an input was imputed |
| Severity zone | Vibration_Zone | A ≤ 1.4, B ≤ 2.8, C ≤ 4.5, D > 4.5 mm/s (ISO 10816-3-style); `Unknown` if imputed |
| Dates | Obs_Year, Obs_Month, Obs_Quarter, Pump_Age_Years, Days_To_Maintenance, Has_Maintenance_Event, Hours_Since_Last_Maintenance | time and wear indicators (past-only) |
| Data-quality | Any_Sensor_Imputed | at least one sensor in the row was imputed |
| Sensor symptoms | `sens_<key>` × 13 | 1 / 0 / `<NA>` (input imputed); thresholds in `preprocessing_report.md` |
| Observed symptoms | `obs_<key>` × 20, Observed_Symptom_Count | multi-hot of Symptom_Keys; `<NA>` if not recorded |
| Labels | Fault_Code, KBS_Fault_ID, Is_Fault | code (BRG, CAV, …), mapping to `../data/faults.csv` IDs, fault flag |
| Ordinal | Severity_Level (0–4), Priority_Level (0–4) | `<NA>` for Unknown |
| One-hot | `Pump_Type__*`, `Manufacturer__*`, `Diagnostic_Status__*` | 0/1 |
| Split | Partition | train / validation / test, grouped by pump |
| Standardised | `z_<feature>` × 12 | (x − mean_train) / std_train; parameters in `scaler_params.json` |

## 4. Mapping to the existing KBS (`../data/faults.csv`)
| Fault_Type here | KBS_Fault_ID |
|---|---|
| Bearing Failure | F01 |
| Cavitation | F02 |
| Shaft Misalignment | F03 |
| Pump Blockage | F04 / F06 (impeller fouling / suction blockage — merged here) |
| Mechanical Seal Leakage | F05 |
| Dry Running | F07 |
| Motor Fault | F08 / F14 (overload / supply imbalance — merged here) |
| Impeller Damage | F10 |
| Discharge Restriction | F11 |
| Air Ingress | F12 |
| — | F09 Coupling Damage, F13 Base Looseness (not generated) |
