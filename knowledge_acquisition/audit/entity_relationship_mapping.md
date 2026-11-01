# Entity and Relationship Mapping

Part of the KA-1 audit. Maps the existing KB (A) to the synthetic dataset (B) entity by entity, then registers
every candidate relationship with its evidence. Source categories:
- **A** — existing project KB
- **B** — synthetic dataset
- **C** — derived dataset feature
- **D** — existing documented engineering reference (only `docs/SOURCE_NOTES.md`; the KSB pages were *not*
  re-read during this audit, so D means "as summarised there")
- **E** — requires independent engineering validation

A and B are both project-authored, so "A+B" means *consistent*, not *validated*. **Every relationship below
still carries E.**

---

## 1. Equipment and component mapping

### 1.1 Equipment
| Existing KB | Dataset equivalent | Terminology match | Gap / note | Source |
|---|---|---|---|---|
| implicit "centrifugal pump" ([app.py:6](../../src/app.py#L6)) | 40 assets `P-001…P-040` | — | KB has no equipment entity | A, B |
| — | Pump_Type: End Suction, Split Case, Multistage, Vertical Inline | n/a | missing in KB; matters because thresholds and fault likelihood depend on type | B |
| — | Nameplate: rated flow, rated Δp, nominal suction, rated speed, rated current | n/a | missing in KB; needed for relative thresholds | B |
| — | Manufacturer (anonymised) | n/a | attribute only | B |
| implied pump-set boundary (C09 motor, C10 base) | not recorded | — | the boundary must be defined explicitly (pump set vs pump) | A, E |

### 1.2 Components
The dataset has no component field. "Dataset evidence" is where a component is *named* inside root-cause,
finding or action text ([generate_dataset.py:42-89](../../data_preparation/scripts/generate_dataset.py#L42-L89)).

| KB component | Dataset mentions | Match | Note |
|---|---|---|---|
| C01 Pump Casing | "Scale deposits in volute"; "Casing hot to touch" | partial | volute is a casing sub-part |
| C02 Impeller | impeller vanes/inlet, "Repair or replace impeller", debris in impeller | yes | |
| C03 Shaft | "Excessive shaft vibration", "Laser realign pump and motor shafts" | yes | |
| C04 Bearings | bearings, lubricant/oil, outer race | yes | lubricant is a separate item (not in KB) |
| C05 Mechanical Seal | seal faces, elastomers, seal flush line, seal gland | yes | sub-components and flush/support system missing in KB |
| C06 Coupling | "Coupling insert worn unevenly" | yes | KB fault F09 absent from dataset |
| C07 Suction Line / Strainer | suction strainer, suction flange gasket, suction valve, suction-side packing | combined item | KB merges line, strainer and valve; "packing" is new terminology (gland/valve packing — ambiguous) |
| C08 Discharge Line / Valve | discharge valve, discharge line, **check valve** | combined item | check valve not in KB |
| C09 Electric Motor | windings/insulation, cooling fan/cowl | yes | sub-components missing in KB |
| C10 Baseplate / Foundation | "Soft foot / foundation settling" (cause of misalignment) | yes | in B it is a *cause location*, in A the location of fault F13 |
| — | suction tank/sump, level control, power supply, process fluid (density, temperature) | **missing** | external system elements that hold root causes (dry running, cavitation, motor overload) |
| — | instrumentation (sight glass, vibration spectrum, oil sample) | **missing** | evidence *sources*, not components |
| — | wear rings | missing in both | common centrifugal-pump wear part — external research needed (E) |

## 2. Symptom mapping
| KB key (symptoms.csv line) | KB name | Dataset recorded phrase / key | Dataset sensor indicator (C) | Match |
|---|---|---|---|---|
| vibration_high (2) | High overall vibration | "High vibration" / vibration_high | `sens_vibration_high` > 4.5 mm/s | key same; **threshold differs** (KB 6.0) |
| bearing_temp_high (3) | Bearing temperature high | "High bearing temperature" | ≥ 80 °C | same |
| grinding_noise (4) | Abnormal grinding/rumbling noise | "Grinding noise" | — | same key; dataset variants "Rumbling noise", "grinding sound" |
| crackling_noise (5) | Crackling / gravel-like noise | "Crackling noise" | — | same key |
| discharge_pressure_low (6) | Low discharge pressure | "Low discharge pressure" | head < 85 % rated | **definition differs** (KB absolute < 4.2 bar) |
| flow_low (7) | Low flow rate | "Low flow" | 10–75 % rated | KB: % of *baseline*; dataset: % of *rating* |
| suction_pressure_low (8) | Low suction pressure / high vacuum | "Low suction pressure" | < 0.8 bar(a) | threshold differs (KB 0.70) |
| seal_leakage (9) | Visible seal leakage | "Visible seal leakage" | — | same |
| motor_current_high (10) | Motor current high | "High motor current" | > 110 % rated | **definition differs** (KB absolute > 38 A) |
| motor_temp_high (11) | Motor temperature high | "High motor temperature" | ≥ 95 °C | threshold differs (KB 80) |
| pressure_fluctuation (12) | Pressure fluctuating | "Pressure fluctuating" | ≥ 10 % | same threshold as KB |
| flow_fluctuation (13) | Flow fluctuating | **absent** | — | KB-only; not independently observable in the KB app either |
| no_flow (14) | No / near-zero flow | "No flow" | < 10 % rated | same |
| prime_failure (15) | Pump fails to prime | "Loss of prime" | — | equivalent, different name |
| coupling_vibration (16) | Shaft/coupling vibration dominant | "Coupling vibration" | — | equivalent |
| seal_temp_high (17) | Seal area temperature high | "High seal temperature" | ≥ 80 °C | threshold differs (KB 85) |
| discharge_pressure_high (18) | Discharge pressure unusually high | "High discharge pressure" | head > 115 % rated | **definition differs** (KB absolute > 6.0 bar) |
| speed_unstable (19) | Motor speed unstable | "Motor speed unstable" | `speed_deviation` (|Δ| > 1.5 %) | the sensor indicator measures *deviation*, not *instability* — not equivalent |
| base_vibration (20) | Localized baseplate vibration | **absent** | — | KB-only (F13 not generated) |
| air_bubbles (21) | Air bubbles / frothy discharge | "Air bubbles in discharge" | — | equivalent |
| efficiency_low (22) | Efficiency / developed head reduced | **absent** | `Current_per_Flow_Index` (C) is a possible proxy | KB-only; overlaps discharge_pressure_low |
| rapid_temp_rise (23) | Rapid temperature rise with low flow | "Rapid temperature rise" | — | dataset drops "with low flow" |
| — | — | "High noise level" / noise_high | > 85 dB(A) | **dataset-only**; KB has noise only as grinding/crackling |

Equivalent symptoms with different names: prime_failure ↔ "Loss of prime"; coupling_vibration ↔ "Shaft/coupling
vibration dominant"; rapid_temp_rise ↔ "…with low flow". There are no true duplicates inside either vocabulary, but
`flow_fluctuation` ≈ `pressure_fluctuation` (co-derived in the KB) and `efficiency_low` ≈ `discharge_pressure_low`
(head) are near-duplicates.

## 3. Fault mapping
| KB fault (faults.csv line) | Dataset label | Match | Note |
|---|---|---|---|
| F01 Bearing Wear / Failure (2) | Bearing Failure | equivalent | "Wear" vs "Failure" — severity stage differs |
| F02 Cavitation (3) | Cavitation | same | |
| F03 Shaft Misalignment (4) | Shaft Misalignment | same | |
| F04 Impeller Blockage / Fouling (5) | Pump Blockage | **merged** | dataset merges F04 + F06 |
| F05 Mechanical Seal Failure (6) | Mechanical Seal Leakage | equivalent | "Leakage" is a symptom-level name; "Failure" a fault-level name |
| F06 Suction Blockage / Clogged Strainer (7) | Pump Blockage (+ cause "Clogged suction strainer"; also a *cause* of Cavitation) | **level conflict** | KB treats it as a fault; B as a cause of two faults |
| F07 Dry Running / Loss of Prime (8) | Dry Running | equivalent | |
| F08 Motor Overload (9) | Motor Fault | **merged** | dataset merges F08 + F14; cause "Overload from high-density fluid" |
| F09 Coupling Damage / Looseness (10) | — | **missing in B** | no data |
| F10 Impeller Damage / Erosion (11) | Impeller Damage | equivalent | |
| F11 Discharge Restriction / Closed Valve (12) | Discharge Restriction | equivalent | "Closed valve" is a cause in B |
| F12 Air Ingress on Suction Side (13) | Air Ingress | equivalent | |
| F13 Base / Foundation Looseness (14) | — | **missing in B** | B has "Soft foot / foundation settling" only as a cause of misalignment |
| F14 Electrical Supply Imbalance (15) | Motor Fault | **merged / level conflict** | B has "Supply phase imbalance" as a cause of Motor Fault |
| — | Unknown | dataset-only | needed as an explicit "no conclusion" outcome |
| — | Normal | dataset-only | needed as an explicit healthy state |

## 4. Shared and weakly discriminating symptoms
| Symptom | KB faults linked | B: faults with P ≥ 0.5 | Assessment |
|---|---|---|---|
| vibration_high | 10 (F01, F02, F03, F04, F05, F08, F09, F10, F13, F14) | 5 | **non-discriminative alone**; useful only in combination |
| flow_low | 7 | 3 | weak alone; direction of head change needed (rated-relative head, C) |
| efficiency_low | 6 | n/a | weak and overlaps head |
| motor_current_high | 6 | 0 | weak; direction depends on pump characteristic (see conflicts) |
| grinding_noise | 6 | 1 | weak in A, specific in B (bearing) — disagreement |
| bearing_temp_high | 5 | 0 | moderate |
| discharge_pressure_low | 5 | 1 | moderate |
| pressure_fluctuation | 2 | 2 | separates {F02, F12} from the rest; needs crackling vs bubbles to separate them |
| suction_pressure_low | 2 | 2 | {F02, F06} in A; {Cavitation, Dry Running} in B |
| seal_leakage, air_bubbles, no_flow, discharge_pressure_high, base_vibration | 1 each | 1 each | **highly specific** — best rule anchors |

Faults with insufficient discriminating evidence in the KB:
- **F08 vs F14.** They share their two strongest symptoms; only `speed_unstable` (manual) separates them.
- **F04 vs F10 vs F06.** The same hydraulic symptoms; R04 ⊂ R10.
- **F03 vs F09 vs F13.** All rest on `coupling_vibration` or `base_vibration`, which are manual observations
  without a defined test.
- **F06 vs F02.** R06's three conditions are all F02 links.

## 5. Root-cause acquisition

### 5.1 Fault → root cause
Columns:
- **A evidence:** text in the KB that names or implies the cause.
- **B:** count on Confirmed records ([generate_dataset.py:42](../../data_preparation/scripts/generate_dataset.py#L42)).
- **D:** SOURCE_NOTES line.

| Fault | Root cause | A evidence | B | D | Status |
|---|---|---|---|---|---|
| Bearing (F01) | Lubrication deficiency | F01 "lubrication-related distress" (faults.csv:2); A01 lubricant level (maint:2) | 46 | SN:5 lists lubrication among routine checks (maintenance, not causation) | **A+B** → E |
| Bearing (F01) | Contaminated lubricant | A01 "lubricant… condition" (maint:2) | 61 | — | A (implied)+B → E |
| Bearing (F01) | Bearing fatigue (end of life) | "progressive bearing damage" (faults.csv:2) | 59 | — | A (implied)+B → E |
| Bearing (F01) | Overload from shaft misalignment | F03 weight on bearing_temp_high (weights:17) suggests link | 77 | — | B; A only implicit → E |
| Cavitation (F02) | Insufficient NPSH available (low suction level) | "inadequate suction conditions" (faults.csv:3); A03 "verify NPSH margin… liquid level" (maint:4) | 18 | SN:11 low-flow operation can cause cavitation (different cause) | **A+B** → E |
| Cavitation (F02) | Partially clogged suction strainer | A03 "suction piping restrictions" (maint:4); F06 exists as a fault | 24 | — | A+B, **level conflict** with F06 → E |
| Cavitation (F02) | Elevated liquid temperature | A03 "temperature" (maint:4) | 16 | — | A+B → E |
| Cavitation (F02) | Operation far right of BEP | — | 22 | — | B only → E |
| Cavitation (F02) | Low-flow operation | — | — | SN:11 ("unfavourable low-flow ranges can cause … cavitation") | **D only** → E |
| Misalignment (F03) | Soft foot / foundation settling | A05 "after verifying soft foot" (maint:6); F13 description (faults.csv:14) | 19 | SN:5 alignment checks | **A+B** → E |
| Misalignment (F03) | Pipe strain | A05 "pipe strain" (maint:6) | 14 | — | **A+B** → E |
| Misalignment (F03) | Improper installation alignment | — | 25 | — | B only → E |
| Misalignment (F03) | Thermal growth not compensated | — | 14 | — | B only → E |
| Blockage (F04) | Debris / foreign material | "foreign material" (faults.csv:5) | 22 | — | **A+B** → E |
| Blockage (F04) | Scaling / fouling deposits | "deposits" (faults.csv:5) | 18 | — | **A+B** → E |
| Blockage (F06) | Clogged suction strainer | F06 name (faults.csv:7); A08 (maint:9) | 8 | — | A (as fault) + B (as cause) → E |
| Seal (F05) | Seal face wear | "seal faces … worn" (faults.csv:6) | 53 | SN:5 shaft-seal checks | **A+B** → E |
| Seal (F05) | Elastomer degradation | "elastomers … damaged" (faults.csv:6); A07 (maint:8) | 54 | — | **A+B** → E |
| Seal (F05) | Seal flush failure | A07 "flush plan" (maint:8) | 54 | — | **A+B** → E |
| Seal (F05) | Excessive shaft vibration | F05 weight on vibration_high (weights:27) — direction unclear | 50 | — | B; A ambiguous → E |
| Seal (F05) | Thermal distress (e.g. dry running) | "thermally distressed" (faults.csv:6) | — (DRY finding "Seal faces heat-checked") | SN:8 dry running → overheating | A+D (partial) → E |
| Dry running (F07) | Insufficient liquid / loss of supply | "insufficient liquid" (faults.csv:8); A09 (maint:10) | 15 | **SN:8** insufficient liquid | **A+B+D** → E |
| Dry running (F07) | Failed priming / loss of prime | F07 name; A09 "why prime was lost" | 10 | — | **A+B** → E |
| Dry running (F07) | Suction valve closed | A08 "verify suction valve is open" (for F06, maint:9) | 12 | — | B; A indirect → E |
| Dry running (F07) | Level control failure | — | 8 | — | B only → E |
| Motor overload (F08) | Process overload / mechanical drag | A10 (maint:11) | 17 ("high-density fluid") | — | **A+B** (partial) → E |
| Motor (F14) | Supply phase imbalance | F14 description (faults.csv:15); A16 | 12 | — | **A+B**, level conflict (fault vs cause) → E |
| Motor (F08/F14) | Winding insulation degradation | — | 15 | — | B only → E |
| Motor (F08/F14) | Cooling fan blocked | — | 17 | — | B only → E |
| Coupling (F09) | Flexible element wear / looseness | faults.csv:10; A11 | — | SN:5 flexible coupling elements | A+D (maintenance check) → E |
| Impeller (F10) | Cavitation erosion | A04 "Inspect impeller for cavitation erosion" (maint:5) | 24 | SN:5 cavitation/erosion inspection | **A+B** → E |
| Impeller (F10) | Abrasive solids erosion | "eroded" (faults.csv:11) | 22 | — | A (implied)+B → E |
| Impeller (F10) | Foreign object impact | "mechanically damaged" (faults.csv:11) | 30 | — | A (implied)+B → E |
| Impeller (F10) | Corrosion | — | 24 | — | B only → E |
| Discharge restr. (F11) | Discharge valve (partially) closed | F11 name; A13 (maint:14) | 24 | — | **A+B** → E |
| Discharge restr. (F11) | Blocked discharge line | "discharge-side restriction" (faults.csv:12) | 13 | — | A+B → E |
| Discharge restr. (F11) | Check valve stuck | — | 18 | — | B only → E |
| Air ingress (F12) | Leaking suction flange gasket / fittings | "suction piping or fittings" (faults.csv:13); A14 gaskets | 22 | — | **A+B** → E |
| Air ingress (F12) | Vortexing at low sump level | — | 17 | — | B only → E |
| Air ingress (F12) | Worn suction-side packing | — | 16 | — | B only; terminology unclear → E |
| Base (F13) | Loose hold-down bolts / soft foot / weak foundation | faults.csv:14; A15 | — | — | A only → E |

### 5.2 Fault-as-cause chains (a fault that causes another fault)
| Chain | A | B | Status |
|---|---|---|---|
| Cavitation → Impeller damage (erosion) | A04 (maint:5) | cause "Cavitation erosion" (24) | A+B → E |
| Shaft misalignment → Bearing failure | F03 bearing_temp link (weights:17) | cause + signature (77; coupling_vibration 0.69) | A (implicit)+B → E |
| Excessive vibration → Seal failure | — | cause "Excessive shaft vibration" (50) | B only → E |
| Dry running → Seal damage | "thermally distressed" (faults.csv:6) | finding "Seal faces heat-checked" | A+B (+SN:8 overheating) → E |
| Clogged suction strainer → Cavitation / Blockage | F06 + A03 | cause of both (24, 8) | A+B → E |
| Base looseness / soft foot → Misalignment | A05, F13 | cause (19) | A+B → E |
| Discharge restriction → low-flow operation → temperature rise / vibration / cavitation | F11 links | — | **SN:11** → D, E |

The knowledge model must therefore allow a **fault to act as the cause of another fault**.

### 5.3 Root cause → affected component (inferred from cause wording; nothing records it directly)
| Root cause | Component (KB id) | Basis |
|---|---|---|
| Lubrication deficiency, contaminated lubricant, fatigue | C04 (+ lubricant, new) | inferred from wording |
| Seal face wear, elastomer degradation | C05 | inferred |
| Seal flush failure | seal support system (**new**) | inferred |
| Insufficient NPSH / low level, vortexing, level control failure, loss of supply | suction tank/sump (**new, external**) | inferred |
| Clogged strainer, suction valve closed, flange gasket leak | C07 | inferred |
| Discharge valve closed, blocked line, check valve stuck | C08 (+ check valve, new) | inferred |
| Soft foot / foundation settling | C10 | inferred |
| Pipe strain | C07 / C08 piping | inferred |
| Improper alignment, thermal growth | C03 / C06 | inferred |
| Winding insulation, cooling fan | C09 sub-components (**new**) | inferred |
| Supply phase imbalance | power supply (**new, external**) | inferred |
| High-density fluid, elevated liquid temperature, operation right of BEP | process / operating point (**new, external**) | inferred |
| Cavitation erosion, abrasive erosion, foreign object, corrosion, debris, scaling | C02 (and C01 volute) | inferred |

All rows are **inferred** and need E.

### 5.4 Root cause → observable symptoms
**Not established.** Only one cause has a distinguishing signature in any source: *Overload from shaft
misalignment* → coupling_vibration (B, generator line 265). The candidate cause-level indicators below exist only as
*inspection findings / tests* (B text, plus A action details). They are tests to confirm a cause, not symptoms:

| Cause | Confirming test / finding (B, `INSPECTION_FINDING` line 61; A where noted) |
|---|---|
| Lubrication problems | oil sample with metal particles; A01 lubricant check |
| Bearing fatigue | vibration spectrum with bearing defect frequencies; outer-race spalling |
| Insufficient NPSH | NPSH margin calculation; A03 "verify NPSH margin" |
| Clogged strainer | strainer differential pressure high |
| Misalignment / soft foot | laser alignment check; 2× running-speed vibration; A05 |
| Seal flush failure | seal flush line inspection |
| Suction-side air leak | soap test at suction flange; vortex at sump |
| Discharge valve | valve position check (A13) |
| Phase imbalance | phase current imbalance measurement (A16) |
| Winding degradation | insulation resistance test |

### 5.5 Root cause → maintenance action
**Not established in B** (actions keyed by fault, line 75). Only these are explicit in A:

| Cause | Action text in A |
|---|---|
| Lubrication | A01 inspect lubrication (maint:2) |
| NPSH / liquid level / suction losses / temperature | A03 (maint:4) |
| Soft foot, pipe strain (verify before aligning) | A05 (maint:6) |
| Clogged strainer / closed suction valve | A08 (maint:9) |
| Loss of liquid supply / prime | A09 (maint:10) |
| Process overload, mechanical drag | A10 (maint:11) |
| Discharge valve closed / no minimum-flow path | A13 (maint:14) |
| Suction fittings / gaskets | A14 (maint:15) |
| Hold-down bolts, soft foot, foundation | A15 (maint:16) |
| Phase imbalance, connections | A16 (maint:17) |

Causes not covered by these texts (e.g. corrosion, check valve stuck, winding degradation, cooling fan blocked, level control failure, vortexing) have no documented corrective action and need E.

---

## 6. Diagnostic relationship register (fault → symptom)
Generated from [symptom_fault_weights.csv](../../data/symptom_fault_weights.csv),
[rules.json](../../data/rules.json) and the cleaned dataset (Confirmed records with symptoms recorded). Columns:
- **Relationship:** always `Fault —manifests_as→ Symptom`.
- **Direct/inferred:** *direct* when stated in A; *inferred* when only associated in B.
- **Uncertainty:** every link is **uncertain**. None is deterministic: no symptom is always present, and none is
  present for only one fault in every case.

Status:
- **A+B consistent:** a KB weight exists and P ≥ 0.2 in B.
- **A only:** not testable in B (fault or symptom absent), or 0.05 ≤ P < 0.2.
- **Conflict:** a KB weight exists but P < 0.05 in B.
- **B only — candidate:** P ≥ 0.2 without a KB weight.

No confidence values are assigned. KB weights are reported as stored; they are not evidence.

| Fault (KB) | Symptom | KB weight (symptom_fault_weights.csv line) | In KB rule | B: P(recorded | fault) | B generator source (generate_dataset.py) | D (SOURCE_NOTES.md line) | Status | Det./uncertain | Source categories |
|---|---|---|---|---|---|---|---|---|---|
| F01 Bearing Wear / Failure | vibration_high | 5 (l2) | R01 | 0.87 | BRG l147 |  | A+B consistent | uncertain | A, B, E |
| F01 Bearing Wear / Failure | bearing_temp_high | 5 (l3) | R01 | 0.60 | BRG l147 |  | A+B consistent | uncertain | A, B, E |
| F01 Bearing Wear / Failure | grinding_noise | 4 (l4) | R01 | 0.70 | BRG l147 |  | A+B consistent | uncertain | A, B, E |
| F01 Bearing Wear / Failure | motor_current_high | 2 (l5) |  | 0.00 |  |  | **Conflict A vs B** | uncertain | A, E |
| F01 Bearing Wear / Failure | efficiency_low | 1 (l6) |  | symptom not in dataset |  |  | A only (not testable in B) | uncertain | A, E |
| F01 Bearing Wear / Failure | coupling_vibration | — |  | 0.22 | BRG l147 |  | B only — candidate | uncertain | B, E |
| F01 Bearing Wear / Failure | noise_high | — |  | 0.29 | BRG l147 |  | B only — candidate | uncertain | B, E |
| F02 Cavitation | crackling_noise | 5 (l7) | R02 | 0.78 | CAV l149 |  | A+B consistent | uncertain | A, B, E |
| F02 Cavitation | vibration_high | 4 (l8) |  | 0.79 | CAV l149 |  | A+B consistent | uncertain | A, B, E |
| F02 Cavitation | discharge_pressure_low | 3 (l9) |  | 0.56 | CAV l149 |  | A+B consistent | uncertain | A, B, E |
| F02 Cavitation | flow_low | 3 (l10) |  | 0.46 | CAV l149 |  | A+B consistent | uncertain | A, B, E |
| F02 Cavitation | suction_pressure_low | 5 (l11) | R02 | 0.83 | CAV l149 |  | A+B consistent | uncertain | A, B, E |
| F02 Cavitation | pressure_fluctuation | 4 (l12) | R02 | 0.84 | CAV l149 |  | A+B consistent | uncertain | A, B, E |
| F02 Cavitation | flow_fluctuation | 4 (l13) |  | symptom not in dataset |  |  | A only (not testable in B) | uncertain | A, E |
| F02 Cavitation | efficiency_low | 3 (l14) |  | symptom not in dataset |  |  | A only (not testable in B) | uncertain | A, E |
| F02 Cavitation | noise_high | — |  | 0.51 | CAV l149 |  | B only — candidate | uncertain | B, E |
| F03 Shaft Misalignment | vibration_high | 5 (l15) | R03 | 0.84 | MIS l157 |  | A+B consistent | uncertain | A, B, E |
| F03 Shaft Misalignment | coupling_vibration | 5 (l16) | R03 | 0.85 | MIS l157 |  | A+B consistent | uncertain | A, B, E |
| F03 Shaft Misalignment | bearing_temp_high | 3 (l17) | R03 | 0.00 |  |  | **Conflict A vs B** | uncertain | A, E |
| F03 Shaft Misalignment | motor_current_high | 2 (l18) |  | 0.00 |  |  | **Conflict A vs B** | uncertain | A, E |
| F03 Shaft Misalignment | grinding_noise | 2 (l19) |  | 0.00 |  |  | **Conflict A vs B** | uncertain | A, E |
| F04 Impeller Blockage / Fouling | flow_low | 5 (l20) | R04 | 0.83 | BLK l159 |  | A+B consistent | uncertain | A, B, E |
| F04 Impeller Blockage / Fouling | discharge_pressure_low | 4 (l21) | R04 | 0.04 |  |  | **Conflict A vs B** | uncertain | A, E |
| F04 Impeller Blockage / Fouling | efficiency_low | 5 (l22) | R04 | symptom not in dataset |  |  | A only (not testable in B) | uncertain | A, E |
| F04 Impeller Blockage / Fouling | vibration_high | 2 (l23) |  | 0.23 | BLK l159 |  | A+B consistent | uncertain | A, B, E |
| F04 Impeller Blockage / Fouling | motor_current_high | 2 (l24) |  | 0.00 |  |  | **Conflict A vs B** | uncertain | A, E |
| F05 Mechanical Seal Failure | seal_leakage | 5 (l25) | R05 | 0.87 | SEAL l153 |  | A+B consistent | uncertain | A, B, E |
| F05 Mechanical Seal Failure | seal_temp_high | 4 (l26) | R05 | 0.59 | SEAL l153 |  | A+B consistent | uncertain | A, B, E |
| F05 Mechanical Seal Failure | vibration_high | 2 (l27) |  | 0.00 |  |  | **Conflict A vs B** | uncertain | A, E |
| F05 Mechanical Seal Failure | bearing_temp_high | 1 (l28) |  | 0.00 |  |  | **Conflict A vs B** | uncertain | A, E |
| F06 Suction Blockage / Clogged Strainer | suction_pressure_low | 5 (l29) | R06 | 0.00 |  |  | **Conflict A vs B** | uncertain | A, E |
| F06 Suction Blockage / Clogged Strainer | flow_low | 5 (l30) | R06 | 0.83 | BLK l159 |  | A+B consistent | uncertain | A, B, E |
| F06 Suction Blockage / Clogged Strainer | discharge_pressure_low | 4 (l31) | R06 | 0.04 |  |  | **Conflict A vs B** | uncertain | A, E |
| F06 Suction Blockage / Clogged Strainer | crackling_noise | 2 (l32) |  | 0.00 |  |  | **Conflict A vs B** | uncertain | A, E |
| F06 Suction Blockage / Clogged Strainer | efficiency_low | 3 (l33) |  | symptom not in dataset |  |  | A only (not testable in B) | uncertain | A, E |
| F06 Suction Blockage / Clogged Strainer | vibration_high | — |  | 0.23 | BLK l159 |  | B only — candidate | uncertain | B, E |
| F07 Dry Running / Loss of Prime | no_flow | 5 (l34) | R07 | 0.89 | DRY l162 |  | A+B consistent | uncertain | A, B, E |
| F07 Dry Running / Loss of Prime | prime_failure | 5 (l35) | R07 | 0.80 | DRY l162 |  | A+B consistent | uncertain | A, B, E |
| F07 Dry Running / Loss of Prime | rapid_temp_rise | 5 (l36) | R07 | 0.50 | DRY l162 | SN l8 overheating | A+B consistent | uncertain | A, B, D, E |
| F07 Dry Running / Loss of Prime | seal_temp_high | 4 (l37) |  | 0.78 | DRY l162 | SN l8 overheating | A+B consistent | uncertain | A, B, D, E |
| F07 Dry Running / Loss of Prime | bearing_temp_high | 3 (l38) |  | 0.61 | DRY l162 | SN l8 overheating | A+B consistent | uncertain | A, B, D, E |
| F07 Dry Running / Loss of Prime | grinding_noise | 2 (l39) |  | 0.00 |  |  | **Conflict A vs B** | uncertain | A, E |
| F07 Dry Running / Loss of Prime | discharge_pressure_low | — |  | 0.89 | DRY l162 |  | B only — candidate | uncertain | B, E |
| F07 Dry Running / Loss of Prime | suction_pressure_low | — |  | 0.78 | DRY l162 |  | B only — candidate | uncertain | B, E |
| F07 Dry Running / Loss of Prime | vibration_high | — |  | 0.78 | DRY l162 | SN l8 vibration | B only — candidate | uncertain | B, D, E |
| F08 Motor Overload | motor_current_high | 5 (l40) | R08 | 0.56 | MOT l170 |  | A+B consistent | uncertain | A, B, E |
| F08 Motor Overload | motor_temp_high | 5 (l41) | R08 | 0.57 | MOT l170 |  | A+B consistent | uncertain | A, B, E |
| F08 Motor Overload | vibration_high | 2 (l42) |  | 0.37 | MOT l170 |  | A+B consistent | uncertain | A, B, E |
| F08 Motor Overload | speed_unstable | 2 (l43) |  | 0.57 | MOT l170 |  | A+B consistent | uncertain | A, B, E |
| F08 Motor Overload | flow_low | 1 (l44) |  | 0.00 |  |  | **Conflict A vs B** | uncertain | A, E |
| F09 Coupling Damage / Looseness | coupling_vibration | 5 (l45) | R09 | fault not in dataset |  |  | A only (not testable in B) | uncertain | A, E |
| F09 Coupling Damage / Looseness | vibration_high | 4 (l46) |  | fault not in dataset |  |  | A only (not testable in B) | uncertain | A, E |
| F09 Coupling Damage / Looseness | grinding_noise | 3 (l47) | R09 | fault not in dataset |  |  | A only (not testable in B) | uncertain | A, E |
| F09 Coupling Damage / Looseness | bearing_temp_high | 2 (l48) |  | fault not in dataset |  |  | A only (not testable in B) | uncertain | A, E |
| F10 Impeller Damage / Erosion | vibration_high | 4 (l49) | R10 | 0.73 | IMP l155 |  | A+B consistent | uncertain | A, B, E |
| F10 Impeller Damage / Erosion | flow_low | 4 (l50) | R10 | 0.58 | IMP l155 |  | A+B consistent | uncertain | A, B, E |
| F10 Impeller Damage / Erosion | discharge_pressure_low | 4 (l51) | R10 | 0.07 |  |  | A only | uncertain | A, E |
| F10 Impeller Damage / Erosion | efficiency_low | 5 (l52) | R10 | symptom not in dataset |  |  | A only (not testable in B) | uncertain | A, E |
| F10 Impeller Damage / Erosion | grinding_noise | 2 (l53) |  | 0.15 |  |  | A only | uncertain | A, E |
| F11 Discharge Restriction / Closed Valve | discharge_pressure_high | 5 (l54) | R11 | 0.87 | DIS l167 |  | A+B consistent | uncertain | A, B, E |
| F11 Discharge Restriction / Closed Valve | flow_low | 5 (l55) | R11 | 0.78 | DIS l167 |  | A+B consistent | uncertain | A, B, E |
| F11 Discharge Restriction / Closed Valve | rapid_temp_rise | 4 (l56) | R11 | 0.78 | DIS l167 | SN l11 low-flow → temperature rise | A+B consistent | uncertain | A, B, D, E |
| F11 Discharge Restriction / Closed Valve | motor_current_high | 2 (l57) |  | 0.00 |  |  | **Conflict A vs B** | uncertain | A, E |
| F11 Discharge Restriction / Closed Valve | efficiency_low | 2 (l58) |  | symptom not in dataset |  |  | A only (not testable in B) | uncertain | A, E |
| F11 Discharge Restriction / Closed Valve | pressure_fluctuation | — |  | 0.30 | DIS l167 |  | B only — candidate | uncertain | B, E |
| F11 Discharge Restriction / Closed Valve | vibration_high | — |  | 0.46 | DIS l167 | SN l11 low-flow → vibration | B only — candidate | uncertain | B, D, E |
| F12 Air Ingress on Suction Side | air_bubbles | 5 (l59) | R12 | 0.75 | AIR l164 |  | A+B consistent | uncertain | A, B, E |
| F12 Air Ingress on Suction Side | prime_failure | 3 (l60) |  | 0.16 |  |  | A only | uncertain | A, E |
| F12 Air Ingress on Suction Side | flow_fluctuation | 4 (l61) | R12 | symptom not in dataset |  |  | A only (not testable in B) | uncertain | A, E |
| F12 Air Ingress on Suction Side | pressure_fluctuation | 4 (l62) | R12 | 0.86 | AIR l164 |  | A+B consistent | uncertain | A, B, E |
| F12 Air Ingress on Suction Side | discharge_pressure_low | 3 (l63) |  | 0.00 |  |  | **Conflict A vs B** | uncertain | A, E |
| F12 Air Ingress on Suction Side | flow_low | 3 (l64) |  | 0.65 | AIR l164 |  | A+B consistent | uncertain | A, B, E |
| F12 Air Ingress on Suction Side | vibration_high | — |  | 0.37 | AIR l164 |  | B only — candidate | uncertain | B, E |
| F13 Base / Foundation Looseness | base_vibration | 5 (l65) | R13 | fault not in dataset |  |  | A only (not testable in B) | uncertain | A, E |
| F13 Base / Foundation Looseness | vibration_high | 4 (l66) | R13 | fault not in dataset |  |  | A only (not testable in B) | uncertain | A, E |
| F13 Base / Foundation Looseness | coupling_vibration | 2 (l67) |  | fault not in dataset |  |  | A only (not testable in B) | uncertain | A, E |
| F13 Base / Foundation Looseness | grinding_noise | 1 (l68) |  | fault not in dataset |  |  | A only (not testable in B) | uncertain | A, E |
| F14 Electrical Supply Imbalance | motor_temp_high | 5 (l69) | R14 | 0.57 | MOT l170 |  | A+B consistent | uncertain | A, B, E |
| F14 Electrical Supply Imbalance | motor_current_high | 4 (l70) | R14 | 0.56 | MOT l170 |  | A+B consistent | uncertain | A, B, E |
| F14 Electrical Supply Imbalance | speed_unstable | 4 (l71) | R14 | 0.57 | MOT l170 |  | A+B consistent | uncertain | A, B, E |
| F14 Electrical Supply Imbalance | vibration_high | 2 (l72) |  | 0.37 | MOT l170 |  | A+B consistent | uncertain | A, B, E |

Summary: 81 relationships — 37 A+B consistent, 19 A only, **15 conflicts**, 10 B-only candidates. Conflicts and
candidates are analysed in `knowledge_gaps_and_conflicts.md`.

## 7. Maintenance and safety mapping

### 7.1 Fault → recommended action
| KB fault | KB action(s) (A) | Dataset action (B) | Agreement |
|---|---|---|---|
| F01 | A01 inspect lubrication → A02 replace bearing | Replace bearings and renew lubrication | B skips the inspection step |
| F02 | A03 restore suction / NPSH → A04 inspect impeller | Restore suction conditions and clean strainer | B adds strainer cleaning (overlaps F06/A08) |
| F03 | A05 laser/dial align | Laser realign pump and motor shafts | same |
| F04 | A06 clean impeller | Clear blockage and clean impeller and strainer | merged with F06 |
| F05 | A07 inspect/replace seal | Replace mechanical seal | B skips inspection |
| F06 | A08 clean strainer | (merged into Blockage action) | merged |
| F07 | A09 stop pump, restore prime/supply | Stop pump, restore liquid supply and re-prime | same |
| F08 | A10 inspect motor load / operating point | Inspect motor and correct electrical fault | **different emphasis** (load vs electrical) |
| F09 | A11 coupling elements | — | B missing |
| F10 | A12 inspect/repair/replace impeller | Repair or replace impeller | same |
| F11 | A13 open valve / minimum-flow path | Open or repair discharge valve and clear line | same |
| F12 | A14 leak-test suction piping | Seal suction-side leaks and re-prime | B adds re-prime |
| F13 | A15 bolts / soft foot / foundation | — | B missing |
| F14 | A16 phase balance (qualified personnel) | Inspect motor and correct electrical fault | merged |
| Unknown | — | Further investigation scheduled | B only |
| Normal | — | Routine preventive maintenance (~2,000 h interval, B policy) | B only |

### 7.2 Severity → safety priority
Two different concepts are present and must stay separate:
- **Hazard class of a fault type.** A: `safety_priority` LOW–CRITICAL, static per fault
  ([faults.csv](../../data/faults.csv) col 4). Only F07 is CRITICAL; F04 and F13 are MEDIUM; the rest are HIGH.
- **Severity of a case.** B: `Fault_Severity` Low–Critical per record, from fault progression.
- **Maintenance priority** P1–P4 (B) is a deterministic function of severity, with dry running always P1
  ([generate_dataset.py:124-128](../../data_preparation/scripts/generate_dataset.py#L124-L128)). It is a policy
  proposal → E.

### 7.3 Action → downtime / cost
| | A | B |
|---|---|---|
| Granularity | qualitative LOW/MEDIUM/HIGH per **fault** (faults.csv) and per **action** (maintenance_actions.csv) | numeric per **event** (median per action in `dataset_knowledge_mapping.md` §3.4) |
| Agreement on ordering | impeller damage most expensive/longest in both; discharge restriction cheapest in both | |
| Disagreements | KB motor faults Medium downtime vs B second-longest (22 h); KB dry-running cost Medium vs B second-highest; KB air ingress downtime Medium vs B low (4.8 h) | → `knowledge_gaps_and_conflicts.md` |

Both are authored assumptions; neither is evidence (E).

### 7.4 Critical conditions requiring immediate action — documented statements only
| Condition | Statement | Source |
|---|---|---|
| Dry running | "Do not continue dry operation" | A: A09 ([maint:10](../../data/maintenance_actions.csv#L10)) |
| Dry running (top-ranked CRITICAL) | "stop/secure equipment according to site procedures" | A: [app.py:70](../../src/app.py#L70) |
| Dry running | dry-running protection may be required | D: [SOURCE_NOTES.md:8](../../docs/SOURCE_NOTES.md#L8) |
| Near-zero-flow operation | "avoid prolonged near-zero-flow operation" | A: A13 ([maint:14](../../data/maintenance_actions.csv#L14)) |
| Internal work (impeller, blockage) | isolate the pump before opening | A: A06, A12 ([maint:7](../../data/maintenance_actions.csv#L7), [:13](../../data/maintenance_actions.csv#L13)) |
| Electrical work | qualified electrical personnel | A: A16 ([maint:17](../../data/maintenance_actions.csv#L17)) |

No other shutdown or immediate-inspection criterion is documented. Any further safety rule (e.g. vibration zone D
→ stop, bearing temperature trip, seal leakage of hazardous fluid) must come from an engineering source or site
procedure (E). This audit makes no such claim.
