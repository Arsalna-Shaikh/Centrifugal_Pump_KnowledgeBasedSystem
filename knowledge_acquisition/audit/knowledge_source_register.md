# Knowledge Source Register

Part of the KA-1 audit. Records the provenance of every important piece of knowledge found.

| Code | Category | What it means here |
|---|---|---|
| A | Existing project knowledge base | `data/*.csv`, `data/rules.json`, `src/inference_engine.py`, `src/app.py` — all written by `build_project.py` |
| B | Synthetic dataset | `data_preparation/` cleaned dataset and asset register — all written by `generate_dataset.py` |
| C | Derived dataset feature | computed in `data_preparation/scripts/preprocess_dataset.py` |
| D | Existing documented engineering reference | **only** the four KSB pages as summarised in [docs/SOURCE_NOTES.md](../../docs/SOURCE_NOTES.md) (also cited in the report `.docx`). Page contents were not re-read in this audit. |
| E | Requires independent engineering validation | no adequate source exists in the repository |

**No external reference was added by this audit.** A and B are both project-authored: B was designed after A and
mapped onto it, so A and B agreeing is not independent support. Every A or B item below therefore also needs E
before it is presented as engineering knowledge.

## 1. Documented engineering statements (D) — complete list
| ID | Statement as recorded | Location | Supports |
|---|---|---|---|
| D-1 | Routine maintenance checks include smooth running, motor power input, lubrication, shaft seals, alignment, flexible coupling elements, cavitation/erosion inspection, clearances, test runs (KSB "Maintenance") | [SOURCE_NOTES.md:5-6](../../docs/SOURCE_NOTES.md#L5-L6) | that these are relevant *inspection points*; not specific fault–symptom links |
| D-2 | Insufficient liquid (dry running) can lead to overheating, abrasion, seizure and vibration; dry-running protection may be required (KSB "Dry running") | [SOURCE_NOTES.md:8-9](../../docs/SOURCE_NOTES.md#L8-L9) | F07 cause (insufficient liquid), F07 → temperature rise, vibration; protection |
| D-3 | Operation in unfavourable low-flow ranges can cause vibration, cavitation, temperature rise and damage (KSB "Operating behaviour") | [SOURCE_NOTES.md:11-12](../../docs/SOURCE_NOTES.md#L11-L12) | low-flow operation (F11 context) → vibration, temperature rise, cavitation |
| D-4 | Commonly monitored variables: inlet pressure, bearing temperature, seal pressure/leakage, fluid temperature, vibration amplitude (KSB "Pipeline pump") | [SOURCE_NOTES.md:14-15](../../docs/SOURCE_NOTES.md#L14-L15) | relevance of these indicators; no thresholds |
| D-0 | "The numerical thresholds inside the code are academic prototype defaults, not values quoted from these sources" | [SOURCE_NOTES.md:17](../../docs/SOURCE_NOTES.md#L17) | establishes that all thresholds are E |

## 2. Register
| ID | Knowledge item | Cat. | Location | Notes |
|---|---|---|---|---|
| K-01 | Equipment = one generic centrifugal pump (pump-set boundary implied) | A | [app.py:6-7](../../src/app.py#L6-L7), components C09/C10 | no entity; boundary undefined |
| K-02 | 4 pump types; 40 assets; nameplate ratings | B | `pump_asset_register.csv`; [generate_dataset.py:30-35](../../data_preparation/scripts/generate_dataset.py#L30-L35) | rating ranges authored |
| K-03 | 10 components C01–C10 and their roles | A | [components.csv:2-11](../../data/components.csv#L2-L11) | roles are general descriptions → E light |
| K-04 | Additional parts named in text (volute, seal faces, flush line, check valve, windings, fan, lubricant, sump) | B | [generate_dataset.py:42-89](../../data_preparation/scripts/generate_dataset.py#L42-L89) | inferred, E |
| K-05 | Fault → component (one per fault) | A | faults.csv col 3 | single-component limitation; E |
| K-06 | 22 symptom definitions | A | [symptoms.csv:2-23](../../data/symptoms.csv#L2-L23) | names only; no measurement definitions |
| K-07 | 20 recorded symptom keys (+ `noise_high`) | B | [common.py:52](../../data_preparation/scripts/common.py#L52) | vocabulary aligned to A by design |
| K-08 | Sensor→symptom thresholds (12) | A | [inference_engine.py:28-49](../../src/inference_engine.py#L28-L49) | **E** (D-0) |
| K-09 | Operator-recording thresholds | B | [generate_dataset.py:205-218](../../data_preparation/scripts/generate_dataset.py#L205-L218) | E |
| K-10 | Relative thresholds incl. vibration zones 1.4/2.8/4.5 mm/s "ISO 10816-3-style", 85 dB(A) | C | [preprocess_dataset.py:27-53](../../data_preparation/scripts/preprocess_dataset.py#L27-L53) | standards named but **not verified** → E |
| K-11 | Relative indicators: Flow/Head/Current % of rated, speed deviation | C | preprocess_dataset.py (engineering_features) | method sound in principle; percentages E |
| K-12 | 14 faults with names/descriptions | A | [faults.csv:2-15](../../data/faults.csv#L2-L15) | E |
| K-13 | 10 faults + Normal + Unknown | B | [common.py:34-46](../../data_preparation/scripts/common.py#L34-L46) | merges F04/F06, F08/F14 |
| K-14 | Static safety priority per fault (F07 CRITICAL) | A | faults.csv col 4 | F07 partly D-2; others E |
| K-15 | Per-case severity Low→Critical | B | [generate_dataset.py:120-122](../../data_preparation/scripts/generate_dataset.py#L120-L122) | generator scale |
| K-16 | Severity → priority P1–P4; dry running always P1; response lags | B | [generate_dataset.py:124-128](../../data_preparation/scripts/generate_dataset.py#L124-L128) | policy, E |
| K-17 | 71 weighted fault–symptom links (weights 1–5) | A | [symptom_fault_weights.csv](../../data/symptom_fault_weights.csv) | weight semantics undocumented; E |
| K-18 | P(symptom \| fault) for 10 faults | B | cleaned dataset; `entity_relationship_mapping.md` §6 | generator re-statement; E |
| K-19 | F07 → temperature rise / vibration | A + B + D-2 | weights:34-39; SOURCE_NOTES:8 | best-supported fault–symptom links; still E (page not re-verified) |
| K-20 | Low-flow (F11) → vibration, temperature rise | A (temp rise) + B + D-3 | weights:56; SOURCE_NOTES:11 | vibration link absent in A |
| K-21 | 14 compound rules + bonuses | A | [rules.json](../../data/rules.json) | no source per rule; bonuses unexplained; E |
| K-22 | Rule firing statistics on synthetic data | B | `dataset_knowledge_mapping.md` §5 | consistency only |
| K-23 | Confidence = score / max score | A | [inference_engine.py:61,73](../../src/inference_engine.py#L61) | method, not knowledge; not a probability |
| K-24 | Cause content in fault descriptions and action details | A | faults.csv, maintenance_actions.csv | implicit; extracted in mapping §5.1 |
| K-25 | 37 root causes, 2–4 per fault | B | [generate_dataset.py:42-59](../../data_preparation/scripts/generate_dataset.py#L42-L59) | E for every link |
| K-26 | Fault → cause links supported by A text and B (A+B) | A, B | mapping §5.1 | consistency, E |
| K-27 | Insufficient liquid → dry running | A, B, D-2 | faults.csv:8; SOURCE_NOTES:8 | the only fault→cause link with a D statement |
| K-28 | Low-flow operation → cavitation | D-3 | SOURCE_NOTES:11 | absent from A and B as a cause |
| K-29 | Fault-as-cause chains (cavitation→impeller erosion; misalignment→bearing; dry running→seal; strainer→cavitation; soft foot→misalignment) | A, B | mapping §5.2 | E |
| K-30 | Misalignment-caused bearing failure shows coupling vibration | B | [generate_dataset.py:265](../../data_preparation/scripts/generate_dataset.py#L265) | the only cause-specific signature; E |
| K-31 | Cause → component | (none) | mapping §5.3 | inferred from wording; E |
| K-32 | 30 diagnostic test/finding names (spectrum, oil sample, NPSH margin, strainer Δp, insulation resistance, …) | B | [generate_dataset.py:61-73](../../data_preparation/scripts/generate_dataset.py#L61-L73) | candidate confirmation tests; E |
| K-33 | 16 maintenance actions with sequence, cost, downtime, details | A | [maintenance_actions.csv:2-17](../../data/maintenance_actions.csv#L2-L17) | inspection points partly D-1; E |
| K-34 | 13 dataset actions, one per fault | B | [generate_dataset.py:75-89](../../data_preparation/scripts/generate_dataset.py#L75-L89) | E |
| K-35 | Cause-specific corrective content in action details (A03, A05, A08, A09, A10, A13, A14, A15, A16) | A | maintenance_actions.csv | E |
| K-36 | Qualitative repair cost / downtime per fault and per action | A | faults.csv cols 5–6; maintenance_actions.csv cols 5–6 | two levels, inconsistent; E |
| K-37 | Numeric downtime/cost per event | B | [generate_dataset.py:90-93](../../data_preparation/scripts/generate_dataset.py#L90-L93) | authored medians; E |
| K-38 | Safety statements: no dry operation; stop/secure on CRITICAL; avoid near-zero flow; isolate before opening; qualified electrician | A (+ D-2 for dry running) | maint:7,10,13,14,17; app.py:70 | the only safety knowledge; E for anything more |
| K-39 | Preventive maintenance every ~2,000 operating hours | B | [generate_dataset.py:307](../../data_preparation/scripts/generate_dataset.py#L307) | authored policy; E |
| K-40 | Wear faults more likely with operating hours | B | [generate_dataset.py:40](../../data_preparation/scripts/generate_dataset.py#L40), l251 | authored; E |
| K-41 | Pump curve and current model (head rises, current falls as flow falls) | B | [generate_dataset.py:176-177](../../data_preparation/scripts/generate_dataset.py#L176-L177) | generic radial-pump assumption; conflicts with A (C-04); E |
| K-42 | Operators record ~85 % of sensor-visible symptoms; ~3 % false reports | B | generate_dataset.py:205-231 (recording rate l219, false reports l231) | authored; motivates "unknown" state |
| K-43 | Normal and Unknown as explicit outcomes | B | common.py:35,46 | design knowledge |

## 3. Summary by category
| Category | Items |
|---|---|
| D (documented reference) | 4 statements (D-1 … D-4) plus the disclaimer D-0; supports parts of K-14, K-19, K-20, K-27, K-28, K-33, K-38 |
| A only | components, KB symptoms/faults, weights, rules, thresholds, actions, qualitative cost/downtime |
| B only | equipment structure, causes, tests/findings, severity/priority policy, numeric cost/downtime |
| C | relative indicators and proposed thresholds |
| E | **every item**, including those with D support, because the D pages were not re-verified and say nothing about thresholds or weights |
