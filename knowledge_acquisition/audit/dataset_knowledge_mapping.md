# Dataset Knowledge Mapping

Part of the KA-1 audit. Examines what the prepared dataset in `data_preparation/` can contribute as knowledge.
Primary source: the cleaned dataset
[cleaned_pump_dataset.csv](../../data_preparation/data/interim/cleaned_pump_dataset.csv) (7,210 rows) and the asset
register [pump_asset_register.csv](../../data_preparation/data/raw/pump_asset_register.csv). The raw file was used only
to confirm vocabulary variants. The processed file was used only for derived indicators, not as a source of
human-readable knowledge.

## 0. The most important caveat — provenance of the dataset
The dataset is **synthetic**. Every relationship in it was written into
[data_preparation/scripts/generate_dataset.py](../../data_preparation/scripts/generate_dataset.py) by this project:

| Knowledge in the data | Where it was authored |
|---|---|
| Fault frequencies; wear faults increase with hours | `FAULT_WEIGHTS`, `WEAR_FAULTS` (lines 38–40) |
| Fault → root-cause lists | `ROOT_CAUSES` (line 42) |
| Inspection findings per fault | `INSPECTION_FINDING` (line 61) |
| Fault → maintenance action (one per fault) | `ACTIONS` (line 75) |
| Downtime/cost medians per fault | `DOWNTIME_MEDIAN`, `COST_MEDIAN` (lines 90–93) |
| Severity from fault intensity; priority from severity | `severity_label`, `priority_for` (lines 120–128) |
| Fault → sensor effects (pump-curve model) | `simulate_reading` (lines 130–198; per fault from line 147) |
| Sensor → recorded symptom thresholds; fault → manual observations | `observed_symptoms` (lines 200–230; `checks` l205, `manual` l221) |
| Misalignment → bearing failure chain | line 265 |

The generator was written *after* the existing KB and was deliberately mapped onto it (`kbs_fault_id` in
[common.py:34-46](../../data_preparation/scripts/common.py#L34-L46)). Therefore:
- Any pattern found in the data is a **re-statement of the generator's assumptions** (source category B). It is
  never independent evidence that a relationship holds on real pumps.
- Agreement between the KB (A) and the dataset (B) means the two project-authored sources are **consistent**; it
  is **not corroboration**.
- The dataset is useful for (i) a controlled vocabulary, (ii) *candidate* relationships to put to an
  engineering source, (iii) consistency checks of the existing rules, and (iv) a test bed. It is **not** useful for
  validating real-world engineering truth.

## 1. Field-by-field classification (cleaned dataset)
Key: **Fact** = directly recorded in the record; **Label** = synthetic ground-truth label; **Derived** = computed
during preparation; **Assoc.** = only meaningful as a statistical association across records.

| Field | Kind | Knowledge category it informs | Usable as | Notes |
|---|---|---|---|---|
| Pump_ID | Fact | 1 Equipment | asset identifier | 40 assets |
| Pump_Type | Fact | 1 Equipment | equipment type | 4 types; authoritative copy in asset register |
| Manufacturer | Fact | 1 Equipment | attribute only | anonymised (Vendor A–D); carries no knowledge |
| Installation_Date, Operating_Hours | Fact | 1 Equipment, 6 Evidence | context, wear indicator | hours monotonic per pump |
| Rated_* (register) | Fact | 1 Equipment, 6 Evidence | reference for relative thresholds | rated flow, Δp, suction, speed, current |
| 11 sensor columns | Fact (value) / Assoc. (pattern) | 6 Evidence | indicator vocabulary + units; ranges per fault are Assoc. | ~1.5–3 % imputed per column (flag `Imputed_Columns`) |
| Observed_Symptoms / Symptom_Keys | Fact (as recorded) | 3 Symptoms, 6 Evidence | symptom vocabulary (20 keys) | ~85 % recording of sensor-visible symptoms; ~3 % false reports in Normal |
| Fault_Type | Label | 4 Faults | fault vocabulary (10 + Normal + Unknown) | merges KB F04/F06 and F08/F14 |
| Root_Cause | Label | 5 Root causes | cause vocabulary (37) + fault→cause pairs | only on Confirmed records; "Under investigation"/"Unknown" otherwise |
| Supporting_Evidence | Fact (text) | 6 Evidence | names of diagnostic *tests/findings* (30 distinct, 3 per fault) | e.g. "Spectrum shows bearing defect frequencies", "NPSH margin calculated below 1 m" |
| Fault_Severity | Label | 9 Severity | per-record degradation level | Low→Critical progression within an episode |
| Diagnostic_Status | Label | 6 Evidence, 10 Rules | certainty of a diagnosis | Confirmed / Suspected / Inconclusive — useful for weighting cases |
| Maintenance_Action | Label | 8 Actions | action vocabulary (13) | one action per fault — no cause dependence |
| Maintenance_Date, Downtime_Hours, Maintenance_Cost | Fact | 8 Actions, 9 Priority | cost/downtime ranges per action | lognormal around authored medians |
| Maintenance_Priority | Label | 9 Priority | priority scale P1–P4 | deterministic function of severity (+ dry running) |
| Label_Missing_In_Source, Imputed_Columns, DQ_Flags … | Derived (data quality) | — | exclusion filters | must be used to exclude rows/values from knowledge extraction |
| Processed: Flow_Pct_Rated, Head_Pct_Rated, Current_Pct_Rated, Speed_Deviation_Pct | Derived | 6 Evidence | proposals for **relative indicators** | <NA> when inputs imputed |
| Processed: `sens_*` (13) | Derived | 3 Symptoms, 6 Evidence | proposed sensor→symptom thresholds | thresholds in [preprocess_dataset.py:27-53](../../data_preparation/scripts/preprocess_dataset.py#L27-L53) — partly cite ISO 10816-3-style zones, not verified (E) |
| Processed: one-hot/ordinal/z-scores/Partition | Derived | — | not knowledge | ML/test convenience only |

## 2. What the dataset contributes per knowledge category
| # | Category | Contribution | Limits |
|---|---|---|---|
| 1 | Equipment | 4 pump types, 40 assets, nameplate ratings, 2- and 4-pole speeds | No fluid, duty, service, motor rating (kW) or installation data |
| 2 | Components | **None directly** — there is no component column | Components appear only inside cause, finding and action text (see `entity_relationship_mapping.md` §1) |
| 3 | Symptoms | 20 recorded symptom keys (19 shared with KB + `noise_high`); 13 sensor-derivable symptoms | KB symptoms `flow_fluctuation`, `base_vibration`, `efficiency_low` absent |
| 4 | Faults | 10 fault types + Normal + Unknown, with record counts | Coarser than KB (merges 4 KB faults into 2); KB F09, F13 absent |
| 5 | Root causes | 37 named causes, 2–4 per fault, with counts on 1,012 Confirmed records | **Causes do not change the recorded symptoms** (see §4) — cause discrimination is impossible from this data |
| 6 | Evidence | Sensor ranges per fault; 30 named inspection findings; diagnostic status | Ranges are generator effects; findings are text only |
| 7 | Relationships | P(symptom recorded \| fault) for 10 faults | Associations, not causation; thresholds of the generator shape them |
| 8 | Maintenance actions | 13 actions, downtime/cost per event | One action per fault; no step sequence; no cause-specific actions |
| 9 | Safety / severity | Per-record severity; priority scale; response lag by priority | No hazard attribute per fault; priority is a generator policy |
| 10 | Rule evidence | A test bed: fires/does-not-fire statistics for existing rules | Consistency check only (see §5) |

## 3. Extracted facts (summary tables)

### 3.1 Equipment (asset register)
| Pump type | Assets | Rated flow (m³/h) | Rated speed (rpm) |
|---|---|---|---|
| End Suction | 20 | 52–220 | 2950 / 1475 |
| Split Case | 7 | 303–868 | 1475 |
| Vertical Inline | 7 | 85–185 | 1475 / 2950 |
| Multistage | 6 | 46–110 | 2950 |

### 3.2 Fault → root cause (Confirmed records, n = 1,012)
| Fault (dataset) | Root causes (count) |
|---|---|
| Bearing Failure | Overload from shaft misalignment 77 · Contaminated lubricant 61 · Bearing fatigue (end of life) 59 · Lubrication deficiency 46 · Unknown 7 |
| Mechanical Seal Leakage | Seal flush failure 54 · Elastomer degradation 54 · Seal face wear 53 · Excessive shaft vibration 50 · Unknown 9 |
| Impeller Damage | Foreign object impact 30 · Cavitation erosion 24 · Corrosion 24 · Abrasive solids erosion 22 · Unknown 2 |
| Cavitation | Partially clogged suction strainer 24 · Operation far right of BEP 22 · Insufficient NPSH available (low suction level) 18 · Elevated liquid temperature 16 · Unknown 6 |
| Shaft Misalignment | Improper installation alignment 25 · Soft foot / foundation settling 19 · Pipe strain 14 · Thermal growth not compensated 14 · Unknown 4 |
| Motor Fault | Motor cooling fan blocked 17 · Overload from high-density fluid 17 · Winding insulation degradation 15 · Supply phase imbalance 12 · Unknown 2 |
| Air Ingress | Leaking suction flange gasket 22 · Vortexing at low sump level 17 · Worn suction-side packing 16 · Unknown 2 |
| Discharge Restriction | Discharge valve partially closed 24 · Check valve stuck 18 · Blocked discharge line 13 |
| Pump Blockage | Debris accumulation in impeller 22 · Scaling / fouling deposits 18 · Clogged suction strainer 8 · Unknown 1 |
| Dry Running | Loss of suction supply (empty tank) 15 · Suction valve closed 12 · Failed priming 10 · Level control failure 8 · Unknown 2 |

The counts reflect uniform random choice in the generator (`rng.choice(ROOT_CAUSES[code])`). They say nothing
about real cause frequencies.

### 3.3 P(symptom recorded | fault), all records with symptoms recorded (Confirmed, Suspected and Unknown-status)
Values ≥ 0.5 in bold. Normal records report `vibration_high` 0.02 and `noise_high` 0.01 (false reports).

| Symptom | Air Ingr. | Bearing | Cavit. | Disch. Restr. | Dry Run | Impeller | Seal | Motor | Blockage | Misalign. | # faults ≥ 0.5 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| air_bubbles | **0.72** | | | | | | | | | | 1 |
| bearing_temp_high | | 0.44 | | | 0.49 | | | | | | 0 |
| coupling_vibration | | 0.25 | | | | | | | | **0.75** | 1 |
| crackling_noise | | | **0.69** | | | | | | | | 1 |
| discharge_pressure_high | | | | **0.88** | | | | | | | 1 |
| discharge_pressure_low | | | 0.45 | | **0.85** | 0.03 | | | 0.03 | | 1 |
| flow_low | **0.58** | | 0.31 | **0.80** | | 0.47 | | 0.01 | **0.84** | | 3 |
| grinding_noise | | **0.62** | | | | 0.18 | | | | | 1 |
| motor_current_high | | | | | | | | 0.37 | | | 0 |
| motor_temp_high | | | | | | | | **0.59** | | | 1 |
| no_flow | | | | 0.01 | **0.92** | | | | | | 1 |
| noise_high | | 0.19 | 0.35 | | 0.15 | | | | | | 0 |
| pressure_fluctuation | **0.84** | | **0.85** | 0.16 | | | | | | | 2 |
| prime_failure | 0.14 | | | | **0.77** | | | | | | 1 |
| rapid_temp_rise | | | | **0.60** | **0.52** | | | | | | 2 |
| seal_leakage | | | | | | | **0.81** | | | | 1 |
| seal_temp_high | | | | | **0.79** | | 0.36 | | | | 1 |
| speed_unstable | | | | | | | | **0.56** | | | 1 |
| suction_pressure_low | | | **0.86** | | **0.79** | | | | | | 2 |
| vibration_high | 0.21 | **0.86** | **0.72** | 0.27 | **0.69** | **0.72** | | 0.22 | 0.07 | **0.85** | 5 |

(Blank = 0.00.) The relationship register in `entity_relationship_mapping.md` §6 uses Confirmed records only, so its values differ slightly. Values below ~0.9 for sensor-visible symptoms partly reflect the generator's 85 % recording rate
and the Low→Critical progression, not engineering.

### 3.4 Maintenance actions — downtime and cost per event (all events)
| Action | Fault | Median downtime (h) | Median cost (USD) |
|---|---|---|---|
| Further investigation scheduled | Unknown | 1.5 | 249 |
| Routine preventive maintenance | Normal | 1.7 | 295 |
| Open or repair discharge valve and clear line | Discharge Restriction | 3.2 | 785 |
| Seal suction-side leaks and re-prime | Air Ingress | 4.8 | 665 |
| Laser realign pump and motor shafts | Shaft Misalignment | 5.1 | 1,007 |
| Clear blockage and clean impeller and strainer | Pump Blockage | 5.2 | 890 |
| Restore suction conditions and clean strainer | Cavitation | 6.4 | 1,161 |
| Replace mechanical seal | Seal Leakage | 8.3 | 3,231 |
| Replace bearings and renew lubrication | Bearing Failure | 11.3 | 2,602 |
| Stop pump, restore liquid supply and re-prime | Dry Running | 13.0 | 4,623 |
| Inspect motor and correct electrical fault | Motor Fault | 22.2 | 4,906 |
| Repair or replace impeller | Impeller Damage | 25.9 | 6,863 |

These are the authored medians (`DOWNTIME_MEDIAN`, `COST_MEDIAN`) plus noise. They give a plausible *ordering*,
not real repair statistics.

### 3.5 Severity and priority
| Severity → priority (all records) | P1 | P2 | P3 | P4 | N/A | Unknown |
|---|---|---|---|---|---|---|
| Critical | 274 | | | | | 7 |
| High | 61 (all Dry Running) | 657 | | | | 16 |
| Medium | | | 1,075 | | | 22 |
| Low | | | | 667 | | 14 |
| No Fault | | | | 110 (preventive maint.) | 4,262 | 2 |

This is a deterministic generator rule ([generate_dataset.py:124-128](../../data_preparation/scripts/generate_dataset.py#L124-L128)):
Critical, or Dry Running at any severity → P1; High → P2; Medium → P3; Low → P4. Median response lag:
P1 1 day, P2 2, P3 6, P4 9. It is a **policy proposal** (B, needs E), not an observed regularity.

## 4. What the dataset can NOT tell us
1. **Cause-specific symptoms.** In the generator, symptoms depend on the fault code only. The one exception is
   the misalignment → bearing-failure chain (line 265). Within Bearing Failure, `coupling_vibration` is recorded in
   0.69 of "Overload from shaft misalignment" records and 0.00 for every other cause. All other within-fault
   differences between causes (e.g. Motor Fault, spread 0.73 in motor_temp_high across causes with n = 12–17) are
   **sampling noise**. **The data cannot support any cause → symptom relationship except that one chain.**
2. **Cause-specific actions.** `ACTIONS` is keyed by fault, so every cause of a fault gets the same action.
3. **Component involvement.** Components are not recorded.
4. **Real thresholds or frequencies.** All thresholds, frequencies, costs and downtimes are authored.
5. **Simultaneous independent faults.** Each record has one primary fault. The 82 Unknown records are blends of two
   faults at low intensity and are useful only as "ambiguous evidence" test cases.

## 5. Consistency of existing rules on the synthetic data (not validation)
How often all of a rule's conditions are recorded together on Confirmed records (n per fault in brackets):

| Rule | Fault | Fires on own fault | Fires on other faults | Interpretation |
|---|---|---|---|---|
| R01 | F01 Bearing (245) | 0.36 | none | consistent |
| R02 | F02 Cavitation (82) | 0.51 | none | consistent |
| R03 | F03 Misalignment (75) | **0.00** | **Bearing Failure 34** | generator's misalignment rarely reaches bearing temp ≥ 80 °C; the pattern matches *misalignment-caused bearing failure* — attribution conflict |
| R04 | F04 | not testable | — | `efficiency_low` not in dataset |
| R05 | F05 Seal (215) | 0.53 | none | consistent |
| R06 | F06 (Pump Blockage, 48) | **0.00** | **Cavitation 23** | R06 pattern describes cavitation in the data — overlap conflict with R02/F02 |
| R07 | F07 Dry Running (46) | 0.35 | none | consistent; limited by manual `rapid_temp_rise` |
| R08 | F08 Motor (63) | 0.40 | Unknown 1 | consistent; cannot separate F08 from F14 (merged in data) |
| R09 | F09 | not testable | — | fault absent |
| R10 | F10 | not testable | — | `efficiency_low` absent |
| R11 | F11 Disch. restr. (54) | 0.56 | none | consistent |
| R12 | F12 | not testable as written | — | `flow_fluctuation` absent from the dataset vocabulary |
| R13 | F13 | not testable | — | fault absent |
| R14 | F14 (Motor Fault, 63) | 0.27 | Unknown 1 | F14 vs F08 not separable in data |

Low firing rates on the own fault are expected for an all-conditions rule when each symptom is recorded with
probability < 1. They do not show that a rule is wrong. The two cross-fault firings (R03, R06) are the signals
worth taking to an engineering source.
