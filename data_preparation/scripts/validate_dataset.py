"""Phase 7: validate the cleaned/processed datasets and compare them with the raw data.

Part A  structural validation of the cleaned dataset (no ground truth needed)
Part B  before/after data-quality comparison (raw vs cleaned)
Part C  evaluation against the generation log — only possible because the data is synthetic.
        This is the ONLY script that reads data/generation_log/.

Writes reports/validation_report.md and data/processed/validation_summary.json.
Exits with code 1 if any Part A check fails.
"""
from __future__ import annotations

import json
import re
import sys

import numpy as np
import pandas as pd

from common import (CLEAN_FILE, COLUMNS, FAULT_LABELS, GENLOG, PLAUSIBLE, PROCESSED, PROCESSED_FILE,
                    RAW_FILE, REGISTER_FILE, REPORTS, SENSOR_COLS, md_table)

NUMERIC = ["Operating_Hours", *SENSOR_COLS, "Downtime_Hours", "Maintenance_Cost"]
DATES = ["Installation_Date", "Observation_Date", "Maintenance_Date"]
CATS = ["Pump_ID", "Pump_Type", "Manufacturer", "Fault_Type", "Root_Cause", "Fault_Severity",
        "Diagnostic_Status", "Maintenance_Action", "Maintenance_Priority"]
NULLS = {"", "n/a", "na", "null", "none", "nan", "--", "-", "?", "err", "#value!", "sensor fault"}
NO_MAINT = "No action required"


def load():
    raw = pd.read_csv(RAW_FILE, dtype=str, keep_default_na=False)
    cl = pd.read_csv(CLEAN_FILE, dtype=str, keep_default_na=False)
    for c in NUMERIC:
        cl[c] = pd.to_numeric(cl[c].replace("", np.nan))
    pr = pd.read_csv(PROCESSED_FILE, low_memory=False)
    ref = pd.read_csv(GENLOG / "clean_reference_dataset.csv", dtype=str, keep_default_na=False)
    for c in NUMERIC:
        ref[c] = pd.to_numeric(ref[c].replace("", np.nan))
    log = pd.read_csv(GENLOG / "injected_issues.csv", dtype=str, keep_default_na=False)
    reg = pd.read_csv(REGISTER_FILE)
    return raw, cl, pr, ref, log, reg


# ------------------------------------------------------------------------------------------- A
def structural(raw, cl, pr, reg):
    has_m = cl.Maintenance_Action != NO_MAINT
    merged = set(";".join(cl.Merged_Record_IDs).split(";")) - {""}
    raw_ids = set(raw.Record_ID)
    checks = [
        ("No exact duplicate rows", int(cl[COLUMNS].duplicated().sum())),
        ("Record_ID unique", int(cl.Record_ID.duplicated().sum())),
        ("No two records for the same pump on the same date", int(cl.duplicated(["Pump_ID", "Observation_Date"]).sum())),
        ("Record_ID format R-nnnnnn", int((~cl.Record_ID.str.fullmatch(r"R-\d{6}")).sum())),
        ("Pump_ID exists in asset register", int((~cl.Pump_ID.isin(reg.Pump_ID)).sum())),
        ("Every raw Record_ID kept or listed as merged (no accidental loss)",
         len(raw_ids - set(cl.Record_ID) - merged)),
        ("Numeric columns fully numeric", sum(int(cl[c].isna().sum() - (~has_m).sum()) if c in
                                              ("Downtime_Hours", "Maintenance_Cost") else 0 for c in NUMERIC)
         + sum(int(not pd.api.types.is_numeric_dtype(cl[c])) for c in NUMERIC)),
        ("No missing sensor values / operating hours", int(cl[SENSOR_COLS + ["Operating_Hours"]].isna().sum().sum())),
        ("All sensor values inside physical limits (single, consistent units)",
         int(sum((~cl[c].between(*PLAUSIBLE[c])).sum() for c in SENSOR_COLS))),
        ("Dates are ISO YYYY-MM-DD", int(sum((~cl[c].str.fullmatch(r"\d{4}-\d{2}-\d{2}") & (cl[c] != "")).sum()
                                             for c in DATES))),
        ("Maintenance date on/after observation date",
         int((pd.to_datetime(cl.Maintenance_Date.replace("", None)) < pd.to_datetime(cl.Observation_Date)).sum())),
        ("Installation before observation",
         int((pd.to_datetime(cl.Installation_Date) > pd.to_datetime(cl.Observation_Date)).sum())),
        ("Maintenance fields present iff a maintenance action exists",
         int(((cl.Maintenance_Date != "") != has_m).sum() + (cl.Downtime_Hours.notna() != has_m).sum())),
        ("Operating hours non-decreasing within each pump",
         int((cl.sort_values(["Pump_ID", "Observation_Date"]).groupby("Pump_ID").Operating_Hours.diff() < 0).sum())),
        ("Fault_Type in controlled vocabulary", int((~cl.Fault_Type.isin(FAULT_LABELS)).sum())),
        ("No empty categorical values", int(sum((cl[c] == "").sum() for c in CATS))),
        ("Processed: same rows as cleaned", abs(len(pr) - len(cl))),
        ("Processed: no pump in two partitions", int((pr.groupby("Pump_ID").Partition.nunique() > 1).sum())),
        ("Processed: every fault class present in every partition",
         int((pd.crosstab(pr.Fault_Type, pr.Partition) == 0).sum().sum())),
    ]
    return pd.DataFrame(checks, columns=["check", "violations"]).assign(
        result=lambda d: np.where(d.violations == 0, "PASS", "FAIL"))


# ------------------------------------------------------------------------------------------- B
def before_after(raw, cl):
    def nonnum(df):
        n = 0
        for c in NUMERIC:
            s = df[c].astype("string").fillna("").str.strip()
            n += int((pd.to_numeric(s, errors="coerce").isna() & ~s.str.lower().isin(NULLS)).sum())
        return n
    def missing_sensor(df):
        return int(sum(df[c].astype(str).str.strip().str.lower().isin(NULLS).sum() for c in SENSOR_COLS))
    def implausible(df):
        return int(sum((~pd.to_numeric(df[c], errors="coerce").dropna().between(*PLAUSIBLE[c])).sum()
                       for c in SENSOR_COLS))
    def date_formats(df):
        f = set()
        for c in DATES:
            for v in df[c]:
                if v:
                    f.add(re.sub(r"\d", "9", re.sub(r"[A-Za-z]{3}", "Mon", v)))
        return len(f)
    rows = [("Rows", len(raw), len(cl)),
            ("Exact duplicate rows", int(raw.duplicated().sum()), int(cl[COLUMNS].duplicated().sum())),
            ("Duplicate Record_IDs", int(raw.Record_ID.duplicated().sum()), int(cl.Record_ID.duplicated().sum())),
            ("Missing / null-token sensor cells", missing_sensor(raw), missing_sensor(cl.astype(str).replace("nan", ""))),
            ("Non-numeric text in numeric columns (units, commas, $)", nonnum(raw), nonnum(cl)),
            ("Physically implausible sensor values", implausible(raw), implausible(cl)),
            ("Distinct date formats", date_formats(raw), date_formats(cl)),
            ("Distinct Pump_ID spellings", raw.Pump_ID.nunique(), cl.Pump_ID.nunique())]
    for c in ["Pump_Type", "Manufacturer", "Fault_Type", "Fault_Severity", "Diagnostic_Status",
              "Maintenance_Priority", "Maintenance_Action"]:
        rows.append((f"Distinct values: {c}", raw[c].nunique(), cl[c].nunique()))
    rows.append(("Distinct Observed_Symptoms strings", raw.Observed_Symptoms.nunique(), cl.Observed_Symptoms.nunique()))
    t = pd.DataFrame(rows, columns=["metric", "raw", "cleaned"])
    stats = []
    for c in SENSOR_COLS:
        r = pd.to_numeric(raw[c], errors="coerce")
        stats.append({"sensor": c, "raw mean": r.mean(), "raw std": r.std(), "raw max": r.max(),
                      "clean mean": cl[c].mean(), "clean std": cl[c].std(), "clean max": cl[c].max()})
    return t, pd.DataFrame(stats)


# ------------------------------------------------------------------------------------------- C
def evaluate(cl, ref, log):
    cli = cl.set_index("Record_ID")
    refi = ref.set_index("Record_ID")
    imputed = cli.Imputed_Columns.str.split(";")
    nullified = (cli.Invalid_Columns + ";" + cli.Suspect_Outlier_Columns).str.split(";")
    res = {}
    res["reference_rows"] = len(ref)
    res["cleaned_rows"] = len(cl)
    res["ids_missing_from_cleaned"] = len(set(ref.Record_ID) - set(cl.Record_ID))
    res["ids_not_in_reference"] = len(set(cl.Record_ID) - set(ref.Record_ID))

    cell = log[log.column != "*"].drop_duplicates(["Record_ID", "column"], keep="last")
    out = []
    for _, r in cell.iterrows():
        rid, col, issue = r.Record_ID, r.column, r.issue_type
        if rid not in cli.index:
            continue
        cv, rv = cli.at[rid, col], refi.at[rid, col]
        was_imp = col in imputed[rid]
        if col in NUMERIC:
            ok = pd.notna(cv) and pd.notna(rv) and np.isclose(cv, rv, rtol=.01, atol=.15)
            # order matters: a value that was nullified/imputed is never credited as "restored",
            # even if the imputed number happens to land close to the truth
            if col in nullified[rid]:
                outcome = "detected → nullified + imputed"
            elif was_imp:
                outcome = "imputed (flagged)"
            elif ok:
                outcome = "restored"
            elif issue in ("implausible_value", "outlier_decimal_shift"):
                outcome = "NOT detected"
            else:
                outcome = "WRONG value"
            err = abs(cv - rv) if pd.notna(cv) and pd.notna(rv) else np.nan
        else:
            err = np.nan
            if col == "Observed_Symptoms" and cv == "Not Recorded":
                outcome = "marked Not Recorded"
            elif cv == rv:
                outcome = "restored"
            elif col == "Supporting_Evidence" and cv.lower() == rv.lower():
                outcome = "restored (case-insensitive)"
            elif cv == "Unknown" and issue in ("missing_categorical", "missing_fault_label"):
                outcome = "marked Unknown (not guessed)"
            else:
                outcome = "WRONG value"
        out.append({"issue_type": issue, "column": col, "outcome": outcome, "abs_error": err})
    cells = pd.DataFrame(out)
    summary = (cells.groupby(["issue_type", "outcome"]).size().unstack(fill_value=0))
    res["cells_evaluated"] = len(cells)
    res["cells_wrong"] = int(cells.outcome.isin(["WRONG value", "NOT detected", "NOT handled"]).sum())
    imp_err = (cells[cells.outcome == "imputed (flagged)"].groupby("column").abs_error
               .agg(["count", "median", "mean"]).rename(columns={"median": "median |error|", "mean": "mean |error|"}))

    # duplicates
    ex = log[log.issue_type == "exact_duplicate"].Record_ID
    nd = log[log.issue_type == "near_duplicate"].Record_ID
    merged = set(";".join(cl.Merged_Record_IDs).split(";"))
    res["exact_duplicates_injected"] = len(ex)
    res["exact_duplicates_remaining"] = int(cl.Record_ID.isin(ex).groupby(cl.Record_ID).size().gt(1).sum())
    res["near_duplicates_injected"] = len(nd)
    res["near_duplicates_removed"] = int((~nd.isin(cl.Record_ID) & nd.isin(merged)).sum())

    # false positives: genuine values nullified without any injected issue on that cell
    injected_cells = set(zip(log.Record_ID, log.column))
    fp = []
    for rid, cols in nullified.items():
        for c in filter(None, cols):
            if (rid, c) not in injected_cells:
                fp.append({"Record_ID": rid, "column": c, "fault": cli.at[rid, "Fault_Type"],
                           "true value": refi.at[rid, c]})
    res["genuine_values_wrongly_nullified"] = len(fp)

    # column accuracy over all rows
    acc = []
    common = cl.Record_ID[cl.Record_ID.isin(ref.Record_ID)]
    a, b = cli.loc[common], refi.loc[common]
    for c in [*CATS, *DATES, "Observed_Symptoms"]:
        acc.append({"column": c, "match %": 100 * (a[c] == b[c]).mean()})
    for c in NUMERIC:
        m = (np.isclose(a[c], b[c], rtol=.01, atol=.15) | (a[c].isna() & b[c].isna()))
        acc.append({"column": c, "match %": 100 * m.mean()})
    acc = pd.DataFrame(acc)

    # fault label preservation
    lab = pd.DataFrame({"reference": b.Fault_Type.value_counts(), "cleaned": a.Fault_Type.value_counts()}).fillna(0)
    lab["difference"] = lab.cleaned - lab.reference
    mis = a.Fault_Type != b.Fault_Type
    conf = pd.crosstab(b.Fault_Type[mis], a.Fault_Type[mis]) if mis.any() else pd.DataFrame()
    res["fault_labels_changed"] = int(mis.sum())
    res["fault_labels_changed_other_than_missing_to_unknown"] = int((mis & ~a.Label_Missing_In_Source.eq("True")).sum())
    return res, summary, imp_err, acc, lab.astype(int), conf, pd.DataFrame(fp)


def main():
    raw, cl, pr, ref, log, reg = load()
    A = structural(raw, cl, pr, reg)
    B, stats = before_after(raw, cl)
    res, summary, imp_err, acc, lab, conf, fp = evaluate(cl, ref, log)
    summary_json = {"structural_checks_failed": int((A.result == "FAIL").sum()), **res}
    (PROCESSED / "validation_summary.json").write_text(json.dumps(summary_json, indent=2), encoding="utf-8")

    L = ["# Final Dataset Validation Report",
         "",
         "_Generated by `scripts/validate_dataset.py`._",
         "",
         "## A. Structural validation of the cleaned and processed datasets",
         f"**{(A.result == 'PASS').sum()} / {len(A)} checks passed.**", "",
         md_table(A), "",
         "## B. Before-and-after data-quality summary",
         md_table(B), "",
         "Sensor statistics (raw = values that happened to parse as numbers, including sentinels such as 9999):", "",
         md_table(stats, floatfmt=".2f"), "",
         "## C. Evaluation against the generation log (synthetic ground truth)",
         "Because the dataset is synthetic, the pre-corruption reference and a cell-level log of every injected "
         "problem exist. The cleaning script never read them; they are used here only to score it. "
         "**This kind of scoring is impossible with real plant data.**", "",
         f"- Reference records: {res['reference_rows']:,} · cleaned records: {res['cleaned_rows']:,} · reference IDs "
         f"missing from cleaned: **{res['ids_missing_from_cleaned']}** · extra IDs: **{res['ids_not_in_reference']}**",
         f"- Exact duplicates injected: {res['exact_duplicates_injected']} · still present: "
         f"**{res['exact_duplicates_remaining']}**",
         f"- Near-duplicates injected: {res['near_duplicates_injected']} · removed and recorded in Merged_Record_IDs: "
         f"**{res['near_duplicates_removed']}**",
         f"- Corrupted cells evaluated: {res['cells_evaluated']:,} · wrong / undetected: **{res['cells_wrong']}**",
         f"- Genuine (uncorrupted) values wrongly nullified as errors: **{res['genuine_values_wrongly_nullified']}**",
         f"- Fault labels differing from reference: {res['fault_labels_changed']} — of which not explained by a "
         f"missing source label: **{res['fault_labels_changed_other_than_missing_to_unknown']}**", "",
         "**How to read a perfect score.** The same project wrote the corruption step and the cleaning rules, and "
         "the cleaning rules were designed from the quality report of this very file. A score of zero errors "
         "therefore shows that every *catalogued* problem type is handled correctly and that no genuine value was "
         "damaged — it does **not** show that the pipeline would handle unseen problems in real plant data "
         "(new unit spellings, new label variants, sensor drift, mis-labelled faults). Unmapped values are listed "
         "in the cleaning report precisely so such cases surface on new data.", "",
         "### Outcome per injected issue type (cells)", "",
         md_table(summary, index=True), "",
         "Outcome meanings: *restored* = cleaned value equals the reference value; *imputed (flagged)* = the value "
         "was genuinely missing and was imputed with a flag (its true value is unknowable); *marked Unknown* = a "
         "missing diagnostic field was deliberately not guessed; *detected → nullified + imputed* = an error was "
         "recognised and replaced.", "",
         "### Imputation error (only measurable on synthetic data)", "",
         md_table(imp_err, index=True), "",
         "Median imputation recovers typical values well for Normal records but cannot recover fault-driven "
         "values — which is why imputed values are excluded from symptom derivation.", "",
         "### Agreement with the reference, all rows", "",
         md_table(acc), "",
         "Numeric columns below 100 % are explained by imputed cells; categorical columns below 100 % by values "
         "deliberately set to Unknown.", "",
         "### Fault cases preserved", "",
         md_table(lab, index=True), "",
         ("Label changes (reference → cleaned):\n\n" + md_table(conf, index=True)) if len(conf) else "", "",
         "### Genuine values wrongly treated as errors", "",
         md_table(fp) if len(fp) else "None.", "",
         ]
    (REPORTS / "validation_report.md").write_text("\n".join(L), encoding="utf-8")
    print(f"Validation: {(A.result == 'PASS').sum()}/{len(A)} structural checks passed; "
          f"{res['cells_wrong']} wrong cells of {res['cells_evaluated']}; "
          f"{res['genuine_values_wrongly_nullified']} genuine values nullified.")
    if (A.result == "FAIL").any():
        sys.exit(1)


if __name__ == "__main__":
    main()
