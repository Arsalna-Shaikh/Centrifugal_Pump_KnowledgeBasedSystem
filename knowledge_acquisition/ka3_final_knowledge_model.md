# KA-3 — Final Knowledge Model: Centrifugal Pump KBS (CT-359)

**Status:** design document, **not implemented**. No code, dataset, knowledge-base file or application was
changed.

**Built from:**
- KA-1 audit ([audit/](audit/)) — what the existing KB and the synthetic dataset contain.
- KA-2 research ([research/ka2_fault_research.md](research/ka2_fault_research.md)) — what external sources support.

**Design goal:** a small, explainable, layered rule-based KBS that:
- separates faults from root causes;
- says how well each piece of knowledge is supported;
- handles unknown and conflicting evidence;
- never presents unvalidated knowledge as fact.

---

## 0. Support levels and source references
Every relationship below carries one support level. These are qualitative evidence labels, **not
probabilities**.

| Level | Meaning | Comes from (KA-2 tags) |
|---|---|---|
| **Strong** | stated by an independent source (standard body, Hydraulic Institute, DOE/HI), alone or with a manufacturer | IND, IND+MFR |
| **Moderate** | stated by a manufacturer source only | MFR |
| **Unvalidated** | only in the project's own KB/dataset, or no source read | UNV, A, B |
| **Disputed** | contradicted by an independent source in some context | IND contradiction |

**Source IDs:**
- `S-01 … S-16`: KA-2 source register ([research §2](research/ka2_fault_research.md)). The main ones:
  - S-01 DOE/HI *Sourcebook* (page numbers given as "p. n")
  - S-02 HI operating regions
  - S-03 HI gas mixtures
  - S-04 KSB cavitation
  - S-06 KSB dry running
  - S-07 KSB operating behaviour
  - S-08 KSB shaft seal
  - S-09 KSB flow rate
  - S-10 Grundfos cavitation FAQ
  - S-11 Goulds 3408A IOM troubleshooting items
  - S-12 SKF / ISO 15243
  - S-13 Vogel alignment article
- **A:** the existing project KB, cited as file:line.

**Rule of use:** only *Strong* and *Moderate* knowledge may raise a diagnosis to "likely". *Unvalidated*
knowledge may be shown as a supporting hint, but is labelled as such in every explanation.

---

## 1. Architectural decisions (the seven KA-1 decisions)
These answer the seven open questions in
[audit/recommended_knowledge_model.md §7](audit/recommended_knowledge_model.md). Each was decided from the KA-1/KA-2
evidence. **No separate group approval was recorded during the KA process. Confirm or amend this table before
implementation.**

| # | Decision | Adopted option | Justification |
|---|---|---|---|
| D1 | Fault granularity | **11 faults + Normal + Unknown** (§3.4). F04 kept (impeller blockage). F08 and F14 merged into one *Motor fault*. Wear-ring wear added. | F08/F14 had no discriminating evidence (KA-1 C-08). Wear-ring wear is independently supported (S-01 pp. 16, 35). |
| D2 | F06, F11, F13, F14 | **F06 → cause** (suction fouling/clogged strainer). **F11 stays a fault** (discharge restriction / low-flow operation). **F13 → cause** (base looseness/soft foot). **F14 → cause** of Motor fault. | S-01 p. 20 treats suction fouling as a cause of cavitation. F11's effects are documented as a condition (S-02, S-07). F13 and F14 had no independent evidence as faults. |
| D3 | Threshold reference | Size-dependent indicators (flow, head, current) are **% of the pump's rated value**. Temperatures, vibration and suction pressure are **absolute**. All values are **provisional (Unvalidated)** and stored as data, not code. | Operating limits are pump-specific (S-02, S-09); absolute bar/A limits fail across sizes (KA-1 C-02). No numeric limit was validated in KA-2. |
| D4 | Symptom vocabulary | 21 symptoms (§3.3): `flow_fluctuation` merged into `pressure_fluctuation`; `efficiency_low` replaced by `performance_decline`; `discharge_pressure_low/high` redefined as `head_low/high` (rated-relative); `base_vibration` retired; `motor_current_low` added. | KA-1 G-15 near-duplicates. S-01 p. 35 uses "decline in performance". S-01 p. 17 makes low current meaningful evidence. |
| D5 | Equipment boundary | **Pump set:** pump + motor + coupling + baseplate + adjacent suction/discharge piping and valves, plus three *external* elements (supply tank/sump, power supply, process liquid). | Most documented causes lie in piping, supply or process, e.g. vortex at low level (S-01 p. 31), pipe strain (S-01 p. 32). |
| D6 | External sources | KA-2 register is the source list. **Still to obtain:** ISO 10816-7 (Annex A zones), ANSI/HI 9.6.1 and 9.6.3, one pump textbook. | Needed to validate any threshold (KA-2 §13, §17). |
| D7 | Uncertainty representation | **Qualitative support levels only** (§0); no certainty factors or probabilities. Hypotheses are ranked by evidence quality (§5.4). | Assignment-appropriate, fully explainable, and avoids arbitrary numbers (KA-1 principle). |

---

## 2. Model overview
```
Equipment (pump set, with ratings)
  └─ Components ── measured by ──> Indicators ──(threshold rules)──> Symptoms
                                                                       │
                     Faults <──(diagnostic rules)─────────────────────┘
                       │  └─ leads_to ─> other Faults (chains)
                       ├─ caused_by ─> Root causes ─ confirmed_by ─> Diagnostic tests
                       │                    └─ located_at ─> Components
                       ├─ recommends ─> Maintenance actions
                       └─ safety ─> Safety rules (override)
```
**Inference chain:** indicator → symptom → fault hypothesis → cause hypothesis → test request → action + safety
message. Every step carries source IDs into the explanation.

---

## 3. Final entities

### 3.1 Equipment
| ID | Entity | Required attributes | Note |
|---|---|---|---|
| EQ-01 | Centrifugal pump set | `pump_design` (`radial` / `mixed` / `axial`), rated flow (m³/h), rated differential head/pressure, rated motor current (A), Qmin (from data sheet), installation type | `pump_design` is needed because motor-current behaviour at low flow depends on it (S-01 p. 17). Qmin is pump-specific (S-09). |

The four types in the dataset (end suction, split case, multistage, vertical inline) are all treated as `radial`
unless the data sheet says otherwise. This is an assumption to confirm per pump.

### 3.2 Components
| ID | Component | Kind | Old ID |
|---|---|---|---|
| CMP-01 | Casing / volute | pump | C01 |
| CMP-02 | Impeller | pump | C02 |
| CMP-03 | Wear rings | pump | **new** (S-01 pp. 16, 35) |
| CMP-04 | Shaft | pump | C03 |
| CMP-05 | Bearings (+ lubricant) | pump | C04 |
| CMP-06 | Mechanical seal / packing | pump | C05 |
| CMP-07 | Coupling | drive train | C06 |
| CMP-08 | Electric motor (windings, cooling) | driver | C09 |
| CMP-09 | Baseplate / foundation | structure | C10 |
| CMP-10 | Suction line (strainer, suction valve, flanges, foot valve) | piping | C07 |
| CMP-11 | Discharge line (discharge valve, check valve) | piping | C08 |
| EXT-01 | Supply tank / sump (liquid level) | external | new |
| EXT-02 | Electrical supply | external | new |
| EXT-03 | Process liquid (temperature, gas content, solids, density) | external | new |

### 3.3 Symptoms and indicators
Observation kinds:
- **S** sensor-derived through a threshold rule;
- **O** observed by a person;
- **T** trend over time.

| ID | Key | Kind | Definition (provisional threshold, see §3.7) | Old ID |
|---|---|---|---|---|
| SYM-01 | vibration_high | S | overall vibration (mm/s RMS) ≥ THR-01 | S01 |
| SYM-02 | bearing_temp_high | S | bearing temperature ≥ THR-02 | S02 |
| SYM-03 | seal_temp_high | S | seal-area temperature ≥ THR-03 | S16 |
| SYM-04 | motor_temp_high | S | motor temperature ≥ THR-04 | S10 |
| SYM-05 | flow_low | S | flow < THR-05 % of rated (and ≥ THR-06) | S06 |
| SYM-06 | no_flow | S | flow < THR-06 % of rated; **implies** flow_low | S13 |
| SYM-07 | head_low | S | differential head < THR-07 % of rated at the operating flow | S05 (redefined) |
| SYM-08 | head_high | S | differential head > THR-08 % of rated | S17 (redefined) |
| SYM-09 | suction_pressure_low | S | suction pressure (bar a) < THR-09 | S07 |
| SYM-10 | motor_current_high | S | current > THR-10 % of rated | S09 (redefined) |
| SYM-11 | motor_current_low | S | current < THR-11 % of rated | **new** |
| SYM-12 | pressure_fluctuation | S | pressure fluctuation ≥ THR-12 % | S11 + S12 merged |
| SYM-13 | crackling_noise | O | crackling/popping, "marbles" sound (S-01 p. 20) | S04 |
| SYM-14 | grinding_noise | O | grinding/rumbling bearing noise | S03 |
| SYM-15 | seal_leakage | O | leakage at seal above normal | S08 |
| SYM-16 | coupling_vibration | O | vibration dominant at coupling | S15 |
| SYM-17 | air_bubbles | O | bubbles/froth in discharge or sight glass | S20 |
| SYM-18 | prime_failure | O | pump will not prime / loses prime | S14 |
| SYM-19 | rapid_temp_rise | T | casing/liquid temperature rising quickly | S22 |
| SYM-20 | speed_unstable | O | motor speed hunting | S18 |
| SYM-21 | performance_decline | T | sustained loss of flow/head against the pump curve (S-01 p. 35) | S21 (replaced) |

**Symptom relations:**
- `no_flow` **implies** `flow_low`.
- **Mutually exclusive pairs** (see §5.3): `head_low` ⊥ `head_high`; `motor_current_low` ⊥ `motor_current_high`.

**Diagnostic tests** (results are evidence for causes):
| ID | Test | Source |
|---|---|---|
| TST-01 | NPSH available vs NPSH3/NPSHR check | S-02, S-05, S-10 (Strong) |
| TST-02 | Alignment check (dial-indicator TIR or laser) | S-01 p. 34 (Strong) |
| TST-03 | Vibration analysis against a baseline | S-01 pp. 34–36 (Strong) |
| TST-04 | Oil analysis | S-01 pp. 16, 36 (Strong) |
| TST-05 | Infrared thermography | S-01 p. 36 (Strong) |
| TST-06 | Seal leakage measurement vs manufacturer spec | S-01 p. 34 (Strong) |
| TST-07 | Suction-line leak test (pressurise / check flanges) | S-11 item 8 (Moderate) |
| TST-08 | Liquid level / submergence check | S-01 p. 31, S-11 item 16 (Strong) |
| TST-09 | Performance test vs pump curve | S-01 p. 35 (Strong) |
| TST-10 | Motor insulation resistance test | S-01 p. 34 (Strong) |
| TST-11 | Internal inspection (impeller, wear rings, passages, strainer) | S-01 p. 35; S-11 items 7, 14, 21 (Strong) |
| TST-12 | Supply voltage/frequency/phase check | S-11 items 5, 40 (Moderate) |

### 3.4 Faults
| ID | Fault | Primary component | Hazard class | Old ID |
|---|---|---|---|---|
| FLT-01 | Cavitation | CMP-02 (damage) / CMP-10, EXT (origin) | High | F02 |
| FLT-02 | Dry running / loss of prime | CMP-06, CMP-05, CMP-03 | **Critical** | F07 |
| FLT-03 | Air / gas ingress | CMP-10, EXT-01, EXT-03 | High | F12 |
| FLT-04 | Bearing failure | CMP-05 | High | F01 |
| FLT-05 | Shaft misalignment | CMP-04, CMP-07 | High | F03 |
| FLT-06 | Mechanical seal failure | CMP-06 | High | F05 |
| FLT-07 | Impeller damage (erosion/corrosion/mechanical) | CMP-02 | High | F10 |
| FLT-08 | Impeller blockage / fouling | CMP-02 | Medium | F04 |
| FLT-09 | Discharge restriction / low-flow operation | CMP-11 | High | F11 |
| FLT-10 | Wear-ring wear (excess internal clearance) | CMP-03 | Medium | **new** |
| FLT-11 | Motor fault (overload / electrical) | CMP-08, EXT-02 | High | F08 + F14 |
| FLT-12 | Coupling damage | CMP-07 | High | F09 |
| OUT-N | Normal (no fault evidence) | — | — | new |
| OUT-U | Unknown — further investigation | — | — | new |

**Hazard classes** are carried over from the old KB. Only Critical for dry running has partial external support:
S-06 describes possible disintegration and a dry-running protection device. **The other classes are
Unvalidated.**

### 3.5 Root causes
| ID | Root cause | Located at | Cause of | Support |
|---|---|---|---|---|
| CAU-01 | Insufficient NPSH available (low suction pressure / level, high lift, suction losses) | CMP-10, EXT-01 | FLT-01 | Strong (S-01 p. 20; S-02; S-11 items 3, 13) |
| CAU-02 | Liquid temperature above design | EXT-03 | FLT-01 | Strong (S-01 p. 20) |
| CAU-03 | Operation far right of BEP (high flow) | operating point | FLT-01 | Strong (S-01 p. 20) |
| CAU-04 | Operation at low flow / below Qmin (recirculation, throttled or oversized pump) | operating point, CMP-11 | FLT-01, FLT-04, FLT-09 | Strong (S-01 pp. 20–21, 25; S-02; S-07) |
| CAU-05 | Suction fouling / clogged strainer / obstructed foot valve | CMP-10 | FLT-01, FLT-08 (low flow) | Strong (S-01 p. 20) + Moderate (S-11 item 15) |
| CAU-06 | Wrong pump selection | design | FLT-01 | Strong (S-01 p. 20) |
| CAU-07 | No liquid supply / incomplete priming | EXT-01, CMP-10 | FLT-02 | Moderate (S-06, S-08, S-11 items 1, 25) |
| CAU-08 | Vortex at low liquid level / insufficient submergence | EXT-01 | FLT-02, FLT-03 | Strong (S-01 p. 31) + Moderate (S-11 item 16) |
| CAU-09 | Air leak at suction piping / flanges | CMP-10 | FLT-03 | Moderate (S-11 items 8, 19, 27) |
| CAU-10 | Air drawn in through packing (suction below atmospheric) | CMP-06 | FLT-03, FLT-02 | Strong (S-01 p. 22) |
| CAU-11 | Gas/vapour in the liquid; vapour pockets in badly sloped suction pipe | EXT-03, CMP-10 | FLT-03 | Strong (S-01 p. 31; S-03) + Moderate (S-11 item 22) |
| CAU-12 | Inadequate or wrong lubrication (incl. contaminated lubricant) | CMP-05 | FLT-04 | Strong (S-01 p. 16) + Moderate (S-12) |
| CAU-13 | Over-greasing | CMP-05 | FLT-04 | Strong (S-01 p. 33) |
| CAU-14 | High bearing load: shaft deflection off-BEP, impeller unbalance, throttled operation | CMP-04, CMP-02 | FLT-04 | Strong (S-01 pp. 21–22, 25) |
| CAU-15 | Contamination / inadequate bearing sealing | CMP-05 | FLT-04 | Moderate (S-12) |
| CAU-16 | Improper mounting, wrong fits | CMP-05 | FLT-04 | Moderate (S-12) |
| CAU-17 | Material fatigue (end of life) | CMP-05 | FLT-04 | Moderate (S-12) |
| CAU-18 | Electrical current through bearing | CMP-05, EXT-02 | FLT-04 | Moderate (S-12) |
| CAU-19 | Pipe strain on casing | CMP-10, CMP-11 | FLT-05 | Strong (S-01 p. 32) + Moderate (S-11 item 35) |
| CAU-20 | Motor shift / foundation movement | CMP-08, CMP-09 | FLT-05 | Strong (S-01 p. 34) |
| CAU-21 | Base looseness / soft foot (old F13) | CMP-09 | FLT-05 | Unvalidated (A: faults.csv:14, maintenance_actions.csv:16) |
| CAU-22 | Uncompensated thermal growth; poor installation alignment | CMP-07 | FLT-05 | Unvalidated (dataset only) |
| CAU-23 | Seal-face contamination / debris | CMP-06 | FLT-06 | Strong (S-01 pp. 16, 22) |
| CAU-24 | Loss of seal lubrication (dry running, gas, evaporation) → overheating | CMP-06 | FLT-06 | Strong (S-01 p. 16) + Moderate (S-08) |
| CAU-25 | Improper seal installation / seal misalignment / shaft deflection | CMP-06, CMP-04 | FLT-06 | Strong (S-01 pp. 16, 22) |
| CAU-26 | Loss of spring / bellows force | CMP-06 | FLT-06 | Strong (S-01 p. 22) |
| CAU-27 | Abrasive particles in liquid | EXT-03 | FLT-06, FLT-07 | Strong (S-01 p. 7) + Moderate (S-08) |
| CAU-28 | Seal flush failure | CMP-06 | FLT-06 | Unvalidated (A: maintenance_actions.csv:8; dataset) |
| CAU-29 | Corrosion (aggravated by cavitation + oxygen) | CMP-02 | FLT-07 | Moderate (S-04) |
| CAU-30 | Foreign object impact | CMP-02 | FLT-07 | Unvalidated (dataset) |
| CAU-31 | Debris / solids lodged in impeller or passages | CMP-02 | FLT-08 | Moderate (S-11 items 7, 11, 21) |
| CAU-32 | Discharge valve closed or partly closed; closed check valve | CMP-11 | FLT-09 | Moderate (S-07) |
| CAU-33 | Erosion of wear-ring clearances | CMP-03 | FLT-10 | Strong (S-01 p. 16) |
| CAU-34 | Liquid heavier/more viscous than allowed (process overload) | EXT-03 | FLT-11 | Moderate (S-11 item 33) |
| CAU-35 | Low supply voltage/frequency; open phase; supply imbalance (old F14) | EXT-02 | FLT-11 | Moderate (S-11 items 5, 40); imbalance: Unvalidated (A: faults.csv:15) |
| CAU-36 | Winding insulation breakdown (prolonged over-temperature) | CMP-08 | FLT-11 | Strong (S-01 p. 35) |
| CAU-37 | Poor motor ventilation | CMP-08 | FLT-11 | Moderate (S-11 item 40) |
| CAU-38 | Coupling element wear / looseness | CMP-07 | FLT-12 | Unvalidated (A: faults.csv:10) |

### 3.6 Maintenance actions and safety rules
| ID | Action | For | Support | Old ID |
|---|---|---|---|---|
| ACT-01 | Restore NPSH: raise suction level/pressure, reduce suction losses, cool liquid; do not throttle below Qmin | FLT-01 / CAU-01, 02 | Moderate (S-11 item 13; S-10 with minimum-flow caveat) | A03 |
| ACT-02 | Inspect impeller for erosion; repair or replace | FLT-01, FLT-07 | Strong (S-01 p. 35) | A04, A12 |
| ACT-03 | Stop pump; restore liquid supply; prime and vent | FLT-02 | Moderate (S-06; S-11 items 1, 25) | A09 |
| ACT-04 | Leak-test suction piping and flanges; repair | FLT-03 / CAU-09 | Moderate (S-11 item 8) | A14 |
| ACT-05 | Increase submergence / fit vortex breaker | CAU-08 | Moderate (S-11 item 16) | new |
| ACT-06 | Gas separation and venting on suction | CAU-11 | Moderate (S-11 item 22) | new |
| ACT-07 | Check bearing condition (noise, temperature, vibration/oil analysis); lubricate per manual, avoid over-greasing; replace if damaged | FLT-04 | Strong (S-01 pp. 33–34) | A01, A02 |
| ACT-08 | Check and correct alignment (dial/laser); correct pipe supports and strain | FLT-05 | Strong (S-01 pp. 32, 34) | A05 |
| ACT-09 | Measure seal leakage; inspect/replace seal; keep faces clean and lubricated | FLT-06 | Strong (S-01 pp. 34–35) | A07 |
| ACT-10 | Dismantle and clean impeller and passages | FLT-08 | Moderate (S-11 items 7, 21) | A06 |
| ACT-11 | Clean strainer; check suction valves fully open | CAU-05 | Moderate (S-11 items 3, 15) | A08 |
| ACT-12 | Open/repair discharge valve; restore flow ≥ Qmin / minimum-flow path | FLT-09 | Moderate (S-07, S-09) | A13 |
| ACT-13 | Reset or replace wear rings to manufacturer clearance | FLT-10 | Strong (S-01 pp. 16, 35) | new |
| ACT-14 | Check supply voltage, frequency and phases; check motor load and ventilation; insulation resistance test | FLT-11 | Moderate (S-11 item 40) + Strong (S-01 p. 34) | A10, A16 |
| ACT-15 | Inspect and repair coupling elements | FLT-12 | Unvalidated | A11 |
| ACT-16 | Inspect hold-down bolts, soft foot, foundation | CAU-21 | Unvalidated | A15 |
| ACT-17 | Further investigation: request the tests listed by the active test-request rule | OUT-U | — | new |

**Safety rules.** These are shown regardless of how a fault ranks:
| ID | Trigger | Message | Support |
|---|---|---|---|
| SAF-01 | FLT-02 suspected at any level, or `no_flow` with `prime_failure` | Stop or secure the pump per site procedure; do not continue dry operation | Moderate (S-06 protection device); A: maintenance_actions.csv:10, app.py:70 |
| SAF-02 | FLT-09 suspected, or `no_flow` with discharge closed | Do not run continuously at or near zero flow; restore flow ≥ Qmin | Moderate (S-07: rapid temperature rise, seizure, burst risk with closed check valve) |
| SAF-03 | Any action that opens the pump (ACT-02, 10, 13) | Isolate the pump before opening | A: maintenance_actions.csv:7, :13 (Unvalidated externally) |
| SAF-04 | Any electrical action (ACT-14) | Qualified electrical personnel only | A: maintenance_actions.csv:17 (Unvalidated externally) |

### 3.7 Thresholds (all provisional)
No numeric limit was validated in KA-2. Values are kept configurable and labelled **Unvalidated**.

| ID | Indicator | Provisional value | Origin | To be replaced by |
|---|---|---|---|---|
| THR-01 | vibration (mm/s RMS) | 6.0 | A: inference_engine.py:28 | ISO 10816-7 Annex A zone boundary for the pump class |
| THR-02 | bearing temperature (°C) | 80 | A: inference_engine.py:29 | OEM / bearing data |
| THR-03 | seal-area temperature (°C) | 85 | A: inference_engine.py:37 | OEM seal data |
| THR-04 | motor temperature (°C) | 80 | A: inference_engine.py:30 | motor insulation class / OEM |
| THR-05 | flow_low (% rated) | 75 | A: inference_engine.py:31 (was % of baseline) | pump POR (ANSI/HI 9.6.3) |
| THR-06 | no_flow (% rated) | 10 | A: inference_engine.py:32 | pump Qmin (data sheet) |
| THR-07 | head_low (% rated at flow) | 85 | data_preparation (C) | pump curve tolerance / OEM |
| THR-08 | head_high (% rated) | 115 | data_preparation (C) | pump curve (shut-off head) |
| THR-09 | suction pressure (bar a) | 0.70 | A: inference_engine.py:35 | NPSHA calculation vs NPSH3 + margin (ANSI/HI 9.6.1) |
| THR-10 | current high (% rated) | 110 | data_preparation (C) | motor nameplate / service factor |
| THR-11 | current low (% rated) | to be set | — | pump power curve at Qmin |
| THR-12 | pressure fluctuation (%) | 10 | A: inference_engine.py:38 | no source identified |

---

## 4. Relationships

### 4.1 Fault → symptom (`manifests_as`)
"Strong / Moderate" relationships are **validated in direction only**. No source gives how often or how strongly.

| Fault | Symptom | Support | Source |
|---|---|---|---|
| FLT-01 Cavitation | crackling_noise | Strong | S-01 p. 20; S-04 |
| | head_low | Strong | S-01 p. 20; S-02; S-04 |
| | suction_pressure_low | Strong (as cause indicator) | S-01 p. 20 |
| | vibration_high | Strong | S-01 p. 21 |
| | flow_low | Moderate | S-11 item 13 |
| | pressure_fluctuation | **Unvalidated** | A: weights:12, rules.json R02 |
| FLT-02 Dry running | no_flow | Moderate | S-11 items 1–7 |
| | prime_failure | Strong | S-01 pp. 22, 31; S-11 item 1 |
| | seal_temp_high, bearing_temp_high, rapid_temp_rise | Moderate ("overheating") | S-06; S-08 |
| | vibration_high | Moderate | S-06 |
| | grinding_noise | **Unvalidated** | A: weights:39 |
| FLT-03 Air ingress | flow_low, head_low | Strong | S-03; S-11 items 8, 22 |
| | prime_failure | Strong | S-01 pp. 22, 31 |
| | air_bubbles | **Unvalidated** | A: weights:59 |
| | pressure_fluctuation | **Unvalidated** (S-01 p. 31 mentions pulsations from vapour pockets only) | A: weights:62 |
| FLT-04 Bearing failure | vibration_high | Strong | S-01 pp. 34, 36 |
| | bearing_temp_high | Strong | S-01 pp. 34, 36 |
| | grinding_noise | Strong (noise) | S-01 p. 34 |
| | motor_current_high | **Unvalidated** | A: weights:5 |
| FLT-05 Misalignment | vibration_high | Moderate | S-13 |
| | motor_current_high | Moderate ("takes too much power") | S-11 item 38 |
| | coupling_vibration | **Unvalidated** | A: weights:16 |
| | bearing_temp_high | **Unvalidated** (KA-1 C-05 open) | A: weights:17 |
| FLT-06 Seal failure | seal_leakage | Strong | S-01 pp. 34–35 |
| | seal_temp_high | Moderate | S-08 |
| | vibration_high | **Unvalidated** | A: weights:27 |
| FLT-07 Impeller damage | performance_decline, head_low | Strong | S-01 p. 35; S-11 item 14 |
| | vibration_high | Strong (via unbalance) | S-01 p. 21 |
| | flow_low | Moderate | S-11 item 14 |
| FLT-08 Impeller blockage | flow_low, no_flow, head_low | Moderate | S-11 items 7, 11, 21 |
| | motor_current_high | **Disputed** for radial pumps (current falls with flow) | S-01 p. 17 vs A: weights:24 |
| FLT-09 Discharge restriction / low flow | flow_low | Strong | S-02; S-07 |
| | rapid_temp_rise | Strong | S-07; S-02 (temperature rise listed) |
| | vibration_high | Strong | S-02 |
| | motor_current_low (radial pump) | Strong | S-01 p. 17 |
| | head_high | **Unvalidated** (follows from the pump curve; not stated as a symptom) | A: weights:54 |
| | motor_current_high | **Disputed** for radial pumps; plausible for axial | S-01 p. 17 vs A: weights:57 |
| FLT-10 Wear-ring wear | performance_decline, head_low, flow_low | Strong | S-01 pp. 16, 35 |
| FLT-11 Motor fault | motor_current_high | Moderate (excess power draw) | S-11 items 33, 40 |
| | motor_temp_high | Moderate | S-01 p. 35 (winding over-temperature); S-11 item 40 |
| | speed_unstable | **Unvalidated** | A: weights:43, :71 |
| FLT-12 Coupling damage | coupling_vibration, vibration_high | **Unvalidated** | A: weights:45–46 |

### 4.2 Fault → fault chains (`leads_to`)
| From | To | Support | Source |
|---|---|---|---|
| FLT-01 Cavitation | FLT-07 Impeller damage | Strong | S-01 pp. 20, 35; S-04 |
| FLT-01 Cavitation | FLT-04 Bearing failure, FLT-06 Seal failure (accelerated wear) | Strong | S-01 pp. 20–21 |
| FLT-03 Air ingress | FLT-02 Dry running (partial; loss of prime) | Strong | S-01 p. 31; S-06 |
| FLT-02 Dry running | FLT-06 Seal failure | Strong + Moderate | S-01 p. 31; S-08 |
| FLT-09 Low-flow operation | FLT-01 Cavitation (recirculation) | Strong | S-01 pp. 20–21; S-07 |
| FLT-09 Low-flow / throttled operation | FLT-04 Bearing failure | Strong | S-01 pp. 22, 25 |
| FLT-07 Impeller damage | FLT-04 Bearing failure (unbalance) | Strong | S-01 p. 21 |
| FLT-05 Misalignment | FLT-04, FLT-06 (via vibration) | Moderate | S-13; S-12 |

### 4.3 Cause → test (`confirmed_by`)
| Cause | Confirming test | Support |
|---|---|---|
| CAU-01, CAU-02 | TST-01 NPSH check | Strong |
| CAU-05 | TST-11 strainer / passage inspection | Moderate |
| CAU-08 | TST-08 level / submergence | Strong |
| CAU-09 | TST-07 suction leak test | Moderate |
| CAU-12, CAU-15 | TST-04 oil analysis | Strong (lubrication) / Moderate (contamination) |
| CAU-14, CAU-17 | TST-03 vibration analysis | Strong |
| CAU-19, CAU-20 | TST-02 alignment check | Strong |
| CAU-23 to CAU-26 | TST-06 leakage + TST-11 inspection | Strong |
| CAU-33 | TST-09 performance test + TST-11 | Strong |
| CAU-35 | TST-12 supply check | Moderate |
| CAU-36 | TST-10 insulation resistance | Strong |

### 4.4 Unvalidated relationships kept for continuity
They are **displayed with an "unvalidated" label and cannot by themselves raise a diagnosis above "possible"**:
- FLT-01/03 → pressure_fluctuation
- FLT-02 → grinding_noise
- FLT-03 → air_bubbles
- FLT-04 → motor_current_high
- FLT-05 → coupling_vibration, bearing_temp_high
- FLT-06 → vibration_high
- FLT-09 → head_high
- FLT-11 → speed_unstable
- all of FLT-12
- causes CAU-21, 22, 28, 30, 38 and the supply-imbalance part of CAU-35
- every threshold value in §3.7
- hazard classes other than FLT-02

---

## 5. Diagnostic rules

### 5.1 Rule layers
| Layer | Purpose | Example |
|---|---|---|
| L1 Evidence | indicator + threshold → symptom (present / absent / unknown) | flow 8 % of rated → no_flow present, flow_low present |
| L2 Fault | symptoms → fault hypothesis | R-CAV-1 |
| L3 Cause | fault + test result → cause | R-C-01 |
| L4 Test request | competing hypotheses → ask for a discriminating test | R-T-01 |
| L5 Action & safety | fault/cause → actions; safety rules always evaluated | ACT-xx, SAF-xx |

A rule's support = the **weakest** support among the relationships it uses.

### 5.2 Rule set
Every condition must be *present*. Unknown conditions leave the rule **pending**; absent ones **block** it (§6).

| ID | IF | THEN | Support | Basis | Replaces |
|---|---|---|---|---|---|
| R-CAV-1 | crackling_noise ∧ (suction_pressure_low ∨ head_low) | FLT-01 likely | Strong | S-01 p. 20; S-04 | R02 |
| R-CAV-2 | TST-01 shows NPSHA ≤ NPSH3 + required margin | FLT-01 likely; CAU-01 | Strong | S-02 | new |
| R-DRY-1 | no_flow ∧ prime_failure | FLT-02 likely; **SAF-01** | Moderate | S-11; S-01 p. 31 | R07 (rapid_temp_rise no longer required) |
| R-DRY-2 | no_flow ∧ (seal_temp_high ∨ bearing_temp_high ∨ rapid_temp_rise) | FLT-02 possible; **SAF-01** | Moderate | S-06 | R07 |
| R-AIR-1 | (flow_low ∨ head_low) ∧ prime_failure ∧ ¬no_flow | FLT-03 likely | Strong | S-03; S-01 pp. 22, 31 | R12 |
| R-AIR-2 | air_bubbles ∧ pressure_fluctuation | FLT-03 possible (**unvalidated**) | Unvalidated | A: rules.json R12 | R12 |
| R-BRG-1 | vibration_high ∧ bearing_temp_high | FLT-04 likely | Strong | S-01 pp. 34, 36 | R01 |
| R-BRG-2 | grinding_noise ∧ (vibration_high ∨ bearing_temp_high) | FLT-04 likely | Strong | S-01 p. 34 | R01 |
| R-MIS-1 | TST-02 alignment out of tolerance | FLT-05 confirmed | Strong | S-01 p. 34 | new |
| R-MIS-2 | vibration_high ∧ coupling_vibration ∧ ¬bearing_temp_high | FLT-05 possible (**unvalidated signature**) → R-T-02 | Unvalidated | A: R03 | R03 |
| R-SEAL-1 | seal_leakage | FLT-06 likely | Strong | S-01 pp. 34–35 | R05 |
| R-SEAL-2 | seal_leakage ∧ seal_temp_high | FLT-06 likely; suspect CAU-24 (lubrication loss) | Moderate | S-08; S-01 p. 16 | R05 |
| R-IMP-1 | performance_decline ∧ vibration_high | FLT-07 likely | Strong | S-01 pp. 21, 35 | R10 |
| R-WR-1 | performance_decline ∧ ¬vibration_high | FLT-10 possible → R-T-03 | Strong for the symptom, Unvalidated for the ¬vibration distinction | S-01 pp. 16, 35 | new |
| R-BLK-1 | (no_flow ∨ flow_low) ∧ head_low ∧ ¬prime_failure ∧ ¬crackling_noise | FLT-08 possible → R-T-03 | Moderate | S-11 items 7, 11, 21 | R04 |
| R-DIS-1 | flow_low ∧ rapid_temp_rise | FLT-09 likely; **SAF-02** | Strong | S-07; S-02 | R11 |
| R-DIS-2 | flow_low ∧ motor_current_low ∧ pump_design = radial | FLT-09 possible | Strong | S-01 p. 17 | new |
| R-MOT-1 | motor_current_high ∧ motor_temp_high | FLT-11 likely | Moderate | S-11 items 33, 40; S-01 p. 35 | R08, R14 |
| R-CPL-1 | coupling_vibration ∧ grinding_noise | FLT-12 possible (**unvalidated**) | Unvalidated | A: R09 | R09 |

**Negative-evidence rules (`argues_against`):**
| ID | IF | THEN | Support |
|---|---|---|---|
| N-01 | motor_current_high ∧ pump_design = radial | lower FLT-08 and FLT-09 by one level | Strong (S-01 p. 17) |
| N-02 | prime_failure absent ∧ flow normal | FLT-02 blocked | follows from the definition |
| N-03 | head_high present | lower FLT-01, FLT-07, FLT-08, FLT-10 by one level (those faults reduce head) | Strong for the direction (S-01 pp. 20, 35) |

**Cause rules (L3):**
| ID | IF | THEN | Support |
|---|---|---|---|
| R-C-01 | FLT-01 ∧ liquid temperature above design | CAU-02 | Strong (S-01 p. 20) |
| R-C-02 | (FLT-01 ∨ FLT-08) ∧ TST-11 finds clogged strainer | CAU-05 | Strong / Moderate |
| R-C-03 | (FLT-02 ∨ FLT-03) ∧ TST-08 finds low level / vortex | CAU-08 | Strong (S-01 p. 31) |
| R-C-04 | FLT-04 ∧ TST-04 shows lubricant degraded/contaminated | CAU-12 / CAU-15 | Strong / Moderate |
| R-C-05 | (FLT-04 ∨ FLT-06) ∧ R-MIS-1 fired | cause chain FLT-05 → FLT-04/06 | Moderate (S-13) |
| R-C-06 | FLT-07 ∧ FLT-01 evidence | cause chain FLT-01 → FLT-07 | Strong |
| R-C-07 | FLT-11 ∧ TST-12 shows low voltage / open phase | CAU-35 | Moderate |

**Test-request rules (L4):**
| ID | IF | THEN request |
|---|---|---|
| R-T-01 | FLT-01 and FLT-03 both possible | TST-01 NPSH check + TST-07 leak test + TST-08 level check |
| R-T-02 | FLT-04 and FLT-05 both possible | TST-02 alignment + TST-03 vibration analysis |
| R-T-03 | FLT-07, FLT-08, FLT-10 competing | TST-09 performance test + TST-11 inspection |
| R-T-04 | any key symptom unknown | ask the operator for that observation |

**Retired old rules:**
- R06 (suction blockage): F06 is now a cause (CAU-05), reached through R-C-02. KA-1 C-06.
- R13 (base looseness): F13 is now a cause (CAU-21). There was no independent evidence for it.

---

## 6. Unknown, absent and conflicting evidence

**Three observation states.** Every symptom is `present`, `absent` or `unknown`.
- The UI default becomes `unknown`, not "normal" (KA-1 G-10).
- A symptom derived from a missing or imputed reading is `unknown`.
- `no_flow` present sets `flow_low` present.

**Rule evaluation.**
- **Fires:** all positive conditions are present and all negated conditions are absent.
- **Pending:** a condition is unknown. The rule is listed as "could apply — needs X", and R-T-04 asks for X.
- **Blocked:** a positive condition is absent. The rule is dropped from the explanation.
- **Unknown never counts as absent.** Missing information can never rule a fault out.

**Conflicting evidence.**
1. **Mutually exclusive symptoms present together** (head_low ∧ head_high, current_low ∧ current_high): raise a
   *data conflict* warning, set both to unknown, and continue.
2. **Negative evidence** (N-01 … N-03) lowers a hypothesis by one level (likely → possible → unlikely). It is shown
   in the explanation with its source.
3. **Competing faults** are kept together as a *differential* and trigger a test-request rule (R-T-01 … 03). The
   system never forces a single answer.
4. **Multiple genuine faults** are allowed. If both ends of a §4.2 chain are found, they are reported as a chain
   ("cavitation, likely causing impeller damage").

**Result statuses and ranking.** Each fault ends as one of:
- **confirmed:** a test rule fired (R-MIS-1, R-CAV-2);
- **likely:** a Strong or Moderate rule fired;
- **possible:** only an Unvalidated rule fired, or the fault was lowered by negative evidence;
- **pending:** rules are waiting on unknown evidence.

Within a status, rank by:
1. support of the fired rule (Strong > Moderate > Unvalidated);
2. number of supporting fired rules;
3. hazard class.

**Normal and Unknown outcomes.**
- **Normal** (OUT-N): no symptom present and the key symptoms are *known* to be absent.
- **Unknown — further investigation** (OUT-U): some symptoms are present but no fault reaches *likely*. ACT-17 then
  lists the tests to request.

**Safety rules are evaluated independently of ranking.** SAF-01 fires for any FLT-02 hypothesis, even "possible"
or pending. This fixes the old app's top-1-only CRITICAL check (app.py:70).

**Explanation.** For every result the system lists:
- the symptoms and the readings/thresholds behind them;
- the rules fired, pending or blocked;
- the support level and source IDs of each relationship;
- any negative evidence and conflicts;
- the requested tests and the recommended actions.

---

## 7. Mapping from the old knowledge base

### 7.1 Components ([data/components.csv](../data/components.csv))
| Old | New | Change |
|---|---|---|
| C01 Pump Casing | CMP-01 | + volute |
| C02 Impeller | CMP-02 | — |
| C03 Shaft | CMP-04 | renumbered |
| C04 Bearings | CMP-05 | + lubricant |
| C05 Mechanical Seal | CMP-06 | + packing |
| C06 Coupling | CMP-07 | — |
| C07 Suction Line / Strainer | CMP-10 | + valves, flanges, foot valve |
| C08 Discharge Line / Valve | CMP-11 | + check valve |
| C09 Electric Motor | CMP-08 | — |
| C10 Baseplate / Foundation | CMP-09 | — |
| — | CMP-03 Wear rings; EXT-01…03 | new |

### 7.2 Symptoms ([data/symptoms.csv](../data/symptoms.csv))
| Old | New | Change |
|---|---|---|
| S01 vibration_high | SYM-01 | threshold → THR-01 (data, Unvalidated) |
| S02 bearing_temp_high | SYM-02 | — |
| S03 grinding_noise | SYM-14 | — |
| S04 crackling_noise | SYM-13 | — |
| S05 discharge_pressure_low | SYM-07 head_low | absolute 4.2 bar → % of rated head |
| S06 flow_low | SYM-05 | % of baseline → % of rated |
| S07 suction_pressure_low | SYM-09 | — |
| S08 seal_leakage | SYM-15 | — |
| S09 motor_current_high | SYM-10 | absolute 38 A → % of rated |
| S10 motor_temp_high | SYM-04 | — |
| S11 pressure_fluctuation | SYM-12 | absorbs S12 |
| S12 flow_fluctuation | SYM-12 | **merged** |
| S13 no_flow | SYM-06 | declared to imply SYM-05 |
| S14 prime_failure | SYM-18 | — |
| S15 coupling_vibration | SYM-16 | — |
| S16 seal_temp_high | SYM-03 | — |
| S17 discharge_pressure_high | SYM-08 head_high | absolute 6.0 bar → % of rated |
| S18 speed_unstable | SYM-20 | — |
| S19 base_vibration | — | **retired** (F13 became a cause; no evidence) |
| S20 air_bubbles | SYM-17 | — |
| S21 efficiency_low | SYM-21 performance_decline | **replaced** |
| S22 rapid_temp_rise | SYM-19 | "with low flow" removed (flow is its own symptom) |
| — | SYM-11 motor_current_low | new |

### 7.3 Faults ([data/faults.csv](../data/faults.csv))
| Old | New | Change |
|---|---|---|
| F01 Bearing Wear / Failure | FLT-04 | — |
| F02 Cavitation | FLT-01 | — |
| F03 Shaft Misalignment | FLT-05 | — |
| F04 Impeller Blockage / Fouling | FLT-08 | — |
| F05 Mechanical Seal Failure | FLT-06 | — |
| F06 Suction Blockage / Clogged Strainer | **CAU-05** | fault → cause (of FLT-01 and FLT-08) |
| F07 Dry Running / Loss of Prime | FLT-02 | — |
| F08 Motor Overload | FLT-11 | merged with F14 |
| F09 Coupling Damage / Looseness | FLT-12 | all relationships Unvalidated |
| F10 Impeller Damage / Erosion | FLT-07 | — |
| F11 Discharge Restriction / Closed Valve | FLT-09 | "closed valve" → CAU-32 |
| F12 Air Ingress on Suction Side | FLT-03 | — |
| F13 Base / Foundation Looseness | **CAU-21** | fault → cause (of FLT-05) |
| F14 Electrical Supply Imbalance | FLT-11 + **CAU-35** | fault → cause |
| — | FLT-10 Wear-ring wear; OUT-N; OUT-U | new |

### 7.4 Weights and rules ([data/symptom_fault_weights.csv](../data/symptom_fault_weights.csv), [data/rules.json](../data/rules.json))
- **Weights** (1–5): replaced by the support levels in §4.1. Old values may be kept as `legacy_weight` for
  comparison only.
- **Bonuses** (4–7): dropped. Rule strength comes from support levels.
- **Rule mapping:**

| Old | New |
|---|---|
| R01 | R-BRG-1, R-BRG-2 |
| R02 | R-CAV-1 |
| R03 | R-MIS-2 (unvalidated) + R-T-02 |
| R04 | R-BLK-1 |
| R05 | R-SEAL-1, R-SEAL-2 |
| R06 | retired → R-C-02 |
| R07 | R-DRY-1, R-DRY-2 |
| R08 | R-MOT-1 |
| R09 | R-CPL-1 (unvalidated) |
| R10 | R-IMP-1 |
| R11 | R-DIS-1 |
| R12 | R-AIR-1, R-AIR-2 |
| R13 | retired |
| R14 | R-MOT-1 |

### 7.5 Actions ([data/maintenance_actions.csv](../data/maintenance_actions.csv))
| Old | New |
|---|---|
| A01, A02 | ACT-07 |
| A03 | ACT-01 |
| A04 | ACT-02 |
| A05 | ACT-08 |
| A06 | ACT-10 |
| A07 | ACT-09 |
| A08 | ACT-11 |
| A09 | ACT-03 + SAF-01 |
| A10, A16 | ACT-14 |
| A11 | ACT-15 |
| A12 | ACT-02 |
| A13 | ACT-12 + SAF-02 |
| A14 | ACT-04 |
| A15 | ACT-16 |

New: ACT-05, 06, 13, 17 and SAF-03, SAF-04.

### 7.6 Engine behaviour ([src/inference_engine.py](../src/inference_engine.py), [src/app.py](../src/app.py))
| Old behaviour | New model |
|---|---|
| Thresholds hard-coded (engine:28-49) | THR-xx data with provisional values |
| Single-pass weighted score + % "confidence" (engine:53-95) | Layered rules L1–L5; status + qualitative support; no percentages |
| UI fields default to normal values | default `unknown` |
| CRITICAL banner for top-ranked fault only (app.py:70) | safety rules evaluated for every hypothesis |
| No causes, tests, chains or negative evidence | CAU, TST, `leads_to`, N-rules |

---

## 8. Limitations and next steps
1. **Thresholds are provisional.** All values are carried from the old KB or the data-preparation pipeline. The
   KBS output must say so until ISO 10816-7, ANSI/HI 9.6.1/9.6.3 and OEM data are consulted.
2. **"Strong" means direction only.** Sources say a fault *causes* a symptom, not how often. The model therefore
   ranks by evidence quality, not likelihood.
3. **Motor and coupling faults were not researched** in KA-2 beyond the troubleshooting manual. FLT-11 is
   Moderate at best; FLT-12 is Unvalidated.
4. **Testing data is synthetic.** The data in `data_preparation/` can test that the rules run and are consistent,
   not that they are correct.
5. **Next (implementation, after approval):**
   - Express this model as CSV/JSON files in a new `knowledge_base/` folder, as proposed in KA-1.
   - Write a new layered engine alongside the old one.
   - Keep the old engine and tests untouched for comparison.
