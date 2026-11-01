# Knowledge Gaps and Conflicts

Part of the KA-1 audit. IDs (`C-nn` conflict, `G-nn` gap) are referenced from the other reports. "Resolution" says
what kind of evidence would settle the item. It does not prescribe the answer.

## Conflicts

### C-01 Three different sensor→symptom threshold sets
| Symptom | A: KB engine ([inference_engine.py](../../src/inference_engine.py)) | B: generator operator threshold ([generate_dataset.py:205-218](../../data_preparation/scripts/generate_dataset.py#L205-L218)) | C: preprocessing ([preprocess_dataset.py:27-53](../../data_preparation/scripts/preprocess_dataset.py#L27-L53)) |
|---|---|---|---|
| vibration_high | ≥ 6.0 mm/s (l28) | > 4.5 | > 4.5 ("ISO 10816-3-style", unverified) |
| bearing_temp_high | ≥ 80 °C (l29) | > 80 | ≥ 80 |
| seal_temp_high | ≥ 85 °C (l37) | > 80 | ≥ 80 |
| motor_temp_high | ≥ 80 °C (l30) | > 95 | ≥ 95 |
| flow_low | < 75 % of *baseline* (l31) | < 75 % of *rated* | 10–75 % of rated |
| no_flow | < 10 % of baseline (l32) | < 10 % rated | < 10 % rated |
| discharge_pressure_low | < 4.2 bar absolute (l33) | < 85 % of rated discharge pressure | head < 85 % of rated head |
| discharge_pressure_high | > 6.0 bar absolute (l34) | > 112 % rated discharge pressure | head > 115 % rated head |
| suction_pressure_low | < 0.70 bar(a) (l35) | < 0.8 bar(a) | < 0.8 bar(a) |
| motor_current_high | > 38 A absolute (l36) | > 110 % rated | > 110 % rated |
| pressure_fluctuation | ≥ 10 % (l38) | > 8 % | ≥ 10 % |
| noise_high | — | > 88 dB(A) | > 85 dB(A) |

None of the three sets has a documented engineering source; SOURCE_NOTES.md:17 states the KB thresholds are
prototype defaults. **Resolution:** E — standard, OEM data or site alarm limits per pump type, expressed relative to
the rating where size-dependent.

### C-02 Absolute vs rating-relative indicators
The KB uses absolute bar and amp limits, which only fit one pump size. Across the 40 synthetic pumps, rated
current spans 30–241 A and rated Δp 2.5–28 bar. **Resolution:** design decision (relative indicators, C) + E for the
percentages.

### C-03 Reference for "low flow": healthy baseline vs nameplate rating
App input is "% of healthy baseline" ([app.py:25](../../src/app.py#L25)); the dataset uses % of rated flow. These differ
whenever the normal duty point is not the rated point. **Resolution:** decide which reference the KB uses and
record it as an attribute of the indicator.

### C-04 Direction of motor current at low flow (physics question)
The KB links `motor_current_high` to faults that *reduce* flow: F04 (weights:24), F11 (weights:57), and indirectly
F10. The generator models power/current *falling* as flow falls (`I = I_rated·(0.45 + 0.5·q)`,
[generate_dataset.py:177](../../data_preparation/scripts/generate_dataset.py#L177)). Hence P = 0.00 in B. Which
direction is right depends on the pump's power curve (pump type / specific speed). Neither source documents it.
**Resolution:** E (pump characteristic curves / textbook). Until then these links should carry
"direction unvalidated".

### C-05 Rule R03 attribution
R03 (coupling_vibration ∧ vibration_high ∧ bearing_temp_high → F03, [rules.json:25](../../data/rules.json#L25)) never
fires on misalignment records in B. It fires on 34 bearing-failure records caused by misalignment. In B,
misalignment heats bearings by only 4–20 °C (below 80 °C). The KB may be describing the *combined* condition
(misalignment that has already damaged bearings). **Resolution:** decide whether R03 concludes F03, F01, or the chain
"F03 causing F01"; E for whether misalignment alone raises bearing temperature above alarm level.

### C-06 Rule R06 (suction blockage) overlaps cavitation
All three R06 conditions ([rules.json:57](../../data/rules.json#L57)) are also F02 links (weights:9,10,11). In B the
R06 pattern occurs on 23 cavitation records and 0 blockage records. In B a clogged strainer is a *cause* of
cavitation. **Resolution:** model the clogged strainer as a cause (see C-07) and find a discriminating test (e.g.
strainer Δp, listed in B findings) — E.

### C-07 Fault vs cause level
| Item | In A | In B |
|---|---|---|
| Clogged suction strainer | fault F06 | cause of Cavitation and of Pump Blockage |
| Supply phase imbalance | fault F14 | cause of Motor Fault |
| Closed discharge valve | part of fault name F11 | cause of Discharge Restriction |
| Loss of prime | part of fault name F07 (and symptom S14) | cause "Failed priming" of Dry Running + symptom |
| Soft foot / foundation | fault F13 | cause of Shaft Misalignment |
**Resolution:** modelling decision (allow fault→fault causation; separate fault mode from cause), then E per item.

### C-08 Fault granularity
B merges F04 + F06 into Pump Blockage and F08 + F14 into Motor Fault. A keeps them separate but cannot
discriminate them (shared evidence; R04 ⊂ R10, R08 ⊂ R14). **Resolution:** decide the granularity. Keep separate
faults only where a discriminating symptom or test exists (E).

### C-09 Fault–symptom conflicts in the register (KB weight present, P < 0.05 in B)
| # | Link (KB weight, line) | Why B shows ~0 | Type |
|---|---|---|---|
| 1 | F01 → motor_current_high (2, l5) | B adds ≤ 4 % current, never > 110 % | threshold/modelling artefact |
| 2 | F03 → bearing_temp_high (3, l17) | B heats bearings 4–20 °C, below 80 °C | modelling choice → see C-05 |
| 3 | F03 → motor_current_high (2, l18) | B adds 3–8 %, below 110 % | threshold artefact |
| 4 | F03 → grinding_noise (2, l19) | B records coupling vibration, not grinding, for misalignment | modelling choice |
| 5 | F04 → discharge_pressure_low (4, l21) | B blockage head loss mostly above the 85 % line | threshold artefact |
| 6 | F04 → motor_current_high (2, l24) | B current falls with flow | **physics question (C-04)** |
| 7 | F05 → vibration_high (2, l27) | B seal leak adds ≤ 0.5 mm/s | modelling choice |
| 8 | F05 → bearing_temp_high (1, l28) | B seal leak does not heat bearings | modelling choice |
| 9–11 | F06 → suction_pressure_low (5), discharge_pressure_low (4), crackling_noise (2) (l29, l31, l32) | B has no separate suction-blockage fault; its "Pump Blockage" is mostly impeller fouling | **granularity (C-08)** |
| 12 | F07 → grinding_noise (2, l39) | B records "High noise level" for dry running instead | vocabulary/modelling |
| 13 | F08 → flow_low (1, l44) | B motor fault does not change flow | modelling choice |
| 14 | F11 → motor_current_high (2, l57) | B current falls at low flow | **physics question (C-04)** |
| 15 | F12 → discharge_pressure_low (3, l63) | B head loss for air ingress stays above 85 % | threshold artefact |

None of these shows that the KB is wrong. They show where the two project-authored sources disagree. Items 6 and
14 are genuine engineering questions; the rest depend on thresholds or on generator choices. **Resolution:** E per
link.

### C-10 Candidate links present only in B (P ≥ 0.2 on Confirmed records, no KB weight)
| Link | P in B | Other support | Note |
|---|---|---|---|
| F01 Bearing → coupling_vibration | 0.22 | — | only via the misalignment chain (0.69 vs 0.00 by cause); a cause-level link, not a fault-level one |
| F01 Bearing → noise_high | 0.29 | — | `noise_high` absent from KB vocabulary |
| F02 Cavitation → noise_high | 0.51 | — | KB uses crackling_noise for the same phenomenon |
| F04/F06 Blockage → vibration_high | 0.23 | — | |
| F07 Dry running → discharge_pressure_low | 0.89 | — | follows from no flow/no head in B's model |
| F07 Dry running → suction_pressure_low | 0.78 | — | B models suction collapse |
| F07 Dry running → vibration_high | 0.78 | **D: SOURCE_NOTES:8** ("vibration") | strongest candidate |
| F11 Discharge restriction → vibration_high | 0.46 | **D: SOURCE_NOTES:11** (low flow → vibration) | strong candidate |
| F11 Discharge restriction → pressure_fluctuation | 0.30 | — | weak |
| F12 Air ingress → vibration_high | 0.37 | — | weak |
**Resolution:** E. The two D-supported links are the best-supported additions, but the KSB pages themselves must
be checked (not done here).

### C-11 Cost/downtime disagreements (both authored)
| Fault | KB (faults.csv) cost / downtime | B median cost / downtime |
|---|---|---|
| Motor faults F08/F14 | Medium / Medium | 2nd-highest ($4.9k, 22 h) |
| Dry running F07 | Medium / High | 2nd-highest cost ($4.6k) |
| Air ingress F12 | Low / **Medium** | low (4.8 h) |
| Misalignment F03 | **Medium** / Medium | low-mid ($1.0k, 5.1 h) |
KB also stores cost/downtime at two levels (fault and action) without saying which is authoritative (e.g. F07 cost
Medium vs A09 cost LOW). **Resolution:** site/maintenance records (E). Until then, treat these as qualitative
placeholders.

### C-12 Safety: hazard class vs case severity vs priority
- A gives a static hazard class per fault (only F07 CRITICAL). B gives per-case severity and a priority policy.
  They are compatible but different concepts (see `entity_relationship_mapping.md` §7.2).
- The app evaluates CRITICAL only for the top-ranked fault ([app.py:70](../../src/app.py#L70)). That is an engine issue,
  but it means the KB's safety knowledge is under-used.
- **Resolution:** keep the three attributes separate; obtain hazard classification from E (site safety).

### C-13 Rule redundancy and double counting
R04 ⊂ R10 and R08 ⊂ R14: the subset rule always fires with the superset. Every rule condition is also a weighted
link of the same fault, so evidence is counted twice. **Resolution:** design decision in the knowledge model.

## Gaps

| ID | Gap | Evidence | Needed source |
|---|---|---|---|
| G-01 | **No equipment context**: no equipment entity, pump type, rating, duty point, fluid, speed | inventory §2 | design + asset data (B shows the structure only) |
| G-02 | **No root-cause layer** in the KB | inventory §9; 37 causes exist only in B | E for each fault–cause link (register §5.1) |
| G-03 | **Cause → evidence knowledge absent** | only 1 cause signature in any source (§5.4) | E: diagnostic tests per cause (B lists 30 test/finding names as starting points) |
| G-04 | **Cause → corrective action** missing for most causes | §5.5 | E / maintenance procedures |
| G-05 | KB faults with no data: F09 coupling, F13 base looseness | mapping §3 | E (and data if testing is wanted) |
| G-06 | Candidate fault topics in neither source (to research, **not asserted**): wear-ring / internal clearance wear, rotor unbalance, bent shaft, resonance, wrong rotation, prolonged off-BEP operation as a fault | not in A or B | E |
| G-07 | Evidence types not modelled: vibration spectrum features, oil analysis, NPSH margin, strainer Δp, insulation resistance, phase current balance | appear only as B finding text and A action details | E |
| G-08 | No provenance per weight, bonus, rule or threshold; weight semantics undocumented | inventory §6–7, SOURCE_NOTES:17 | design (source fields) + E |
| G-09 | No negative evidence / exclusion knowledge (symptoms that argue *against* a fault) | inventory §6 | E |
| G-10 | No "unknown" observation state | app defaults ([app.py:21-31](../../src/app.py#L21-L31)) | design decision |
| G-11 | Safety knowledge limited to 6 documented statements; no shutdown/trip criteria | §7.4 | E / site procedures |
| G-12 | External references thin: 4 pages from one vendor, summarised, not re-verified in this audit | SOURCE_NOTES:5-14 | E (standards, textbooks, OEM manuals) |
| G-13 | Actions: 12/14 faults have one step; no verification/after-repair step; B actions skip inspection steps | inventory §8, §7.1 | E |
| G-14 | No temporal evidence (trend, "rapid" rise, persistence) although `rapid_temp_rise` implies a time window | symptoms.csv:23 | design + E |
| G-15 | Near-duplicate symptoms need resolution: flow_fluctuation≈pressure_fluctuation, efficiency_low≈discharge_pressure_low, no_flow⊂flow_low, rapid_temp_rise embeds low flow, speed_unstable≠speed_deviation | mapping §2 | design decision |
| G-16 | Components: no sub-components or external system elements, although most causes are located there | mapping §1.2, §5.3 | design + E |
| G-17 | Fault description vs component: one component per fault cannot express origin vs damage location (F02, F07) | inventory §3 | design |
