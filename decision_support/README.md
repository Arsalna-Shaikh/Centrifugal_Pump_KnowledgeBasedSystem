# DS-1 Decision-Support Layer (`decision_support/`)

Converts a `kbs_engine` result into an operator-friendly diagnostic report: a structured dictionary plus a
plain-text rendering. It reads the engine result and `knowledge_base/` only. The legacy engine and the Streamlit
app are unchanged.

## What the report contains
| Section | Content | Where it comes from |
|---|---|---|
| `headline`, `outcome_text` | One-line summary: diagnosis / Normal / Unknown, prefixed by a safety flag if any | engine outcome |
| `safety_warnings` | Operating safety warnings, checked against every hypothesis | engine safety + `safety_rules.csv` |
| `work_precautions` | Precautions tied to maintenance work (e.g. isolate before opening) | safety rules that trigger only on actions |
| `hypotheses` | Ranked faults in four groups: `diagnoses` (confirmed/likely), `also_possible`, `under_investigation` (pending), `ruled_out_or_argued_against` | engine faults |
| per hypothesis | diagnostic status, knowledge support, hazard class, supporting evidence (with readings and thresholds), contradicting evidence, expected-but-absent symptoms, missing evidence, rule-by-rule explanation with sources and assumptions | engine agenda, rules, relationships |
| `competing_diagnoses` | Faults that remain plausible together | engine conflicts |
| `unexplained_evidence` | Present observations that no fired or pending rule accounts for, with their knowledge-base links (explicitly **not** diagnoses). Pending hypotheses also show their partial evidence. | `manifests_as` / `indicated_by` / `confirmed_by` |
| `root_causes`, `candidate_root_causes`, `fault_chains` | Concluded causes; possible causes with confirming tests; fault → fault chains | engine + `caused_by` / `confirmed_by` |
| `recommended_tests` | Discriminating tests first, then confirming tests | engine test requests |
| `information_needed` | Observations that would let pending rules decide | engine pending rules |
| `maintenance_actions` | Actions with purpose, competence, support and precautions, plus maintenance priority (P1 immediate / P2 high / P3 planned) and qualitative cost and downtime; ordered by priority | engine actions + `maintenance_actions.csv` + `kb_meta.json` priority policy |
| per fault hypothesis: `maintenance_impact` | Qualitative repair cost and downtime class, kept separate from `hazard` | `faults.csv` |
| `evidence`, `evidence_summary`, `data_conflicts`, `limitations` | Full evidence list, present/absent/unknown counts, conflicts, caveats | engine |

## Rules the report follows
- **Nothing is invented.** Actions, tests, warnings and hazard classes are copied from the engine result or the
  knowledge base.
- **No case severity.** The knowledge base has no validated severity model, so `case_severity` is always `None`.
  The report shows only the fault type's hazard class, together with that class's own support level.
- **Status and support are always shown side by side, never merged.** Diagnostic status is how likely the fault
  is; knowledge support is how well-sourced the knowledge behind it is.
- **No hypothesis is dropped.** Unknown, pending, competing and ruled-out hypotheses all stay in the report.
  Unknown evidence is never presented as absent.

## Use
```python
from kbs_engine import Case, InferenceEngine
from decision_support import build_report, render_text

engine = InferenceEngine()
result = engine.run(Case(equipment={...}, measurements={...}, observations={...}))
report = build_report(result, engine.kb)    # dict, e.g. for a future Streamlit page
print(render_text(report))
```

## Streamlit page (SI-1)
`src/pages/1_New_KBS_Diagnosis.py` adds a **New KBS Diagnosis** page to the existing app. Streamlit discovers it
automatically, and `src/app.py` (the legacy page) is unchanged.
```powershell
.\.venv\Scripts\Activate.ps1
streamlit run src\app.py       # legacy page opens first; choose "New KBS Diagnosis" in the sidebar
```
- **Inputs:** equipment parameters, measurements and observations (present / absent / unknown), plus optional test
  results. Blank fields stay **unknown**; invalid values are rejected with a message.
  - Only inputs that a threshold or rule uses are offered. Every field's help text is generated from the
    knowledge base and says what it is used for.
  - Test results: only the six tests that a rule interprets are offered.
  - Site-specific limits: for the five thresholds that have no sourced value (THR-03, THR-14, THR-22, THR-23,
    THR-25), the user can enter a site value. It is passed as an equipment-specific override and labelled as
    user-supplied in the report. Without it, those checks are skipped and the user is warned.
  - Legacy comparison: runs after the new diagnosis, on a copy of the case. A failure is shown in its tab and
    cannot affect the new result.
- **Examples:** the sidebar has example cases (healthy, cavitation, incomplete dry running, competing faults, no data).
- **Output tabs:** diagnoses, root causes, evidence, tests and information needed, maintenance actions, the full
  text report (downloadable), and a legacy-engine comparison.
- **Adapter:** `ui_adapter.py` holds input validation, case building and the legacy-comparison mapping, without
  importing Streamlit.

## Tests
```powershell
python -m unittest discover -s decision_support/tests -t .
# Streamlit UI tests (AppTest) run where Streamlit is installed, e.g. the project .venv:
.\.venv\Scripts\python.exe -m pytest decision_support/tests -p no:cacheprovider
```
The 18 tests cover:
- normal cases;
- major faults (including test-confirmed faults and root causes);
- competing faults;
- contradicting and ruled-out evidence;
- missing evidence;
- safety warnings and work precautions;
- no-invention / no-dropping checks;
- text rendering;
- report construction for about 1,350 synthetic dataset cases. These only check structure; the synthetic labels are
  not used as proof of accuracy.
