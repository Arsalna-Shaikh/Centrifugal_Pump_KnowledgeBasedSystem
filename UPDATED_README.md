# Centrifugal Pump Knowledge-Based System

**Course:** CT-359 Knowledge Based System, Complex Computing Problem (NED University of Engineering and Technology)

An explainable knowledge-based system that diagnoses faults in centrifugal pump sets and recommends maintenance.
Engineering knowledge is held in a structured, source-referenced knowledge base. A stratified forward-chaining
engine turns measurements and observations into fault hypotheses, root causes, test requests, safety warnings and
prioritised maintenance actions, and explains every conclusion.

> **Academic prototype.** The dataset is synthetic and all numeric symptom thresholds are provisional. Results are
> not evidence of diagnostic accuracy on real equipment, and safety messages do not replace site procedures.

---

## 1. Main features
- **Structured knowledge base**: equipment, components, indicators, thresholds, symptoms, faults, root causes,
  diagnostic tests, maintenance actions and safety rules, linked by 282 typed relationships and 36 production rules.
  Every item records its source and a support level.
- **Forward-chaining inference** in ordered layers (evidence → faults → negative evidence → causes and chains →
  test requests → actions and safety).
- **Three-state evidence**: present, absent or unknown. Unknown is never treated as absent.
- **Conflict handling**: sensor vs observation disagreements, mutually exclusive symptoms, physically inconsistent
  pressures, estimated values and competing faults are all detected and reported.
- **Equipment-specific thresholds**: flow, head and current judged relative to the pump's rated or healthy-baseline
  values. Optional user-entered site limits cover thresholds with no sourced value.
- **Decision support**: safety warnings checked against every hypothesis, work precautions, maintenance actions with
  priority (P1/P2/P3) and qualitative cost and downtime, and requests for discriminating tests.
- **Explanations**: each hypothesis shows its labelled evidence (Present / Absent / Unknown / Not used), the rules
  that fired, their sources and assumptions, and what is still missing.
- **Streamlit interface** with example cases, help text on every input, and a downloadable plain-text report.

## 2. System architecture
```
Streamlit page (src/pages/1_New_KBS_Diagnosis.py)
        │ inputs                                    ▲ report
        ▼                                           │
UI adapter (decision_support/ui_adapter.py)    Decision support (decision_support/report.py)
  validation, blank = unknown, builds a Case        ▲ engine result
        │                                           │
        └──────────► Inference engine (kbs_engine/engine.py) ◄── Knowledge base (knowledge_base/*.csv, *.json)
                         stratified forward chaining              loaded read-only by kbs_engine/knowledge.py
```
Offline inputs: `knowledge_acquisition/` (how the knowledge was collected and assessed) and `data_preparation/`
(the synthetic dataset, used for testing).

## 3. Knowledge representation
A hybrid formalism:
- **Frame-like records**: CSV tables with typed attributes, e.g. a fault's hazard class, cost class and downtime
  class, each with its own provenance.
- **Typed relationships** (`relationships.csv`, 15 types): `manifests_as`, `caused_by`, `confirmed_by`,
  `recommends`, `corrects`, `leads_to`, `argues_against`, `requires_precaution`, `implies`, `excludes` and others.
  They form a lightweight ontology / knowledge graph.
- **Production rules** (`diagnostic_rules.json`, 36 rules): 19 fault rules, 3 negative-evidence rules, 9 cause rules,
  2 fault-chain rules and 3 test-request rules.

**Support levels:**
- **Strong**: an independent source that was read.
- **Moderate**: a manufacturer or trade source.
- **Definitional**: true by definition or design.
- **Unvalidated**: project-authored, with no external source.
- **Disputed**: contradicted by an independent source.

Knowledge support is always kept separate from diagnostic likelihood. Vocabularies and policies are in
`knowledge_base/kb_meta.json`.

| Contents | Count |
|---|---|
| Equipment class / parameters | 1 / 12 |
| Components | 14 |
| Indicators / thresholds | 12 / 26 (25 Unvalidated, 1 Definitional) |
| Symptoms | 23 |
| Faults + outcomes | 12 + 2 (Normal, Unknown) |
| Root causes / diagnostic tests | 39 / 12 |
| Maintenance actions / safety rules | 17 / 4 |
| Sources | 16 external engineering sources and 3 research leads |

## 4. Dataset and knowledge acquisition
**Knowledge acquisition** (`knowledge_acquisition/`) had three documented stages:
- **KA-1**: an entity-relationship register, plus the knowledge gaps and conflicts found.
- **KA-2**: research across 16 external sources (DOE / Hydraulic Institute, KSB, Grundfos, ITT Goulds, SKF and others),
  with each finding graded.
- **KA-3**: the final knowledge model and its design decisions.

**Synthetic dataset** (`data_preparation/`, seed 359): 40 pumps of four types, 2023–2025.
- **Counts:** 7,354 raw rows, 7,210 after cleaning; the preprocessed file has 123 columns.
- **Injected problems:** 19 deliberate data-quality problem types, so that the cleaning steps can be tested.
- **Pipeline:** quality analysis, cleaning, preprocessing, exploratory analysis (13 figures, 4 notebooks) and
  validation (19/19 checks pass).

The dataset is **not real plant data**. It is used only to test the engine, never as ground truth.

## 5. Inference engine and forward chaining
`kbs_engine/engine.py` runs the rule layers in order. Each layer runs to a fixed point (until no rule adds a new
fact) before the next starts:

| Layer | What it does |
|---|---|
| L1 Evidence | Measurements → symptom states, using the most specific threshold basis available (healthy baseline, then % of rated, then absolute). Missing, estimated or inconsistent readings give *unknown*. |
| L2 Faults | A rule fires when all conditions hold. When none fails but some are unknown, the fault becomes *pending* and the missing information is requested. |
| L2 Negative | Lowers a hypothesis by one level, or blocks it on *known* absence |
| L3 Causes / chains | Root causes and fault → fault chains from earlier conclusions plus symptoms or test results |
| L4 Tests | Discriminating tests when specific hypotheses compete |
| L5 Actions / safety | Actions with precautions; every safety rule is checked against every hypothesis |

**Status and outcome:**
- **Status ladder:** blocked < unlikely < pending < possible < likely < confirmed. Rules with Unvalidated support
  are shown at most as *possible*.
- **Diagnosis**: at least one fault is likely or confirmed.
- **Normal**: every assessable symptom is known to be absent.
- **Unknown**: anything else. Further investigation is recommended.

## 6. Decision support
`decision_support/report.py` turns the engine result into a report with:
- **Headline and safety:** a headline; operating safety warnings (shown first); work precautions.
- **Hypotheses:** grouped by status, each with supporting, contradicting and missing evidence and a rule-by-rule
  explanation with sources.
- **Root causes:** concluded and candidate causes, with the tests that would confirm them, plus fault chains.
- **Next steps:** requested tests and the observations still needed.
- **Maintenance actions:** each with its priority, purpose, competence, precautions, and qualitative cost and
  downtime.
- **Text report:** a plain-text version, which the page offers for download.

**Maintenance priority:**
- **P1-immediate**: a make-safe action, or an action for a fault under an active safety warning.
- **P2-high**: an action for a likely or confirmed fault or cause.
- **P3-planned**: everything else.

Priority, cost and downtime are **Unvalidated** project policy and classes. They never change the diagnosis.

## 7. Repository structure (current KBS)
```
knowledge_base/             structured knowledge (CSV + JSON) and validate_kb.py
kbs_engine/                 knowledge loader, inference engine, explanation, dataset adapters
  tests/test_engine.py
  reports/dataset_consistency.md
decision_support/           report builder and UI adapter
  tests/                    report, adapter, Streamlit page, scenarios, cost/priority, page-audit tests
src/pages/1_New_KBS_Diagnosis.py   Streamlit user interface
knowledge_acquisition/      KA-1 audit, KA-2 research, KA-3 final knowledge model
data_preparation/           synthetic dataset pipeline (own README, requirements and .venv)
submission/                 final report (DOCX + PDF) and its figures
requirements.txt            dependencies for the application and tests
```

## 8. Installation and setup
Requires **Python 3.11** (tested with 3.11.9 on Windows 11). From the repository root, in PowerShell:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```
If PowerShell refuses to run `Activate.ps1`, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or call `.\.venv\Scripts\python.exe` directly.

The inference engine and the knowledge-base validator use only the Python standard library. Streamlit and pandas
are needed for the user interface, and pytest for the test suite.

## 9. Running the Streamlit application
```powershell
streamlit run src\pages\1_New_KBS_Diagnosis.py
```
Then open the URL that Streamlit prints (normally http://localhost:8501). To try the system quickly:
1. Choose an example case in the sidebar, for example *Cavitation* or *Dry running (incomplete data)*.
2. Press **Load example**.
3. Press **Run new KBS diagnosis**.

Leave a field blank if its value is unknown: blank means *unknown*, never zero. Hover over the help icons to see
what each input is used for.

## 10. Running the automated tests
```powershell
python -m pytest kbs_engine/tests decision_support/tests -p no:cacheprovider
```
Expected result: **164 passed** (verified 2026-11-01). The Streamlit page tests use `streamlit.testing` and run
headless; they are skipped automatically if Streamlit is not installed. The engine tests also run without pytest:
```powershell
python -m unittest discover -s kbs_engine/tests -t .
```

## 11. Validating the knowledge base
```powershell
python knowledge_base\validate_kb.py
```
Expected output: `PASS: 0 errors, 0 warnings (8756 + 590 checks)`.

The validator checks the schema, unique IDs, references, provenance (every item cites a known source, and its
support level matches the source type), vocabularies and rule structure. It also rewrites
`knowledge_base/VALIDATION_REPORT.md`.

## 12. Other useful commands
```powershell
python -m kbs_engine.dataset_consistency     # rewrites kbs_engine/reports/dataset_consistency.md
cd data_preparation; .\run_pipeline.ps1       # rebuilds the synthetic dataset (see data_preparation/README.md)
```
The consistency table compares engine behaviour with the synthetic labels. It is **not** an accuracy measure.

## 13. Current limitations
- **No real-world validation:** there was no plant data and no expert review.
- **Synthetic dataset:** its relationships are simplified and its labels come from the project's own assumptions.
- **Provisional thresholds:** 25 of 26 are Unvalidated, and 5 have no sourced value at all (they are used only
  with a user-entered site limit).
- **Unvalidated knowledge:** 96 of 282 relationships and 6 of 36 rules rest only on project-authored knowledge.
- **Incomplete rule coverage:**
  - single symptoms (air bubbles, coupling vibration, crackling noise) do not conclude a fault;
  - no test separates bearing failure from seal failure;
  - several test results are not interpreted by any rule.
- **Cost, downtime and priority** are qualitative and Unvalidated. No case-specific severity is assessed.
- **Scope:** one equipment class and snapshot cases only. Design-dependent rules need the pump design to be entered.

## 14. Important files
| File | Purpose |
|---|---|
| `knowledge_base/diagnostic_rules.json` | All production rules |
| `knowledge_base/relationships.csv` | Typed relationships with provenance |
| `knowledge_base/sources.csv` | Source register |
| `knowledge_base/kb_meta.json` | Vocabularies, support levels, policies (threshold selection, display cap, priority) |
| `knowledge_base/validate_kb.py` | Knowledge-base validator |
| `kbs_engine/knowledge.py` | Read-only knowledge loader |
| `kbs_engine/engine.py` | Forward-chaining inference engine |
| `kbs_engine/dataset_cases.py` | Converts synthetic dataset records into engine cases |
| `decision_support/report.py` | Report builder and text rendering |
| `decision_support/ui_adapter.py` | Input validation, site limits, help texts, case building |
| `src/pages/1_New_KBS_Diagnosis.py` | Streamlit user interface |
| `knowledge_acquisition/ka3_final_knowledge_model.md` | Final knowledge model and design decisions |
| `knowledge_acquisition/research/ka2_fault_research.md` | Engineering source research |
| `data_preparation/README.md` | Dataset pipeline guide |
| `submission/CT359_Centrifugal_Pump_KBS_Final_Report.pdf` | Final project report |

Module-level details are in `knowledge_base/README.md`, `kbs_engine/README.md` and `decision_support/README.md`.
