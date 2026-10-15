# CT-359 Centrifugal Pump KBS — Viva Guide

## 30-second project explanation
Our project is an explainable knowledge-based expert system for centrifugal pump fault diagnosis. The knowledge base stores components, symptoms, faults, symptom weights, compound rules, safety levels, cost/downtime, and maintenance actions. The inference engine converts sensor values into symbolic facts, applies weighted forward reasoning, fires matching IF–THEN rules, ranks possible faults, and explains which evidence produced the result.

## Most important distinction
**Knowledge base = what the system knows. Inference engine = how the system reasons with that knowledge.**

## Why centrifugal pump?
It combines hydraulic, mechanical, sealing, and electrical faults, and different faults share symptoms. That makes it a good complex-problem example for knowledge representation and explainable reasoning.

## Why rules instead of machine learning?
Rules are transparent, easy to validate with domain experts, and do not require a large labeled dataset. Machine learning can be future work after collecting validated field history.

## Why forward chaining?
We start from known facts such as vibration, temperature, pressure, flow, noise, and leakage, and infer possible faults. That is a data-driven direction, so forward reasoning is natural.

## How do you handle incomplete information?
A full rule match is not mandatory. Each observed symptom contributes a weight to candidate faults. Compound rule bonuses are added only when all their conditions are available. Therefore partial evidence still produces a ranked result.

## Is the confidence a probability?
No. It is an explainable normalized evidence score, not a statistically calibrated probability. This is an important limitation.

## Are the logs real?
No. They are synthetic educational logs generated for prototype testing. We state this clearly. Real deployment would require OEM/plant data and expert validation.

## How is conflicting evidence handled?
Several faults can receive evidence at the same time. The system ranks them instead of forcing one answer and displays the top alternatives with their matching evidence.

## What makes the system explainable?
For every result it shows matched symptoms, fired rule IDs, rule explanations, safety priority, and recommended maintenance actions.

## Main dataset numbers
- 10 components
- 14 fault classes
- 22 symbolic symptoms
- 16 maintenance actions
- 14 compound rules
- 280 synthetic diagnostic cases
- 255 time-stamped sensor-log records

## Internal test result
Top-1 agreement: 85.7%. Top-3 inclusion: 98.2%. This checks internal consistency only because the cases are synthetic and based on the same knowledge model.

## Best demo cases
1. Bearing failure: vibration 8.5, bearing temp 90, grinding noise ON.
2. Cavitation: vibration 7, flow 70, discharge pressure 4, suction pressure 0.5, fluctuation 15, crackling noise ON.
3. Dry running: flow 3, discharge pressure 0.5, suction pressure 0.2, seal temp 100, pump primed OFF, rapid temperature rise ON.

## Questions you may be asked
**What is a production rule?** An IF conditions THEN conclusion representation of expert knowledge.

**What is knowledge acquisition?** Collecting and structuring knowledge from manuals, experts, maintenance history, and operational data.

**Why not ontology?** It is strong for semantic relationships, but production rules are simpler for this prototype and directly support explainable diagnosis. An ontology can be added later.

**What is a limitation of rule-based systems?** Rule bases can become difficult to maintain as the domain expands, and poorly designed rules can conflict.

**What would you add in industry?** Real SCADA/historian inputs, OEM alarm limits, work-order history, expert validation, temporal reasoning, and possibly probabilistic or machine-learning support.
