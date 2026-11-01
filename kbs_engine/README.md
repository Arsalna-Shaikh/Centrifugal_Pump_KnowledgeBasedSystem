# KR-2 Inference Engine (`kbs_engine/`)

A layered forward-chaining inference engine for the structured knowledge base in `knowledge_base/`. It uses only
the Python standard library. It is **separate from** the legacy engine (`src/inference_engine.py`) and the
Streamlit app, which are unchanged.

## Pipeline
| Layer | What happens | Knowledge used |
|---|---|---|
| L1 evidence | Measurements → symptom states (`present` / `absent` / `unknown`) using equipment-specific thresholds; merged with manual observations; `implies` / `excludes` applied; conflicts recorded | indicators, thresholds, equipment parameters, symptom relations |
| L2 faults | Fault rules fire → fault hypotheses | 19 `L2_fault` rules |
| L2 negative | Negative evidence lowers a hypothesis; known absence blocks one | 3 `L2_negative` rules |
| L3 causes / chains | Cause and fault-chain rules using the L2 conclusions | 9 `L3_cause` + 2 `L3_chain` rules |
| L4 tests | Requests for discriminating tests when hypotheses compete | 3 `L4_test_request` rules |
| L5 actions & safety | Actions from `recommends` / `corrects`; precautions; **safety rules checked against every hypothesis** | relationships, safety rules |

**How the layers run.** The layers are stratified, and each one runs to a fixed point over a working memory. Later
layers consume the conclusions of earlier ones; for example, R-C-01 needs FLT-01 from R-CAV-1. The `agenda` in the
result records every firing with its cycle number.

**Evidence handling:**
- **Equipment-specific thresholds.** For each symptom the engine uses the default threshold for the most specific
  basis available: healthy baseline, then % of rated, then absolute. Equipment-specific values can be supplied as
  `threshold_overrides`. A legacy absolute value (e.g. 4.2 bar) is used only with
  `allow_non_default_thresholds=True`. A threshold with no sourced value is never used.
- **Unknown ≠ absent.** A rule that needs a symptom to be *absent* only fires when absence is known. A missing or
  imputed measurement makes its symptom `unknown`.
- **Inconsistent readings are not used.** If discharge pressure is below suction pressure, both readings (and the
  pump head derived from them) are treated as unknown, and an `inconsistent_measurements` conflict is recorded.
  This means no Normal verdict can rest on them.
- **Pending hypotheses.** A rule with some evidence present but other conditions unknown makes its fault
  `pending`, and the engine asks for the missing observations.
- **Conflicts:**
  - Sensor and observation disagree → symptom becomes `unknown` and the conflict is recorded.
  - Mutually exclusive symptoms present together → both become `unknown`.
  - Several plausible faults → recorded as competing hypotheses, and the L4 test requests are raised.

**Support vs likelihood.** Each hypothesis reports three things separately:
- `status`: the diagnostic likelihood after negative evidence and the display cap;
- `likelihood`: the best stored rule likelihood;
- `support`: the quality of the knowledge.

Unvalidated rules are shown at most as `possible`, per `kb_meta.json`. Their stored likelihood is not changed.

**Outcome.**
- `diagnosis`: at least one fault is `likely` or `confirmed`.
- `OUT-N` (Normal): every assessable sensor symptom is known absent and nothing is present.
- `OUT-U` (Unknown): anything else. It recommends ACT-17 and requests confirming tests.

## Use
```python
from kbs_engine import Case, InferenceEngine, explain

engine = InferenceEngine()
case = Case(
    equipment={"pump_design": "radial", "rated_flow": 100, "rated_differential_pressure": 5.0,
               "rated_motor_current": 50},
    measurements={"flow_rate": 3, "differential_pressure": 0.4, "suction_pressure": 1.5},
    observations={"prime_failure": "present"},       # present / absent / unknown
    test_results={},                                 # e.g. {"TST-02": "out_of_tolerance"}
)
result = engine.run(case)
print(explain(result, engine.kb))
```

## Tests
Run from the repository root:
```powershell
python -m unittest discover -s kbs_engine/tests -t .
# or, with the project's virtual environment that already has pytest:
.\.venv\Scripts\python.exe -m pytest kbs_engine/tests -p no:cacheprovider
```
The 51 tests cover:
- evidence derivation;
- normal operation;
- 10 fault scenarios;
- root causes and chains;
- missing evidence;
- conflicting evidence;
- safety overrides;
- support vs likelihood;
- forward chaining;
- explanations;
- invariants over 1,347 synthetic dataset records.

## Dataset use
`dataset_cases.py` builds cases from the **synthetic** cleaned dataset:
- sensor columns become measurements, with imputed values marked;
- operator-recorded observations become `present`;
- observations that were not recorded stay `unknown`;
- all pumps are assumed radial.

The tests only check invariants on these cases. Examples: a fired rule's conditions really hold; safety fires for
any dry-running hypothesis; no evidence is derived from imputed values. **They never use the synthetic labels as
proof of accuracy.**

`python -m kbs_engine.dataset_consistency` writes `reports/dataset_consistency.md`. It is an informational table of
engine behaviour on those records, explicitly not an accuracy measure.
