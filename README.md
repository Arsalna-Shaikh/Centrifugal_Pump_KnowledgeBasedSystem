# Centrifugal Pump Fault Diagnosis Knowledge-Based System

**Course:** CT-359 Knowledge Based System

This is a complete academic prototype that represents centrifugal-pump maintenance knowledge as weighted production rules and uses forward-chaining style evidence evaluation to rank likely faults.

## Features
- 14 fault classes and 22 symbolic symptoms
- 16 maintenance actions with cost/downtime categories
- 14 compound production rules
- Numeric sensor-to-symbolic evidence conversion
- Ranked multi-fault diagnosis with confidence/evidence score
- Explanation trace (matched evidence + fired rules)
- Safety, repair-cost, and downtime metadata
- Synthetic diagnostic-case dataset and operational sensor log
- Streamlit demonstration UI

## Important academic note
The datasets in `data/diagnostic_cases.csv` and `data/operational_sensor_log.csv` are **synthetic, reproducible educational data**, not measurements from a real plant. They are generated from the project knowledge model for demonstration and testing. Prototype thresholds are not OEM safety limits.

## Run
```bash
pip install -r requirements.txt
streamlit run src/app.py
```

## Test
```bash
pytest -q
```

## Knowledge files
- `components.csv` — pump components
- `faults.csv` — fault classes, safety, cost, downtime
- `symptoms.csv` — symbolic observations
- `symptom_fault_weights.csv` — fault/evidence relationships
- `rules.json` — compound IF-THEN diagnostic rules
- `maintenance_actions.csv` — recommended actions
- `diagnostic_cases.csv` — 280 synthetic labeled cases
- `operational_sensor_log.csv` — 255 five-minute synthetic operating records

## Viva one-line explanation
**The knowledge base stores what the system knows; the inference engine decides how to use that knowledge to infer faults from observed evidence.**
