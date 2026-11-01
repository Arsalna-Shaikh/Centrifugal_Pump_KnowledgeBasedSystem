# Existing Knowledge-Base Inventory

Part of the KA-1 audit (`knowledge_acquisition_audit.md`). Read-only inventory of the knowledge held by the
existing KBS at commit `1aaa2f8`. Line numbers refer to that commit (files unchanged at audit time). CSV line 1
is the header, so the first record is line 2.

## 1. Knowledge-bearing files
| File | Holds | Records |
|---|---|---|
| [data/components.csv](../../data/components.csv) | components | 10 (C01–C10) |
| [data/symptoms.csv](../../data/symptoms.csv) | symptom vocabulary | 22 (S01–S22) |
| [data/faults.csv](../../data/faults.csv) | faults + safety priority, repair cost, downtime | 14 (F01–F14) |
| [data/symptom_fault_weights.csv](../../data/symptom_fault_weights.csv) | weighted fault–symptom links | 71 |
| [data/rules.json](../../data/rules.json) | compound IF–THEN rules with bonus | 14 (R01–R14) |
| [data/maintenance_actions.csv](../../data/maintenance_actions.csv) | maintenance actions per fault | 16 (A01–A16) |
| [src/inference_engine.py](../../src/inference_engine.py) | sensor → symptom thresholds, scoring, safety ranking | 12 threshold rules |
| [src/app.py](../../src/app.py) | input vocabulary shown to users | 9 numeric + 10 boolean inputs |
| [docs/SOURCE_NOTES.md](../../docs/SOURCE_NOTES.md) | the only documented external sources | 4 KSB lexicon pages |
| [build_project.py](../../build_project.py) | generator that wrote all of the above | — |

`data/demo_cases.json`, `data/diagnostic_cases.csv`, `data/operational_sensor_log.csv` and
`data/evaluation_results.csv` are synthetic test data generated from the same weight table
([build_project.py:67-82](../../build_project.py#L67-L82)); they contain no independent knowledge.

**Provenance.** Every entity and number above was written by `build_project.py`. The only external sources are the
four KSB pages summarised in [docs/SOURCE_NOTES.md](../../docs/SOURCE_NOTES.md#L5-L14). The note itself states that
the numeric thresholds are "academic prototype defaults, not values quoted from these sources"
([SOURCE_NOTES.md:17](../../docs/SOURCE_NOTES.md#L17)). No source is recorded for any weight, bonus or link.

## 2. Equipment
There is **no equipment entity**. The equipment is implicit: one generic "centrifugal pump" in the
titles/captions ([app.py:6-7](../../src/app.py#L6-L7)). There is no pump type, size, rating, duty point, fluid or
asset identifier. The component list includes the motor (C09) and baseplate (C10), so the implied boundary is
the **pump set** (pump + driver + coupling + baseplate + adjacent suction/discharge piping), not the pump casing
alone.

## 3. Components ([components.csv:2-11](../../data/components.csv#L2-L11))
| ID | Name | Category | Line | Faults pointing to it (faults.csv `component_id`) |
|---|---|---|---|---|
| C01 | Pump Casing | Hydraulic | 2 | F07 |
| C02 | Impeller | Hydraulic | 3 | F02, F04, F10 |
| C03 | Shaft | Mechanical | 4 | F03 |
| C04 | Bearings | Mechanical | 5 | F01 |
| C05 | Mechanical Seal | Sealing | 6 | F05 |
| C06 | Coupling | Mechanical | 7 | F09 |
| C07 | Suction Line / Strainer | Hydraulic | 8 | F06, F12 |
| C08 | Discharge Line / Valve | Hydraulic | 9 | F11 |
| C09 | Electric Motor | Electrical | 10 | F08, F14 |
| C10 | Baseplate / Foundation | Structural | 11 | F13 |

Observations:
- **Single component per fault.** Each fault has exactly one `component_id`, but several faults involve more
  than one component. Dry running is assigned to the casing (C01) while its damage is to the seal and bearings.
  Misalignment is assigned to the shaft (C03) though the coupling is involved. Cavitation is assigned to the
  impeller (C02), the damage location, though its origin is suction conditions (C07).
- **Combined items.** C07 and C08 each combine a line, a strainer and a valve. These are piping/system items
  rather than pump parts.
- **Missing parts.** No sub-components (wear rings, volute, seal faces, seal flush/support system, lubricant,
  motor windings, cooling fan) and no external system items (supply tank/sump, power supply, process).

## 4. Symptoms ([symptoms.csv:2-23](../../data/symptoms.csv#L2-L23))
| ID | Key | Name | Category | Line | How obtained in the app | Faults linked (count) |
|---|---|---|---|---|---|---|
| S01 | vibration_high | High overall vibration | Mechanical | 2 | vibration ≥ 6.0 mm/s ([engine:28](../../src/inference_engine.py#L28)) | 10 |
| S02 | bearing_temp_high | Bearing temperature high | Thermal | 3 | ≥ 80 °C ([engine:29](../../src/inference_engine.py#L29)) | 5 |
| S03 | grinding_noise | Abnormal grinding/rumbling noise | Acoustic | 4 | checkbox `abnormal_noise` ([app:33](../../src/app.py#L33), [engine:40](../../src/inference_engine.py#L40)) | 6 |
| S04 | crackling_noise | Crackling / gravel-like noise | Acoustic | 5 | checkbox ([app:34](../../src/app.py#L34)) | 2 |
| S05 | discharge_pressure_low | Low discharge pressure | Hydraulic | 6 | < 4.2 bar absolute ([engine:33](../../src/inference_engine.py#L33)) | 5 |
| S06 | flow_low | Low flow rate | Hydraulic | 7 | < 75 % of healthy baseline ([engine:31](../../src/inference_engine.py#L31)) | 7 |
| S07 | suction_pressure_low | Low suction pressure / high vacuum | Hydraulic | 8 | < 0.70 bar(a) ([engine:35](../../src/inference_engine.py#L35)) | 2 |
| S08 | seal_leakage | Visible seal leakage | Visual | 9 | manual ([app:40](../../src/app.py#L40)) | 1 |
| S09 | motor_current_high | Motor current high | Electrical | 10 | > 38 A absolute ([engine:36](../../src/inference_engine.py#L36)) | 6 |
| S10 | motor_temp_high | Motor temperature high | Thermal | 11 | ≥ 80 °C ([engine:30](../../src/inference_engine.py#L30)) | 2 |
| S11 | pressure_fluctuation | Pressure fluctuating | Hydraulic | 12 | ≥ 10 % ([engine:38-39](../../src/inference_engine.py#L38-L39)) | 2 |
| S12 | flow_fluctuation | Flow fluctuating | Hydraulic | 13 | **always added together with S11** ([engine:39](../../src/inference_engine.py#L39)) | 2 |
| S13 | no_flow | No / near-zero flow | Hydraulic | 14 | < 10 % of baseline (also sets S06) ([engine:32](../../src/inference_engine.py#L32)) | 1 |
| S14 | prime_failure | Pump fails to prime | Operational | 15 | checkbox "Pump is primed" = off ([engine:49](../../src/inference_engine.py#L49)) | 2 |
| S15 | coupling_vibration | Shaft/coupling vibration dominant | Mechanical | 16 | manual ([app:41](../../src/app.py#L41)) | 3 |
| S16 | seal_temp_high | Seal area temperature high | Thermal | 17 | ≥ 85 °C ([engine:37](../../src/inference_engine.py#L37)) | 2 |
| S17 | discharge_pressure_high | Discharge pressure unusually high | Hydraulic | 18 | > 6.0 bar absolute ([engine:34](../../src/inference_engine.py#L34)) | 1 |
| S18 | speed_unstable | Motor speed unstable | Electrical | 19 | manual ([app:43](../../src/app.py#L43)) | 2 |
| S19 | base_vibration | Localized baseplate vibration | Mechanical | 20 | manual ([app:42](../../src/app.py#L42)) | 1 |
| S20 | air_bubbles | Air bubbles / frothy discharge | Visual | 21 | checkbox ([app:35](../../src/app.py#L35)) | 1 |
| S21 | efficiency_low | Efficiency / developed head reduced | Performance | 22 | manual ([app:44](../../src/app.py#L44)) | 6 |
| S22 | rapid_temp_rise | Rapid temperature rise with low flow | Thermal | 23 | manual ([app:45](../../src/app.py#L45)) | 2 |

## 5. Faults ([faults.csv:2-15](../../data/faults.csv#L2-L15))
| ID | Name | Component | Safety | Repair cost | Downtime | Line | Cause content embedded in the description |
|---|---|---|---|---|---|---|---|
| F01 | Bearing Wear / Failure | C04 | HIGH | Medium | Medium | 2 | "lubrication-related distress" |
| F02 | Cavitation | C02 | HIGH | Low | Medium | 3 | "due to inadequate suction conditions" |
| F03 | Shaft Misalignment | C03 | HIGH | Medium | Medium | 4 | — |
| F04 | Impeller Blockage / Fouling | C02 | MEDIUM | Low | Medium | 5 | "deposits or foreign material" |
| F05 | Mechanical Seal Failure | C05 | HIGH | Medium | Medium | 6 | "worn, damaged, or thermally distressed" |
| F06 | Suction Blockage / Clogged Strainer | C07 | HIGH | Low | Low | 7 | the name itself is a cause ("clogged strainer") |
| F07 | Dry Running / Loss of Prime | C01 | **CRITICAL** | Medium | High | 8 | "insufficient liquid" |
| F08 | Motor Overload | C09 | HIGH | Medium | Medium | 9 | — |
| F09 | Coupling Damage / Looseness | C06 | HIGH | Medium | Medium | 10 | "flexible element wear, looseness" |
| F10 | Impeller Damage / Erosion | C02 | HIGH | High | High | 11 | "eroded, cracked" |
| F11 | Discharge Restriction / Closed Valve | C08 | HIGH | Low | Low | 12 | the name itself is a cause ("closed valve") |
| F12 | Air Ingress on Suction Side | C07 | HIGH | Low | Medium | 13 | "air enters suction piping or fittings" |
| F13 | Base / Foundation Looseness | C10 | MEDIUM | Medium | Medium | 14 | "loose hold-down bolts, soft foot, weak foundation" |
| F14 | Electrical Supply Imbalance | C09 | HIGH | Medium | Medium | 15 | the fault is itself a cause of motor heating |

Safety priority is a **static attribute of the fault type** (`SAFETY_RANK`,
[engine:9](../../src/inference_engine.py#L9)). There is no per-case severity. The app raises a CRITICAL banner only when
the top-ranked fault is CRITICAL ([app.py:70](../../src/app.py#L70)).

## 6. Weighted fault–symptom links ([symptom_fault_weights.csv](../../data/symptom_fault_weights.csv))
Weights are integers 1–5. The meaning of a weight (likelihood? specificity? expert strength?) is not documented
anywhere, and no link has a source. Max score = Σ weights + Σ rule bonuses for that fault (used as the denominator
of the "confidence" percentage, [engine:61,73](../../src/inference_engine.py#L61)).

| Fault | Lines | Links (weight) | Max score |
|---|---|---|---|
| F01 | 2–6 | vibration_high 5, bearing_temp_high 5, grinding_noise 4, motor_current_high 2, efficiency_low 1 | 21 |
| F02 | 7–14 | crackling_noise 5, suction_pressure_low 5, vibration_high 4, pressure_fluctuation 4, flow_fluctuation 4, discharge_pressure_low 3, flow_low 3, efficiency_low 3 | 36 |
| F03 | 15–19 | vibration_high 5, coupling_vibration 5, bearing_temp_high 3, motor_current_high 2, grinding_noise 2 | 21 |
| F04 | 20–24 | flow_low 5, efficiency_low 5, discharge_pressure_low 4, vibration_high 2, motor_current_high 2 | 22 |
| F05 | 25–28 | seal_leakage 5, seal_temp_high 4, vibration_high 2, bearing_temp_high 1 | 17 |
| F06 | 29–33 | suction_pressure_low 5, flow_low 5, discharge_pressure_low 4, efficiency_low 3, crackling_noise 2 | 23 |
| F07 | 34–39 | no_flow 5, prime_failure 5, rapid_temp_rise 5, seal_temp_high 4, bearing_temp_high 3, grinding_noise 2 | 31 |
| F08 | 40–44 | motor_current_high 5, motor_temp_high 5, vibration_high 2, speed_unstable 2, flow_low 1 | 20 |
| F09 | 45–48 | coupling_vibration 5, vibration_high 4, grinding_noise 3, bearing_temp_high 2 | 18 |
| F10 | 49–53 | efficiency_low 5, vibration_high 4, flow_low 4, discharge_pressure_low 4, grinding_noise 2 | 23 |
| F11 | 54–58 | discharge_pressure_high 5, flow_low 5, rapid_temp_rise 4, motor_current_high 2, efficiency_low 2 | 24 |
| F12 | 59–64 | air_bubbles 5, flow_fluctuation 4, pressure_fluctuation 4, prime_failure 3, discharge_pressure_low 3, flow_low 3 | 27 |
| F13 | 65–68 | base_vibration 5, vibration_high 4, coupling_vibration 2, grinding_noise 1 | 17 |
| F14 | 69–72 | motor_temp_high 5, motor_current_high 4, speed_unstable 4, vibration_high 2 | 20 |

No negative (counter-evidence) weights exist, although the generator comments that negative weights would mean
contradiction ([build_project.py:66](../../build_project.py#L66)).

## 7. Compound rules ([rules.json](../../data/rules.json))
All conditions are AND-ed; a rule adds its `bonus` to its fault's score. Every condition also appears as a
weighted link of the same fault, so a firing rule *double-counts* evidence already scored.

| ID | Line | IF (all) | THEN | Bonus | Remark |
|---|---|---|---|---|---|
| R01 | 3 | vibration_high, bearing_temp_high, grinding_noise | F01 | 4 | |
| R02 | 14 | crackling_noise, suction_pressure_low, pressure_fluctuation | F02 | 5 | |
| R03 | 25 | coupling_vibration, vibration_high, bearing_temp_high | F03 | 4 | overlaps R01/R09 symptoms |
| R04 | 36 | flow_low, discharge_pressure_low, efficiency_low | F04 | 4 | **subset of R10** |
| R05 | 47 | seal_leakage, seal_temp_high | F05 | 5 | |
| R06 | 57 | suction_pressure_low, flow_low, discharge_pressure_low | F06 | 4 | all three conditions are also F02 links |
| R07 | 68 | no_flow, prime_failure, rapid_temp_rise | F07 | 7 | `rapid_temp_rise` is manual-only |
| R08 | 79 | motor_current_high, motor_temp_high | F08 | 5 | **subset of R14** |
| R09 | 89 | coupling_vibration, grinding_noise | F09 | 4 | |
| R10 | 99 | flow_low, discharge_pressure_low, vibration_high, efficiency_low | F10 | 4 | |
| R11 | 111 | discharge_pressure_high, flow_low, rapid_temp_rise | F11 | 6 | |
| R12 | 122 | air_bubbles, flow_fluctuation, pressure_fluctuation | F12 | 5 | flow_fluctuation is auto-implied by pressure_fluctuation |
| R13 | 133 | base_vibration, vibration_high | F13 | 5 | |
| R14 | 143 | motor_temp_high, speed_unstable, motor_current_high | F14 | 5 | |

Bonus values (4–7) have no documented rationale.

## 8. Maintenance actions ([maintenance_actions.csv:2-17](../../data/maintenance_actions.csv#L2-L17))
| ID | Fault | Seq | Action | Cost | Downtime | Line | Cause / safety content in `details` |
|---|---|---|---|---|---|---|---|
| A01 | F01 | 1 | Inspect bearing lubrication and condition | LOW | LOW | 2 | lubricant level/condition |
| A02 | F01 | 2 | Replace damaged bearing | MEDIUM | MEDIUM | 3 | "if inspection confirms…" |
| A03 | F02 | 1 | Improve suction conditions / verify NPSH margin | LOW | MEDIUM | 4 | liquid level, suction losses, temperature, valves, piping restriction |
| A04 | F02 | 2 | Inspect impeller for cavitation erosion | MEDIUM | MEDIUM | 5 | links F02 → impeller erosion (F10) |
| A05 | F03 | 1 | Laser/dial align motor and pump shafts | MEDIUM | MEDIUM | 6 | "after verifying soft foot and pipe strain" |
| A06 | F04 | 1 | Clean impeller and internal passages | LOW | MEDIUM | 7 | "Isolate pump" |
| A07 | F05 | 1 | Inspect/replace mechanical seal | MEDIUM | MEDIUM | 8 | seal faces, flush plan, elastomers, sleeve |
| A08 | F06 | 1 | Clean suction strainer and inspect suction line | LOW | LOW | 9 | suction valve open |
| A09 | F07 | 1 | Stop pump and restore prime/liquid supply | LOW | HIGH | 10 | "Do not continue dry operation"; investigate why prime was lost |
| A10 | F08 | 1 | Inspect motor load and process operating point | LOW | MEDIUM | 11 | mechanical drag, process overload |
| A11 | F09 | 1 | Inspect and repair/replace coupling elements | MEDIUM | MEDIUM | 12 | |
| A12 | F10 | 1 | Inspect/repair or replace impeller | HIGH | HIGH | 13 | "Open pump after isolation" |
| A13 | F11 | 1 | Open/verify discharge valve and minimum-flow path | LOW | LOW | 14 | "avoid prolonged near-zero-flow operation" |
| A14 | F12 | 1 | Leak-test suction piping and fittings | LOW | MEDIUM | 15 | fittings/gaskets |
| A15 | F13 | 1 | Inspect hold-down bolts, soft foot and foundation | MEDIUM | MEDIUM | 16 | |
| A16 | F14 | 1 | Check phase voltage/current balance and connections | MEDIUM | MEDIUM | 17 | "Qualified electrical personnel" |

12 of 14 faults have a single action. Actions are linked to faults only, never to causes.

## 9. Causes
**No cause entity exists.** Cause knowledge is embedded as free text in fault names (F06, F11, F14), fault
descriptions (section 5) and action details (section 8). It is extracted and classified in
`entity_relationship_mapping.md` §5.

## 10. Thresholds, scoring and uncertainty
- **12 sensor thresholds**, hard-coded in Python ([engine:28-49](../../src/inference_engine.py#L28-L49)), not stored in the KB.
- **Absolute thresholds.** Pressure and current thresholds are absolute (4.2 / 6.0 bar, 38 A). They only make
  sense for one specific pump size.
- **Two reference points for flow.** Flow is a percentage of a "healthy baseline" ([app.py:25](../../src/app.py#L25)),
  not of the rated flow.
- **Uncertainty.** Confidence = score / max score ([engine:73](../../src/inference_engine.py#L73)). It is not a probability.
  There are no certainty factors, no negative evidence and no "unknown" input state: the UI fields default to
  normal values.

## 11. Terminology issues found in the existing KB
| Issue | Where |
|---|---|
| Value-case inconsistency: `Medium` in faults.csv vs `MEDIUM` in maintenance_actions.csv | faults.csv:2-15, maintenance_actions.csv:2-17 |
| Composite fault names joined by "/" mix fault mode and cause (e.g. "Dry Running / Loss of Prime", "Discharge Restriction / Closed Valve") | faults.csv:7,8,12 |
| `efficiency_low` ("Efficiency / developed head reduced") overlaps `discharge_pressure_low` (head reduced) | symptoms.csv:22 vs :6 |
| `flow_fluctuation` cannot be observed independently in the app (always co-derived with pressure fluctuation) | engine:38-39 |
| `rapid_temp_rise` is defined "with low flow", i.e. it embeds another symptom | symptoms.csv:23 |
| `no_flow` implies `flow_low` (both set below 10 %) — a hierarchy that is not declared | engine:31-32 |
| UI label "Grinding/rumbling noise" sets `grinding_noise`; input name is `abnormal_noise` | app.py:33, engine:40 |
| "Pump fails to prime" (symptom) vs "Loss of Prime" (fault name) — same phenomenon at two levels | symptoms.csv:15, faults.csv:8 |
| Two faults per component without a discriminating symptom: F08 vs F14 share motor_current_high and motor_temp_high; F14 adds speed_unstable only | weights 40–44, 69–72 |
