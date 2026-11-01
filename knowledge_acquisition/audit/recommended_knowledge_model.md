# Recommended Knowledge Model (proposal — not implemented)

Part of the KA-1 audit. A structure for an **explainable hybrid rule-based KBS** that removes the gaps in
`knowledge_gaps_and_conflicts.md`. It defines *where* knowledge goes and *what must accompany it*. It does not
populate validated content: every link will start as `unvalidated` until an engineering source is attached.

## 1. Design principles (each traced to an audit finding)
| Principle | Why (audit reference) |
|---|---|
| Separate **indicator → threshold → symptom**: a measurement, the rule that makes it abnormal, and the symbolic fact | thresholds are hard-coded and conflict three ways (C-01, C-02, C-03) |
| Separate **fault (failure mode)** from **root cause**, and allow a fault to be the cause of another fault | no cause layer (G-02); fault/cause level conflicts (C-07); chains (mapping §5.2) |
| Separate **hazard class** (fault type), **severity** (case) and **priority** (decision) | C-12 |
| Equipment context is explicit; thresholds can depend on equipment type and rating | G-01, C-02 |
| Every relationship carries **source IDs** and a **validation status** | G-08; source register |
| **Negative evidence** and symptom hierarchy/exclusion are first-class | G-09, G-15 |
| Observations can be **unknown**, distinct from absent | G-10 |
| Rules are **layered**, so inference genuinely chains (evidence → fault → cause → action) | first audit: single-pass scoring only |
| No numeric confidence until elicited; qualitative support levels with stated criteria | "do not assign arbitrary confidence" |
| Historical cases (the dataset) are stored **apart** from knowledge | dataset is synthetic and generator-derived (dataset mapping §0) |

## 2. Entities
| Entity | ID pattern | Key attributes | Seeded from (status) |
|---|---|---|---|
| Source | `SRC-nnn` | category (A–E), citation, location (file:line or URL), verified (bool), notes | source register |
| EquipmentType | `EQT-nn` | name, boundary (e.g. "pump set: pump + driver + coupling + baseplate + adjacent piping"), description | A (implicit), B types |
| EquipmentSubtype | `EQS-nn` | parent EQT, name (End Suction, Split Case, Multistage, Vertical Inline), power-curve type (for C-04) | B; curve type E |
| Component | `CMP-nnn` | name, level (`component` / `sub-component` / `external`), parent CMP, category, legacy_id (C01…) | A C01–C10 + B text mentions (mapping §1.2) |
| Indicator | `IND-nn` | quantity, unit, measurement method, reference (`absolute` / `pct_rated` / `pct_baseline`), allowed range | A inputs, B columns, C relative features |
| Threshold | `THR-nnn` | indicator, operator, value, reference, applies_to (EQT/EQS), alarm level, source_ids, status | A / B / C values as *candidates* (C-01) |
| Symptom | `SYM-nn` | key, name, kind (`sensor-derived` / `observed` / `test-finding`), legacy_id (S01…), synonyms | A 22 + B `noise_high`; synonyms from cleaning map |
| DiagnosticTest | `TST-nn` | name (vibration spectrum, oil analysis, NPSH margin, laser alignment, strainer Δp, insulation resistance, phase balance, soap test…), what it measures | B finding text (K-32), A action details |
| Fault | `FLT-nn` | name (failure mode only, no "/ cause"), description, hazard_class, legacy_id (F01…), status | A 14 faults (renamed where C-07 applies) |
| RootCause | `CAU-nnn` | name, category (`operational`, `process`, `installation`, `wear`, `contamination`, `electrical`, `maintenance`), may_be_fault (FLT id) | B 37 causes + A implied causes |
| MaintenanceAction | `ACT-nnn` | name, purpose (`investigate` / `correct` / `prevent` / `make-safe`), steps, competence, isolation_required, cost_class, downtime_class, legacy_id (A01…) | A 16 + B 13 |
| SafetyPrecaution | `SAF-nn` | statement, trigger, source_ids | A statements (K-38), D-2 |
| Rule | `RUL-nnn` | layer, conditions, conclusion, support_level, explanation template, source_ids, status, legacy_id (R01…) | A R01–R14 (layer 2) |
| Case *(outside the KB)* | `CASE-…` | observations, ground truth, provenance | `data_preparation/` dataset — test/historical store only |

## 3. Relationships
All relationships share: `id`, `source_ids` (≥ 1), `status` (`unvalidated` / `validated` / `rejected`),
`support_level` (see §4), `notes`.

| Relationship | Domain → Range | Extra attributes | Example (illustrative; status as found) |
|---|---|---|---|
| `has_subtype` | EQT → EQS | — | pump set → End Suction (B) |
| `has_component` / `part_of` | EQT → CMP, CMP → CMP | — | Mechanical seal ← seal faces (B text) |
| `measures` | IND → CMP | sensor location | bearing temperature → bearings (A) |
| `abstracts_to` | THR → SYM (via IND) | — | IND bearing temp ≥ 80 °C → bearing_temp_high (A, E) |
| `implies` | SYM → SYM | — | no_flow ⇒ flow_low (A behaviour, G-15) |
| `excludes` | SYM ↔ SYM | — | discharge_pressure_high ⊥ discharge_pressure_low (design) |
| `fault_located_in` | FLT → CMP | role: `origin` / `damage` | Cavitation: origin suction side, damage impeller (G-17, E) |
| `manifests_as` | FLT → SYM | typicality (`usual` / `sometimes` / `rare`), specificity (`specific` / `shared`), direction (for ± indicators), conditions (e.g. pump subtype) | F07 → seal_temp_high (A+B+D-2) |
| `argues_against` | SYM → FLT | — | none known yet (G-09) |
| `caused_by` | FLT → CAU | typical (bool) | Dry running ← insufficient liquid (A+B+D-2) |
| `leads_to` | FLT → FLT | mechanism text | Cavitation → Impeller damage (A04, B) |
| `cause_located_at` | CAU → CMP | — | Clogged strainer → suction strainer (inferred, E) |
| `confirmed_by` | CAU → TST | expected finding | Bearing fatigue → spectrum shows defect frequencies (B, E) |
| `indicated_by` | CAU → SYM | — | Misalignment-caused bearing failure → coupling_vibration (B only) |
| `recommends` | FLT → ACT | sequence, purpose | F01 → A01 then A02 (A) |
| `corrects` | ACT → CAU | — | A05 align ← soft foot / pipe strain checked first (A) |
| `requires_precaution` | FLT / ACT → SAF | — | A12 → isolate before opening (A) |
| `has_cost_downtime` | ACT → (class) | cost_class, downtime_class, numeric range if sourced | A qualitative; B numeric = placeholder |

## 4. Uncertainty, conflicting evidence and unknowns
**Support level** (qualitative, assigned only by criteria — never invented):

| Level | Criterion |
|---|---|
| `documented` | a verified external source (D re-verified, standard, OEM, textbook) states the relationship |
| `consistent` | stated in the KB (A) and consistent with the dataset (B), no external source yet |
| `candidate` | appears in only one project source (A or B) |
| `disputed` | sources disagree (e.g. C-04, C-09 items) |
| `unknown` | no evidence |

- **Optional numeric strength.** A numeric strength (certainty factor or likelihood) may be added later as a
  *separate* attribute. It should be elicited from an expert or estimated from real data, and it must record its
  own source. The current KB weights 1–5 can be carried over as `legacy_weight` for comparison only.
- **Observation states.** Each symptom takes one of `present`, `absent` or `unknown`. Unknown never counts as
  absent.
- **Conflicting evidence:**
  - `excludes` pairs present together → data-quality warning.
  - `argues_against` lowers a hypothesis.
  - Competing faults are kept as a ranked differential.
  - When no hypothesis meets a minimum support, the result is the explicit outcome **Unknown — further
    investigation** (the dataset already uses this class).
- **Derived values.** A symptom derived from an imputed or estimated indicator value is marked `unknown`. This
  mirrors the data-preparation rule.

## 5. Rule layers (forward chaining across layers)
| Layer | Rule kind | IF | THEN | Example from existing knowledge |
|---|---|---|---|---|
| 1 Evidence abstraction | threshold rules | indicator value (+ equipment context) | symptom present/absent/unknown | A engine thresholds, relative versions from C |
| 2 Fault hypothesis | diagnostic rules | symptoms (all / any / none-of) | fault hypothesis + support | R01–R14 (re-checked for C-05, C-06, C-13) |
| 3 Cause hypothesis | cause rules | fault hypothesis + symptoms / test findings | cause hypothesis | "Bearing failure ∧ coupling_vibration → suspect misalignment cause" (B only, E) |
| 4 Test request | investigation rules | competing hypotheses with no discriminating evidence | request a diagnostic test (TST) | F04 vs F10 vs F06 → request performance check / strainer Δp (E) |
| 5 Recommendation | action rules | confirmed/suspected cause or fault + severity | ordered actions, priority | A action sequences |
| 6 Safety (override) | safety rules | hazard class / specific symptoms | precaution, stop/secure message — regardless of rank | F07 "do not continue dry operation" (A, D-2) |

Each conclusion carries an explanation trace:
indicator → threshold → symptom → rule → fault → cause → action, with the source IDs at every step.

## 6. Proposed file layout (CSV/JSON, same style as the existing KB)
```
knowledge_base/
  sources.csv              SRC
  equipment_types.csv      EQT, EQS
  components.csv           CMP (+ part_of)
  indicators.csv           IND
  thresholds.csv           THR
  symptoms.csv             SYM
  symptom_relations.csv    implies / excludes
  tests.csv                TST
  faults.csv               FLT (+ hazard_class)
  fault_components.csv     fault_located_in (role)
  fault_symptoms.csv       manifests_as / argues_against
  causes.csv               CAU
  fault_causes.csv         caused_by
  fault_chains.csv         leads_to
  cause_components.csv     cause_located_at
  cause_tests.csv          confirmed_by
  actions.csv              ACT
  fault_actions.csv        recommends
  cause_actions.csv        corrects
  safety.csv               SAF + requires_precaution
  rules.json               RUL (layer, conditions, conclusion, explanation, source_ids, status)
```
Keep a crosswalk from legacy IDs (C01, S01, F01, A01, R01) so the current engine and tests remain traceable.

## 7. Decisions needed before building
1. **Fault granularity.** Keep F04/F06 and F08/F14 separate (only with a discriminating test) or merge them as the
   dataset does (C-08)?
2. **F06, F11, F13, F14.** Should these be faults, causes, or both via `may_be_fault` (C-07)?
3. **Threshold reference.** Rated values, healthy baseline, or both per indicator (C-03)? This also decides
   whether equipment ratings become required inputs.
4. **Symptom vocabulary.** Resolve G-15: drop or merge flow_fluctuation and efficiency_low; add noise_high;
   distinguish speed instability from speed deviation.
5. **Equipment boundary.** Pump set (current implicit choice) or pump only.
6. **External sources.** Which ones to obtain for category E validation: standards, textbook, OEM manuals,
   site procedures. The KSB pages in SOURCE_NOTES should at least be re-read and cited per relationship.
7. **Uncertainty representation.** Qualitative support levels only, or also elicited certainty factors.
