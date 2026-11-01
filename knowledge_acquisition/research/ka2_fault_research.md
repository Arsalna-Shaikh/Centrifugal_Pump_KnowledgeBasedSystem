# KA-2 — Independent Engineering Research: Centrifugal Pump Faults

**Purpose.** Validate (or fail to validate) the project's existing fault knowledge against sources outside the
project. KA-1 found that the KB and the synthetic dataset are both project-authored, so neither can validate the
other. This document records only what external sources were **actually read**, where, and how strongly they
support each relationship.

**Scope:** pump fundamentals · cavitation · dry running · air ingress · suction blockage · bearing failure ·
misalignment · mechanical seal failure · impeller damage · discharge restriction.
**Date of research:** 2026-10-31. **No project file was modified.**

---

## 1. Evidence levels used in this document
| Tag | Meaning |
|---|---|
| **IND** | Independently supported: a standards body, a government/industry-association publication not tied to one manufacturer (DOE + Hydraulic Institute), or the Hydraulic Institute itself. |
| **MFR** | Manufacturer-specific guidance: a single OEM's lexicon, FAQ, manual or training material (KSB, Grundfos, ITT Goulds, SKF). Credible, but may reflect that vendor's products and practice. |
| **IND+MFR** | Stated by an IND source **and** at least one MFR source (corroborated). |
| **UNV** | Unvalidated: claimed in the project KB/dataset but **no source read in this research supports it**, or the only source could not be accessed. |
| *(lead)* | A source identified but **not read** (paywalled, blocked, scanned or too large). It supports nothing until read. |

Rules applied:
- Nothing is marked IND or MFR on the strength of a search-engine summary alone. Where only a snippet was seen,
  this is said explicitly.
- No numeric threshold is accepted unless the source text gave it. **None of the sources read gave a
  general-purpose numeric alarm threshold.**

## 2. Source register
| ID | Source | Type | URL | What was read | Access notes / limitations |
|---|---|---|---|---|---|
| S-01 | US DOE & Hydraulic Institute, *Improving Pumping System Performance: A Sourcebook for Industry*, 2nd ed., 2006 (DOE/GO-102006-2079) | IND | https://www.energy.gov/sites/prod/files/2014/05/f16/pump.pdf | printed pp. 7, 9–10, 16–17, 19–23, 25, 31–36 | Text extracted locally from the PDF with a simple stdlib extractor; a few words are dropped at layout breaks. Quotes below are short and should be checked against the PDF before external publication. Written for system efficiency/reliability, not as a diagnostic manual. |
| S-02 | Hydraulic Institute (P. Gaydon), "The Basics of NPSH & Pump Operating Regions", pumps.org, 2022-12-07 (orig. *Pumps & Systems* 2017) | IND | https://www.pumps.org/2022/12/07/the-basics-of-npsh-pump-operating-regions/ | full article | Summarises ANSI/HI 9.6.1 and 9.6.3 concepts; gives **no numeric POR/AOR or margin values**. |
| S-03 | Hydraulic Institute, "The Effects of Gas & Liquid Mixtures on Rotodynamic Pumps & Water Hammer Basics", *Pumps & Systems*, 2015-01-19 | IND | https://www.pumpsandsystems.com/effects-gas-liquid-mixtures-rotodynamic-pumps-water-hammer-basics | full article | Gives **no gas-volume % limit**; refers to ANSI/HI 2.3. |
| S-04 | KSB Centrifugal Pump Lexicon — "Cavitation" | MFR | https://www.ksb.com/en-global/centrifugal-pump-lexicon/article/cavitation-1117364 | full entry | Mechanism and criteria; does not discuss NPSH or temperature as *causes*. |
| S-05 | KSB Lexicon — "NPSH" | MFR | https://ksb.com/en-global/centrifugal-pump-lexicon/article/npsh-1116954 | full entry | Formulas are images (not read); no numeric margin. |
| S-06 | KSB Lexicon — "Dry running" (already cited in `docs/SOURCE_NOTES.md`) | MFR | https://www.ksb.com/en-global/centrifugal-pump-lexicon/article/dry-running-1116984 | full entry | **Re-verified.** Does *not* itself name seal damage as an effect (see S-08). |
| S-07 | KSB Lexicon — "Operating behaviour" (already cited) | MFR | https://www.ksb.com/en-global/centrifugal-pump-lexicon/article/operating-behaviour-1118222 | full entry | **Re-verified.** No numeric operating limits. |
| S-08 | KSB Lexicon — "Shaft seal" | MFR | https://www.ksb.com/en-global/centrifugal-pump-lexicon/article/shaft-seal-1116516 | full entry | Mechanical-seal function and dry-running failure. |
| S-09 | KSB Lexicon — "Flow rate" | MFR | https://www.ksb.com/en-global/centrifugal-pump-lexicon/article/flow-rate-1116844 | full entry | Definition of Qmin/Qmax only. |
| S-10 | Grundfos FAQ — "What is cavitation?" | MFR | https://www.grundfos.com/us/support/faq/what-is-cavitation | full entry | Short; no symptoms listed. |
| S-11 | ITT Goulds Pumps, *Model 3408A IOM* (6/08), troubleshooting, printed pp. 23–24 | MFR | https://www.manualsdir.com/manuals/461667/goulds-pumps-3408a-iom.html?page=31 (and `?page=32`) | troubleshooting table items 1–41 | Third-party host of an OEM manual; **model-specific** (split-case pump). The table has no "noisy / bearings hot / seal leakage" sections. |
| S-12 | SKF, *Bearing damage analysis (ISO 15243)* e-learning transcript, R32 (2019) | MFR | https://www.skf.com/skf/campaign/aptitudearchive/training/brgdam_v2/presentation_content/external_files/Brg%20damage%20transcript%20R32.pdf | pp. 2–6 | Text extracted locally. Describes ISO 15243:2004 classification (the standard itself was not read). Cause statistics are "SKF experience". |
| S-13 | E. Vogel, "Pump Alignment: Just the Facts", *Pumps & Systems*, 2011-12-17 | MFR/trade (practitioner article) | https://www.pumpsandsystems.com/pump-alignment-just-facts-0 | full article | Single author; numbers given without a cited source. |
| S-14 | ISO 10816-7:2009 *Mechanical vibration — Evaluation of machine vibration by measurements on non-rotating parts — Part 7: Rotodynamic pumps for industrial applications* | IND (standard) *(lead for content)* | iso.org/standard/41726.html (HTTP 403 to this tool); catalogue listings e.g. https://standards.globalspec.com/std/1157527/iso-10816-7 | **scope only, from catalogue/search listings** | Zone limit values (Annex A) **not obtained**. ISO lists ISO/AWI 20816-7 as its planned replacement (https://www.iso.org/standard/92744.html, seen via search). |
| S-15 | ANSI/HI 9.6.1-2017 *Rotodynamic Pumps Guideline for NPSH Margin* | IND (standard) *(lead for values)* | https://law.resource.org/pub/us/cfr/ibr/inc/ansi/ansi.hi.9.6.1.2017.pdf | downloaded, **scanned images – no text layer** | Only definitions seen in S-02 and in an ANSI blog **search snippet** ("NPSH margin … is equal to the NPSHA minus the NPSH3"). Margin tables not read. |
| S-16 | ISO 15243:2017 *Rolling bearings — Damage and failures* | IND (standard) *(lead)* | https://www.iso.org/standard/59619.html (HTTP 403) | not read | Known only through S-12. |
| L-1 | Osman (2019), "Vibration Signature of Misaligned Rotors of Centrifugal Pump", EIJEST | peer-reviewed *(lead)* | https://eijest.journals.ekb.eg/article_97279.html | **not read** (DNS failure) | Search snippet claims 1X/2X/3X peaks; **not used as evidence**. |
| L-2 | Flowserve, *Self-Diagnose the Root Causes to Your Mechanical Seal Failure* | MFR *(lead)* | https://kh.aquaenergyexpo.com/wp-content/uploads/2023/09/Self-Diagnose-the-Root-Causes-to-Your-Mechanical-Seal-Failure.pdf | **not read** (> 10 MB) | Third-party host. |
| L-3 | Textbooks: Karassik et al., *Pump Handbook*; Gülich, *Centrifugal Pumps* | textbook *(lead)* | — | **not read** | No legitimate open copy accessed. Recommended for KA-3. |

## 3. Centrifugal pump fundamentals
| # | Statement | Evidence | Level |
|---|---|---|---|
| P1 | Operating a pump **at or near its BEP** minimises energy cost and "also decreases loads on the pump and maintenance requirements". | S-01 pp. 9–10 | IND |
| P2 | Away from the design point, flow separation and **suction/discharge recirculation** develop; these transients cause pulsations (noise) and can cause vibration and cavitation; continuous operation is only permitted near the design point; ranges narrow for high specific-speed pumps. | S-07 | MFR |
| P3 | Outside the preferred operating region (POR) there are "areas of flow recirculation and separation that can cause additional loading, flow induced vibration"; the allowable operating region (AOR) is where "service life … is acceptable" and must be obtained from the manufacturer; POR is determined per ANSI/HI 9.6.3. | S-02 | IND |
| P4 | **Motor current vs flow depends on pump type.** For a *radial* centrifugal pump the brake-horsepower curve "is typically a constantly increasing line", so motor current rises with flow and is lowest when downstream valves are closed (deadhead). For an *axial* pump the relationship is reversed. | S-01 p. 17 | IND |
| P5 | Minimum flow rate (Qmin) is the "minimum permissible flow rate at which the pump can be continuously operated without suffering any damage" — a pump-specific value from the supply contract/data sheet. | S-09 | MFR |
| P6 | Pump problems and system problems interact: improper selection/operation induces vibration that loosens joints and fatigues piping supports. | S-01 pp. 19–20 | IND |
| P7 | Head, not pressure, is the pump-independent measure (pressure depends on density); readings near pipe-size changes differ. | S-01 p. 7 | IND |

**Implication for the KB:** P3–P5 confirm KA-1 conflict C-02/C-03. Operating limits are **pump-specific**, from
manufacturer data, so the KB must hold limits per equipment and cannot use one absolute value. P4 **resolves
C-04** for radial pumps (see §12 and §14).

---

## 4. Cavitation (KB F02)
**Mechanism.**
- Vapour cavities form where local static pressure falls below the vapour pressure, then "sudden collapse … in the
  form of an implosion", producing a microjet (S-04, MFR). The same mechanism is described by S-01 p. 20 (IND) and
  S-10 (MFR) → **IND+MFR**.
- Cavitation onset depends on NPSH. NPSHA is the system's head above vapour pressure at the suction; NPSH3 is
  the NPSH at which head falls by 3 % (S-02 IND; S-05 MFR). The Hydraulic Institute adopted 3 % in 1932 because it was
  the smallest consistently measurable drop (S-02).
- Cavitation already exists at NPSH3: NPSHi (incipient) is higher than NPSH3 (S-04, S-05). Hence an
  **NPSH margin** above NPSH3 is needed (S-02). Its values are in ANSI/HI 9.6.1 (S-15, not read).

| Root cause | Source | Level |
|---|---|---|
| Lower-than-design suction pressure | S-01 p. 20 | IND |
| Higher-than-design liquid temperature (raises vapour pressure) | S-01 p. 20; S-04 notes vapour pressure–temperature link | IND |
| Wrong pump selection | S-01 p. 20 | IND |
| Operation far to the right on the curve (high flow) | S-01 p. 20 | IND |
| Cavitation damage at **low** flow under certain conditions / internal recirculation causes cavitation-like damage | S-01 pp. 20–21; S-07 | IND+MFR |
| Suction starved by **air pockets or fouling of pipes** | S-01 p. 20 | IND |
| Insufficient NPSHA vs NPSHR | S-10; S-11 item 13 | MFR (IND via S-02 concept) |
| Excessive suction lift / suction friction losses | S-11 items 3, 26 | MFR |

| Symptom / consequence | Source | Level |
|---|---|---|
| "Crackling and popping noises that often sound like marbles passing through the pump" | S-01 p. 20 | IND |
| Rise in noise level, rough running | S-04 | MFR → with S-01: **IND+MFR** (noise) |
| Reduced head / performance; drop in efficiency | S-01 p. 20; S-02; S-04 | IND+MFR |
| Impeller erosion; with oxygen, increased corrosion | S-01 pp. 20, 35; S-02; S-04 | IND+MFR |
| Unbalance from material loss → alternating bearing loads → accelerated bearing wear; accelerated seal wear | S-01 pp. 20–21 | IND |
| Vibration stressing foundations and piping | S-01 p. 21 | IND |
| Pump takes too much power (listed cause) | S-11 item 30 | MFR |

**Diagnostic tests (supported):** NPSHA vs NPSHR/NPSH3 comparison (S-02, S-05, S-10); recognising the acoustic
signature (S-01 p. 20). NPSH testing at 3 % head drop is the standard test method (S-02).

**Remedies (supported):** raise suction head or lower the pump, cool the liquid, pressurise the suction vessel
(S-11 item 13, MFR); throttle the discharge to reduce flow and NPSHR (S-10, MFR); tougher materials where it is
unavoidable (S-01 p. 21, IND).

**Not supported / UNV:**
- `pressure_fluctuation` as a cavitation symptom (KB weights l12; rule R02). No source read names pressure
  fluctuation. S-07 mentions *pulsations* only for low-flow separation.
- `suction_pressure_low` < 0.70 bar(a). The *concept* (low suction pressure) is IND; the threshold is UNV.
- `flow_fluctuation` (KB weights l13): UNV.

## 5. Dry running / loss of prime (KB F07)
**Mechanism.** Absence of the liquid that normally cools, lubricates and centres running parts (S-06, MFR). There
is also *partial* dry running when gas bubbles reach normally wetted parts (S-06).
- Seals, packing and wear rings "are susceptible to damage if they are not lubricated" (S-01 p. 31, IND).
- Mechanical-seal faces depend on a liquid film; air in the gap causes dry running and "thermal overload of the
  seal faces and mechanical seal failure (heat stress cracks)" (S-08, MFR).

| Root cause | Source | Level |
|---|---|---|
| No liquid in the pump / operation without liquid fill | S-06; S-08 | MFR |
| Ingress of air in the suction line | S-06 | MFR |
| Gas ingress, high gas content, or evaporation of the fluid | S-08 | MFR |
| Vortex at low liquid level → loss of suction head or air into the pump → **loss of prime** | S-01 p. 31 | IND |
| Air drawn in through improperly installed packing (suction below atmospheric) → pump cannot stay primed | S-01 p. 22 | IND |
| Lack of / loss of prime; incomplete priming | S-11 items 1, 25 | MFR |

| Symptom / consequence | Source | Level |
|---|---|---|
| Overheating, abrasion, seizure, vibration → possible "complete disintegration of the pump" | S-06 | MFR |
| Mechanical-seal heat-stress cracks / seal failure | S-08 | MFR |
| Seal, packing, wear-ring damage | S-01 p. 31 | IND |
| No liquid delivered | S-11 items 1–7 | MFR |
| Severe performance degradation and pump damage after loss of prime | S-01 p. 31 | IND |

**Protection / tests:** dry-running protection device that stops the pump (S-06, MFR); quench as dry-running
protection for seals (KSB search summary only — not read); priming checks, venting air and checking suction
joints (S-11, MFR).

**Not supported / UNV:**
- KB `rapid_temp_rise` and `seal_temp_high ≥ 85 °C` as numeric indicators. "Overheating" is MFR-supported; the
  thresholds are UNV.
- KB `grinding_noise` (weights l39): UNV.
- KA-1 C-10 candidates `vibration_high` (S-06 MFR: "vibrations") and seal damage (S-08 MFR, S-01 p. 31 IND) are now
  **source-supported**.

## 6. Air ingress (KB F12)
**Mechanism.** Gas in the liquid blocks the impeller inlet. In the extreme the pump "becomes air-bound" and flow
stops, and near shut-off "even with small percentages of gas, the unit stops pumping liquid". Smaller amounts
reduce flow and head through blockage and lower mixture density (S-03, IND).

| Root cause | Source | Level |
|---|---|---|
| Air leaks in suction piping / flanges | S-11 items 8, 19, 27 | MFR |
| Air through improperly installed packing where suction is below atmospheric | S-01 p. 22 | IND |
| Vortex formation when liquid level is too close to the suction inlet; inadequate submergence | S-01 p. 31; S-11 item 16 | IND+MFR |
| Gas in the liquid (dissolved gas coming out of solution) | S-03; S-11 item 22 | IND+MFR |
| Vapour collection in poorly sloped suction piping → pressure pulsations | S-01 p. 31 | IND |

| Symptom / consequence | Source | Level |
|---|---|---|
| Reduced flow and head; flow stoppage (air-bound) | S-03; S-11 ("Not enough liquid / pressure") | IND+MFR |
| Pump operates for a short time, then stops | S-11 items 27–28 | MFR |
| Loss of prime / failure to re-prime | S-01 pp. 22, 31 | IND |
| Partial dry running of wetted parts | S-06 | MFR |
| Pressure pulsations (from vapour pockets) | S-01 p. 31 | IND |

**Tests / remedies:** leak-test suction flanges (e.g. pressurise the line and watch for pressure drop); increase
submergence or fit a vortex breaker; gas-separation chamber with venting (S-11, MFR). Run at or beyond BEP flow
when gas is present (S-03, IND).

**Not supported / UNV:**
- Any gas-volume % limit. S-03 gives none; trade-press figures (2 %, 4 %, 10 %) were seen only in search
  summaries → UNV.
- KB `air_bubbles` as a *visual* symptom is plausible but **no source read names it**. UNV.
- `pressure_fluctuation` for air ingress: only "pressure pulsations" from vapour collection (S-01 p. 31). That is
  partial support at most → UNV pending a direct source.

## 7. Suction blockage / clogged strainer (KB F06) and impeller blockage (KB F04)
| Statement | Source | Level |
|---|---|---|
| Suction starved by fouling of pipes → cavitation damage | S-01 p. 20 | IND |
| Fouling increases pressure drop | S-01 p. 19 | IND |
| Foot valve too small or partially obstructed; strainer open area should be 3–4 × the suction-pipe area | S-11 item 15 (as summarised by the fetch tool) | MFR (model-specific guidance) |
| Impeller completely / partially plugged → no / not enough liquid; dismantle and clean | S-11 items 7, 11 | MFR |
| Obstruction in liquid passages → not enough pressure | S-11 item 21 | MFR |
| Valves must be wide open; check suction friction losses | S-11 items 3, 26 | MFR |

**Assessment.**
- IND (S-01 p. 20) supports suction fouling as a **cause of cavitation**, which backs KA-1's finding that a
  clogged strainer is better modelled as a *root cause* (C-06, C-07) than as a separate fault.
- No source read gives distinguishing symptoms of suction blockage versus cavitation, or a strainer
  differential-pressure test value → **UNV**.
- KB rule R06 (suction_pressure_low ∧ flow_low ∧ discharge_pressure_low → F06) remains UNV.

## 8. Bearing failure (KB F01)
**Mechanism / classification.**
- ISO 15243 classifies in-service rolling-bearing damage by visible features into six main failure modes:
  fatigue (subsurface / surface initiated), wear (abrasive / adhesive), corrosion (moisture / fretting / false
  brinelling), electrical erosion (excessive voltage / current leakage), plastic deformation (overload /
  indentation), and fracture and cracking (forced / fatigue / thermal). Source: S-12, describing ISO 15243:2004
  (MFR description of an IND standard; standard text not read).
- Damage ≠ failure: a damaged bearing may still function (S-12).

| Root cause | Source | Level |
|---|---|---|
| High loads, poor lubrication, high operating temperature, vibration accelerate bearing wear | S-01 p. 16 | IND |
| Inadequate lubrication (contamination, wrong viscosity) → surface-initiated fatigue | S-12 p. 4 | MFR |
| Contamination / inadequate sealing → abrasive wear, indentation from debris | S-12 pp. 4–5 | MFR |
| Over-greasing interferes with rolling motion → overheating | S-01 p. 33 | IND |
| Improper mounting / handling; wrong fits; misalignment outside limits | S-12 pp. 2, 5–6 | MFR |
| Electrical current through the bearing | S-12 p. 5 | MFR |
| Cavitation-induced impeller unbalance → alternating bearing loads | S-01 p. 21 | IND |
| Shaft deflection (unequal radial pressure around the impeller) → high bearing wear | S-01 p. 22 | IND |
| Throttled / oversized pump operation → higher-than-normal bearing wear | S-01 p. 25 | IND |
| Distribution of causes among failed bearings: ~1/3 fatigue, ~1/3 lubrication, ~1/6 contamination, ~1/6 other (handling, mounting); varies by industry | S-12 p. 2 ("SKF experience") | MFR — **vendor statistic, not general fact** |

| Symptom / detection | Source | Level |
|---|---|---|
| Noise indicating wear; worn bearings can be noisy or seize | S-01 p. 34 | IND |
| Elevated operating temperature (measure it); hot-running bearing visible on IR thermography | S-01 pp. 34, 36 | IND |
| Vibration analysis vs baseline detects beginning bearing problems | S-01 pp. 34, 36 | IND |
| Oil analysis indicates bearing condition and end of life | S-01 pp. 16, 36 | IND |
| Visual damage features for root-cause analysis after removal (ISO 15243) | S-12 | MFR (describing IND standard) |

**Assessment.**
- KB links F01 → `vibration_high`, `bearing_temp_high`, `grinding_noise` are **IND-supported as indicators
  (direction only)**.
- Their thresholds (6.0 mm/s, 80 °C) are UNV.
- `motor_current_high` and `efficiency_low` for F01 are UNV.

## 9. Shaft misalignment (KB F03)
| Statement | Source | Level |
|---|---|---|
| Piping pulled into position strains the casing and "pull[s] the pump out of alignment"; proper pipe support avoids it | S-01 p. 32 | IND |
| Casing distorted by pipe strain; misalignment → pump takes too much power; check alignment, realign | S-11 items 35, 38 | MFR |
| Motor shifting can cause misalignment; check periodically | S-01 p. 34 | IND |
| Purpose of alignment is to minimise vibration from forces across the coupling; except in extreme cases, "the resulting vibration is what damages bearings and seals" | S-13 | MFR/trade |
| Mechanical seals need precise alignment (micron-level face tolerances) | S-01 p. 22 | IND |

| Diagnostic test | Source | Level |
|---|---|---|
| Dial-indicator total indicated runout (TIR); laser alignment for precise requirements; tolerances from the pump manual | S-01 p. 34 | IND |
| Straightedge/feeler gauge, taper gauge, rim-and-face / reverse-dial, laser | S-13 | MFR/trade |
| Vibration readings to reveal changes; vibration technician to confirm misalignment as the cause | S-01 p. 34; S-13 | IND+MFR |
| Shaft runout ≤ 0.002 in on the shaft (bent-shaft check, model-specific) | S-11 item 36 | MFR (model-specific value) |

**Not supported / UNV:**
- Specific **vibration signature** (dominant 2× running speed, axial vibration). Only search snippets were seen
  (L-1, and a Hydraulic Institute FAQ that was not read). UNV until a source is read.
- Misalignment → **bearing temperature high** (KB weights l17, rule R03): no source read states it. S-13 states that
  vibration, not bearing load, is the main damage path. So KA-1 C-05 **remains open**.
- Soft foot as a cause: not stated in any source read (only "motor shifting", "pipe strain"). UNV.
- Alignment tolerance numbers (S-13 figures are uncited practitioner guidance): UNV as general values.

## 10. Mechanical seal failure (KB F05)
**Mechanism.** Two faces pressed together slide on a liquid lubricating film (gap < 1 µm assumed for leakage
calculations); leakage normally escapes as vapour or droplets (S-08, MFR).

| Root cause | Source | Level |
|---|---|---|
| Contamination of seal faces; debris wedging into the faces | S-01 pp. 16, 22 | IND |
| Overheating due to inadequate lubrication | S-01 p. 16 | IND |
| Dry running, gas ingress, evaporation → heat-stress cracks | S-08 | MFR → with S-01: **IND+MFR** (lubrication loss → overheating) |
| Improper installation | S-01 p. 16 | IND |
| Loss of spring/bellows force (fatigue, corrosive degradation) | S-01 p. 22 | IND |
| Misalignment of the seal / shaft deflection → seal leakage | S-01 p. 22 | IND |
| Abrasive fluids → wear (mitigated by clean flush/barrier fluid) | S-08 | MFR |
| Cavitation accelerates seal wear | S-01 p. 20 | IND |
| Bearing or seal seizure can score the shaft sleeve | S-01 p. 34 | IND |

| Symptom / test | Source | Level |
|---|---|---|
| Leakage — check and measure; replace if above the manufacturer's specification | S-01 pp. 33–34 | IND |
| Excessive leakage indicates need for repair | S-01 p. 35 | IND |
| Visual failure analysis of faces (heat checking, wear patterns) | L-2 (not read) | lead |

**Assessment.**
- KB F05 → `seal_leakage` is **IND-supported**.
- `seal_temp_high` as a seal-failure symptom: only implied ("overheating", S-01 p. 16). The ≥ 85 °C value is UNV.
- F05 → `vibration_high` (weights l27) and `bearing_temp_high` (l28): UNV.
- Dataset causes "seal face wear", "elastomer degradation", "seal flush failure": face degradation is IND; the
  others are not named in sources read (flush only indirectly via S-08) → UNV.

## 11. Impeller damage (KB F10) and wear-ring wear
| Statement | Source | Level |
|---|---|---|
| Cavitation erodes impellers; severe cavitation or erosion degrades the impeller and reduces performance | S-01 pp. 20, 35; S-04 | IND+MFR |
| Material loss → impeller unbalance → bearing loads | S-01 p. 21 | IND |
| Abrasive particulates erode some pumps (e.g. multistage) | S-01 p. 7 | IND |
| Cavitation + oxygen → increased corrosion | S-04 | MFR |
| Defective / badly eroded impeller → not enough liquid; inspect impeller, bearings, shaft | S-11 item 14 | MFR |
| Wear-ring clearances grow with erosion → internal leakage → performance decline; a "substantial decline in the pump's performance" indicates wear-ring replacement | S-01 pp. 16, 35 | IND |

**Assessment.**
- F10 → reduced flow/head/performance is **IND-supported**.
- F10 → `vibration_high` is supported only **via unbalance** (IND).
- Wear-ring wear is a **missing fault/cause** in the KB (KA-1 G-06): IND-supported, and its symptom is a
  performance decline.
- Foreign-object impact as a cause: not in sources read → UNV.

## 12. Discharge restriction / closed valve / low-flow operation (KB F11)
| Statement | Source | Level |
|---|---|---|
| At shut-off "the drive's high output power is transferred to the fluid handled leading to a rapid temperature increase", leading to evaporation, seizure in clearance gaps, and possible bursting with a closed check valve | S-07 | MFR |
| Continuous operation is not permitted from zero flow to the operating limit; recirculation and separation at low flow | S-07; S-02 | IND+MFR |
| Operation outside the POR → additional loading and flow-induced vibration | S-02 | IND |
| Highly throttled valves / high backpressure → higher-than-normal bearing wear; excessive flow noise | S-01 p. 25 | IND |
| Radial pump: power/current **lowest** at closed discharge (deadhead) | S-01 p. 17 | IND |
| High-static-head systems at reduced speed can operate near shut-off → poor performance or damage | S-01 p. 17 | IND |
| Minimum flow is pump-specific (Qmin) | S-09 | MFR |

**Assessment.**
- F11 → temperature rise is **IND+MFR** (KB `rapid_temp_rise` supported in direction; no threshold).
- F11 → vibration is **IND** (S-02). This is KA-1 candidate C-10, now supported.
- F11 → `discharge_pressure_high`: the head rises toward shut-off on the curve. This is implied by the pump-curve
  description, but no source read states it as a symptom → UNV (likely; needs a direct citation).
- F11 → `motor_current_high` (KB weights l57) is **contradicted for radial pumps** (S-01 p. 17, IND). It would be
  correct only for axial / high specific-speed pumps. **Resolves KA-1 C-04:** the link must be conditional on pump
  type.
- The same reasoning applies to F04 → `motor_current_high` (weights l24) when blockage reduces flow → contradicted
  for radial pumps.

## 13. Vibration thresholds and standards
- **ISO 10816-7:2009** is the pump-specific vibration evaluation standard. From catalogue listings (S-14, scope
  only):
  - It covers rotodynamic pumps for industrial use above 1 kW, measured on non-rotating parts.
  - It defines evaluation zones with limits for horizontal and vertical pumps (Annex A), plus guidance for alarm and
    trip settings.
  - It is to be revised as ISO 20816-7 (approved work item, seen via search).
- **The zone values were not obtained.** Therefore:
  - The KB's 6.0 mm/s threshold remains **UNV**.
  - The preprocessing's "ISO 10816-3-style" 4.5 mm/s boundary
    (`data_preparation/scripts/preprocess_dataset.py:29`) remains **UNV**. It also refers to the general-machinery
    part, not the pump-specific part 7. **It should not be described as standard-based until Annex A of
    ISO 10816-7 has been read.**
- No temperature, current or pressure-fluctuation alarm values were found in any source read. All KB thresholds
  ([src/inference_engine.py:28-49](../../src/inference_engine.py#L28-L49)) remain **UNV**.

---

## 14. Effect on the KA-1 findings
| KA-1 item | Before | After KA-2 |
|---|---|---|
| C-04 motor current at low flow | open | **Resolved (IND, S-01 p. 17):** radial pumps draw *less* current at low flow; KB links F11/F04 → motor_current_high contradicted for radial pumps; link must be conditional on pump type |
| C-05 misalignment → bearing temperature (R03) | open | **Still open.** No source read; S-13 points to vibration as the damage path |
| C-06/C-07 clogged strainer level | open | **Supported as a cause of cavitation** (S-01 p. 20, IND); discriminating test still missing |
| C-10 F07 → vibration | candidate | **MFR-supported** (S-06) |
| C-10 F11 → vibration | candidate | **IND-supported** (S-02) |
| Dry running → seal damage (mapping §5.2) | A+B only | **IND+MFR** (S-01 p. 31; S-08) |
| Cavitation → impeller erosion (mapping §5.2) | A+B | **IND+MFR** (S-01; S-04) |
| Cavitation → bearing/seal wear | not in KB | **IND** (S-01 pp. 20–21) — new link |
| Wear-ring wear (G-06) | missing | **IND** cause of performance decline (S-01 pp. 16, 35) — new fault/cause candidate |
| Thresholds (C-01) | UNV | **Still UNV.** Standards located (ISO 10816-7, ANSI/HI 9.6.1/9.6.3) but values not obtained |
| `docs/SOURCE_NOTES.md` summaries D-2, D-3 | not re-verified | **Re-verified** against S-06, S-07; summaries are accurate (D-2 correctly does not claim seal damage) |

## 15. Summary of support by fault
| Fault | Mechanism | Causes | Symptoms (direction) | Tests | Thresholds |
|---|---|---|---|---|---|
| Cavitation | IND+MFR | IND+MFR | IND+MFR (noise, head loss, erosion, vibration) | IND (NPSH) | UNV |
| Dry running | MFR (+IND seal/wear-ring damage) | IND+MFR | MFR (overheating, vibration, seizure); IND (damage) | MFR (protection device) | UNV |
| Air ingress | IND | IND+MFR | IND+MFR (flow/head loss, loss of prime) | MFR (leak test, submergence) | UNV (no gas % limit) |
| Suction blockage | IND (as cause of cavitation) | MFR | MFR (no/low flow) | **UNV** | UNV |
| Bearing failure | MFR (ISO 15243 via SKF) | IND+MFR | IND (noise, temperature, vibration) | IND (vibration, oil, IR) | UNV |
| Misalignment | IND (pipe strain, motor shift) | IND | MFR (vibration → bearing/seal damage); signature **UNV** | IND (dial/laser) | UNV |
| Mechanical seal | MFR | IND+MFR | IND (leakage) | IND (leak measurement) | UNV |
| Impeller damage | IND+MFR | IND+MFR | IND (performance loss, unbalance) | IND (performance decline) | UNV |
| Discharge restriction / low flow | IND+MFR | IND | IND+MFR (temperature rise, vibration, recirculation); current ↓ for radial pumps | IND (operating region vs POR/AOR) | UNV (pump-specific Qmin) |

## 16. Limitations of this research
- **Few primary standards read.** Standards were located but only their scope was seen (ISO 10816-7, ISO 15243)
  or a scanned copy could not be text-extracted (ANSI/HI 9.6.1). Numeric limits therefore remain unvalidated.
- **No textbook read** (L-3). The DOE/HI sourcebook is a practical guide, not a diagnostic reference.
- **Manufacturer sources** reflect their own products. The Goulds table is for one model, and the SKF statistics
  are company experience.
- **DOE text was machine-extracted.** A few words are lost at layout breaks. Quotes are short and page-referenced
  but should be re-checked in the PDF before use in the final report.
- **Search-summary claims excluded.** Claims seen only in search summaries (gas-% limits, 2× misalignment
  signature, seal heat checking, NPSH margin values) are **not** used as evidence.

## 17. Recommended next steps (KA-3)
1. Obtain ISO 10816-7 Annex A (zone limits) through the university library before setting any vibration threshold.
2. Obtain ANSI/HI 9.6.1 (margin tables) and 9.6.3 (POR/AOR) text, or a textbook chapter, for NPSH and low-flow limits.
3. Read one pump textbook chapter on troubleshooting (Karassik *Pump Handbook* or Gülich) to independently confirm
   the misalignment vibration signature and the suction-blockage vs cavitation discrimination.
4. Read one seal-failure-analysis guide (L-2) for seal cause → finding relationships.
5. Record each relationship's source ID (S-xx) in the future `sources.csv`/relationship tables proposed in
   `knowledge_acquisition/audit/recommended_knowledge_model.md`, using these levels: IND / MFR / IND+MFR → candidate
   for `documented`; UNV → stays `unvalidated`.
