# Preparing the Data for Knowledge-Base Integration (Phase 10)

**Status: proposal only.** Nothing in `../data`, `../src` or `../tests` has been changed. This document explains
how the prepared dataset *could* support the KBS later, and — just as important — what it must not be used for.

## Guiding principle
A KBS encodes **knowledge** (justified, general, explainable). A dataset contains **observations** (specific,
noisy, and here synthetic). Data can *suggest, check and calibrate* knowledge; it should not *become* knowledge
automatically. In particular, this dataset was generated from assumptions, so any rule "learnt" from it would
simply re-encode the generator — a circular argument. Correlations are leads for an expert to review, not rules.

## What should become what
| Kind of item | Becomes | Examples from this dataset | Where it would live |
|---|---|---|---|
| Equipment master data | **Structured facts** | pump → type, manufacturer, rated flow/Δp/current/speed, installation date | new `equipment.csv` (from `pump_asset_register.csv`) |
| Controlled vocabularies | **Structured facts** | 12 fault labels, 20 symptom keys, 37 root causes, 13 maintenance actions, severity/priority scales | `faults.csv`, `symptoms.csv`, new `causes.csv`, `maintenance_actions.csv` |
| Fault → component, fault → cause, cause → action | **Structured facts / relations** | Cavitation → caused by *insufficient NPSH*, *clogged strainer* → action *restore suction conditions* | new `fault_cause.csv`, `cause_action.csv` (the cause layer the audit found missing) |
| Sensor → symptom thresholds | **Rules (evidence layer)** | `Head_Pct_Rated < 85 → discharge_pressure_low`, `Suction < 0.8 bar(a) → suction_pressure_low` | a thresholds file read by `derive_symptoms()` instead of hard-coded numbers |
| Diagnostic patterns | **Rules**, written and justified by people | IF suction_pressure_low AND crackling_noise AND pressure_fluctuation THEN Cavitation | `rules.json` (existing) |
| Relative strength of symptom ↔ fault links | **Rule parameters**, data-*checked* | P(seal_leakage \| Seal Leakage) = 0.81 supports a high weight | `symptom_fault_weights.csv` (review, not overwrite) |
| Cost, downtime, priority statistics per fault | **Facts for recommendation/priority**, as ranges | median downtime/cost per fault (EDA figures 8–9) | `faults.csv` cost/downtime columns |
| Individual records, maintenance history, time series | **Historical observations** — not knowledge | the 7,210 condition records, 1,159 work orders | a case base / test set, never inside the rule base |
| Unknown / Inconclusive / label-missing records | **Historical observations** for review | 131 Unknown records (82 genuinely inconclusive + 49 more whose label was missing in the source) | used to find knowledge gaps, never as training labels |

## How each KBS need is supported
1. **Knowledge acquisition.** The cleaned vocabularies give the KBS one agreed name per fault, symptom, cause and
   action. Variant spellings found during cleaning (`cleaning_cell_changes.csv`) show how technicians actually
   write — useful for an input parser.
2. **Symptom–fault relationships.** The symptom–fault matrix (EDA figure 13) and the `obs_*` / `sens_*` columns give
   P(symptom | fault) per class. Use it to *review* `../data/symptom_fault_weights.csv`: a weight of 5 for a
   symptom seen in < 20 % of that fault's records, or a missing link for one seen in > 50 %, deserves expert
   discussion.
3. **Fault–cause relationships.** `Root_Cause` (on Confirmed records) gives fault → cause pairs with counts. This is
   the most direct way to build the missing *cause layer*: one row per (fault, cause) with its source and,
   optionally, a relative frequency.
4. **Evidence identification.** `sens_*` shows which symptoms can be derived automatically from sensors (13) and
   `obs_*` which need a human (crackling noise, seal leakage, air bubbles, loss of prime …). The agreement table in
   `preprocessing_report.md` shows how reliable operator reports are relative to sensors.
   **Relative thresholds** (`Flow_Pct_Rated`, `Head_Pct_Rated`, `Current_Pct_Rated`) fix a weakness found in the
   audit: the current KBS uses absolute pressures (e.g. 4.2 bar), which cannot work across a mixed fleet.
5. **Diagnostic rule validation.** Run the existing engine on the `test` partition, using only `sens_*` and
   `obs_*` evidence that is known (not `<NA>`), and report top-1/top-3 agreement **per fault class** against
   `Fault_Type` for Confirmed records. Because the partition is grouped by pump, the test pumps are unseen.
   Report it honestly as *agreement with synthetic labels*, not real-world accuracy.
6. **Maintenance recommendations.** `Maintenance_Action` per fault and cause links the diagnosis to actions;
   downtime/cost distributions and `Priority_Level` support a priority score (safety × confidence × downtime ×
   cost) instead of today's safety-only tie-break.

## What must NOT be done
- Do not convert correlations directly into rules (e.g. Downtime ↔ Cost ρ = 0.80 is not a diagnostic rule).
- Do not use imputed sensor values (`Imputed_Columns`) as evidence — `sens_*` is already `<NA>` for them.
- Do not use `Unknown`, `Label_Missing_In_Source` or `Suspected` records as ground truth for rule scoring.
- Do not tune thresholds or weights on the `test` partition; use `train` / `validation`.
- Do not present results on this dataset as evidence of real diagnostic accuracy.

## Suggested next steps (for approval)
1. Create a cause layer (`causes.csv`, `fault_cause.csv`) from the Confirmed `Root_Cause` pairs plus literature.
2. Move sensor thresholds into a knowledge file and switch to relative (per-rating) thresholds.
3. Write an evaluation script that runs the existing engine on the test partition (read-only use of the KBS).
4. Review `symptom_fault_weights.csv` against the symptom–fault matrix with a domain source for each change.
