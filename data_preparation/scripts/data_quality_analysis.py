"""Phase 3: profile the RAW dataset and write reports/data_quality_report.md.

Read-only with respect to the raw data.  Deliberately does NOT read data/generation_log/
— the assessment must be based only on what an analyst can see in the raw export.
"""
from __future__ import annotations

import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from common import COLUMNS, PLAUSIBLE, RAW_FILE, REPORTS, SENSOR_COLS, UNITS, VIS, md_table

NUMERIC_COLS = ["Operating_Hours", *SENSOR_COLS, "Downtime_Hours", "Maintenance_Cost"]
DATE_COLS = ["Installation_Date", "Observation_Date", "Maintenance_Date"]
CAT_COLS = ["Pump_ID", "Pump_Type", "Manufacturer", "Fault_Type", "Root_Cause", "Fault_Severity",
            "Diagnostic_Status", "Maintenance_Action", "Maintenance_Priority"]
NULL_TOKENS = {"", "n/a", "na", "null", "none", "nan", "--", "-", "?", "err", "error", "#value!",
               "sensor fault"}

DATE_PATTERNS = {
    "ISO YYYY-MM-DD": r"^\d{4}-\d{2}-\d{2}$",
    "DD/MM/YYYY": r"^\d{2}/\d{2}/\d{4}$",
    "DD-Mon-YYYY": r"^\d{2}-[A-Za-z]{3}-\d{4}$",
    "YYYYMMDD": r"^\d{8}$",
    "YYYY/MM/DD": r"^\d{4}/\d{2}/\d{2}$",
}
VALUE_PATTERNS = {
    "plain number": r"^-?\d+(\.\d+)?$",
    "comma decimal": r"^-?\d+,\d{1,2}$",
    "thousands separator": r"^\d{1,3}(,\d{3})+(\.\d+)?$",
    "number + unit text": r"^\$?-?[\d,]+(\.\d+)?\s*[A-Za-z°/]+\.?$",
    "currency prefix": r"^\$[\d,]+(\.\d+)?$",
}


def load_raw() -> pd.DataFrame:
    """Everything as text, nothing auto-converted — so problems stay visible."""
    return pd.read_csv(RAW_FILE, dtype=str, keep_default_na=False)


def classify(series: pd.Series, patterns: dict) -> pd.Series:
    def one(v):
        if v.strip().lower() in NULL_TOKENS:
            return "empty" if v.strip() == "" else "null-like token"
        for name, rx in patterns.items():
            if re.match(rx, v.strip()):
                return name
        return "other"
    return series.map(one)


def overview(raw):
    return pd.DataFrame({
        "column": raw.columns,
        "pandas_default_dtype": [str(pd.read_csv(RAW_FILE, usecols=[c]).dtypes.iloc[0]) for c in raw.columns],
        "expected": ["numeric" if c in NUMERIC_COLS else "date" if c in DATE_COLS else "text/category"
                     for c in raw.columns],
        "distinct_values": [raw[c].nunique() for c in raw.columns],
    })


def missing_table(raw):
    out = []
    for c in raw.columns:
        s = raw[c].str.strip()
        empty = (s == "").sum()
        token = s.str.lower().isin(NULL_TOKENS - {""}).sum()
        out.append({"column": c, "empty_cells": int(empty), "null_like_tokens": int(token),
                    "missing_total": int(empty + token), "missing_%": round(100 * (empty + token) / len(raw), 2)})
    return pd.DataFrame(out)


def duplicate_summary(raw):
    exact = raw.duplicated(keep=False)
    norm_pid = raw.Pump_ID.str.upper().str.replace(r"[^0-9]", "", regex=True).str.lstrip("0")
    norm_date = parse_dates_loose(raw.Observation_Date)
    key = pd.DataFrame({"p": norm_pid, "d": norm_date})
    partial = key.duplicated(keep=False) & ~exact
    return {
        "rows": len(raw),
        "exact_duplicate_rows (all copies)": int(exact.sum()),
        "exact_duplicate_rows (redundant copies)": int(raw.duplicated().sum()),
        "duplicate Record_IDs": int(raw.Record_ID.duplicated().sum()),
        "same pump + same observation date, not exact copies": int(partial.sum()),
    }, raw[partial].sort_values(["Pump_ID", "Observation_Date"]).head(6)


def parse_dates_loose(s):
    out = pd.Series(pd.NaT, index=s.index)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y", "%Y%m%d", "%Y/%m/%d"):
        m = out.isna()
        out[m] = pd.to_datetime(s[m].str.strip(), format=fmt, errors="coerce")
    return out


def numeric_profile(raw):
    pattern_rows, stats_rows, outlier_rows = [], [], []
    for c in NUMERIC_COLS:
        cls = classify(raw[c], VALUE_PATTERNS)
        counts = cls.value_counts()
        examples = {k: raw.loc[cls == k, c].head(3).tolist() for k in counts.index if k != "plain number"}
        pattern_rows.append({"column": c, **counts.to_dict(),
                             "non_numeric_examples": "; ".join(f"{k}: {v}" for k, v in examples.items()
                                                               if k != "empty")[:160]})
        x = pd.to_numeric(raw[c], errors="coerce")
        d = x.describe()
        stats_rows.append({"column": c, "unit": UNITS.get(c, ""), "parseable": int(d["count"]),
                           "mean": d["mean"], "std": d["std"], "min": d["min"], "median": x.median(),
                           "max": d["max"]})
        q1, q3 = x.quantile([.25, .75])
        iqr = q3 - q1
        mad = (x - x.median()).abs().median()
        robust_z = 0.6745 * (x - x.median()) / mad if mad else pd.Series(0, index=x.index)
        lo, hi = PLAUSIBLE[c]
        outlier_rows.append({"column": c,
                             "IQR_fence_low": q1 - 1.5 * iqr, "IQR_fence_high": q3 + 1.5 * iqr,
                             "IQR_outliers": int(((x < q1 - 1.5 * iqr) | (x > q3 + 1.5 * iqr)).sum()),
                             "robust_z_gt_3.5": int((robust_z.abs() > 3.5).sum()),
                             "plausible_range": f"{lo} – {hi}",
                             "physically_implausible": int(((x < lo) | (x > hi)).sum())})
    patt = pd.DataFrame(pattern_rows).fillna(0)
    cnt = [c for c in patt.columns if c not in ("column", "non_numeric_examples")]
    patt[cnt] = patt[cnt].astype(int)
    return (patt[["column", *cnt, "non_numeric_examples"]], pd.DataFrame(stats_rows), pd.DataFrame(outlier_rows))


def outliers_by_label(raw):
    """Are statistical outliers concentrated in fault records (genuine) or normal ones (suspect)?"""
    label = raw.Fault_Type.str.strip().str.lower()
    is_normal = label.isin(["normal", "ok", "normal operation"])
    pump = raw.Pump_ID.str.upper().str.replace(r"[^0-9]", "", regex=True).str.lstrip("0")
    def iqr_flags(x):
        q1, q3 = x.quantile([.25, .75])
        return (x > q3 + 1.5 * (q3 - q1)) | (x < q1 - 1.5 * (q3 - q1))
    rows = []
    for c in ["Vibration_mm_s", "Bearing_Temperature_C", "Seal_Temperature_C", "Motor_Current",
              "Motor_Speed_RPM", "Pressure_Fluctuation"]:
        x = pd.to_numeric(raw[c], errors="coerce")
        lo, hi = PLAUSIBLE[c]
        plaus = x.between(lo, hi)
        xp = x.where(plaus)
        pooled = iqr_flags(xp)
        scaled = iqr_flags(xp / xp.groupby(pump).transform("median"))   # relative to the pump's own level
        rows.append({"column": c,
                     "pooled IQR: fault/unknown recs": int((pooled & ~is_normal).sum()),
                     "pooled IQR: 'normal' recs": int((pooled & is_normal).sum()),
                     "per-pump scaled IQR: 'normal' recs": int((scaled & is_normal).sum()),
                     "implausible (any record)": int((~plaus & x.notna()).sum())})
    return pd.DataFrame(rows)


def date_profile(raw):
    rows = []
    for c in DATE_COLS:
        rows.append({"column": c, **classify(raw[c], DATE_PATTERNS).value_counts().to_dict()})
    return pd.DataFrame(rows).fillna(0)


def category_variants(raw, col, top=12):
    """Group raw spellings by a normalised key to expose inconsistent variants."""
    s = raw[col]
    key = s.str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
    g = (pd.DataFrame({"key": key, "raw": s}).groupby("key")["raw"]
         .agg(variants=lambda v: sorted(set(v)), n="size").reset_index())
    g["n_variants"] = g.variants.map(len)
    g["variants"] = g.variants.map(lambda v: " · ".join(f"'{x}'" for x in v))
    return g.sort_values("n", ascending=False).head(top)[["variants", "n_variants", "n"]]


def symptom_profile(raw):
    s = raw.Observed_Symptoms
    seps = {"'; '": s.str.contains("; ", regex=False), "', '": s.str.contains(", ", regex=False),
            "' | '": s.str.contains(" | ", regex=False), "' / '": s.str.contains(" / ", regex=False),
            "' and '": s.str.contains(" and ", regex=False)}
    sep_tbl = pd.DataFrame({"separator": list(seps), "rows": [int(v.sum()) for v in seps.values()]})
    tokens = s.str.lower().str.split(r"\s*(?:;|,|\||/| and )\s*", regex=True).explode().str.strip(" .")
    tok = tokens[tokens != ""].value_counts()
    return sep_tbl, tok


def figures(raw, miss):
    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, 6))
    m = miss.sort_values("missing_%")
    ax.barh(m.column, m["missing_%"], color="#4C72B0")
    ax.set_title("Raw dataset: missing or null-like values per column")
    ax.set_xlabel("Missing (% of rows, empty cells + null tokens)")
    ax.set_ylabel("Column")
    fig.tight_layout(); fig.savefig(VIS / "01_raw_missing_by_column.png", dpi=120); plt.close(fig)

    tok = raw.apply(lambda s: s.str.strip().str.lower().isin(NULL_TOKENS))
    fig, ax = plt.subplots(figsize=(11, 6))
    sns.heatmap(tok.iloc[:600].T, cbar=False, cmap=["#f0f0f0", "#c44e52"], ax=ax)
    ax.set_title("Raw dataset: missing-value pattern (first 600 rows; red = missing)")
    ax.set_xlabel("Row position in raw export"); ax.set_ylabel("Column")
    ax.set_xticks([])
    fig.tight_layout(); fig.savefig(VIS / "02_raw_missing_matrix.png", dpi=120); plt.close(fig)


def main():
    raw = load_raw()
    ov = overview(raw)
    miss = missing_table(raw)
    dup, dup_examples = duplicate_summary(raw)
    patt, stats, outl = numeric_profile(raw)
    by_label = outliers_by_label(raw)
    dates = date_profile(raw)
    sep_tbl, tok = symptom_profile(raw)
    figures(raw, miss)

    L = ["# Data Quality Report — RAW pump dataset",
         "",
         "_Generated by `scripts/data_quality_analysis.py` from `data/raw/raw_pump_dataset.csv` only. "
         "The dataset is **synthetic** (see `dataset_description.md`)._",
         "",
         "## 1. Shape and columns",
         f"- Rows: **{len(raw):,}**  ·  Columns: **{raw.shape[1]}**",
         f"- Unexpected columns: {sorted(set(raw.columns) - set(COLUMNS)) or 'none'}; "
         f"missing expected columns: {sorted(set(COLUMNS) - set(raw.columns)) or 'none'}",
         "",
         "## 2. Data types",
         "`pandas_default_dtype` is what `pd.read_csv` infers with default settings. Numeric columns "
         "inferred as `object`/`str` contain non-numeric text (units, tokens, comma decimals).",
         "", md_table(ov), "",
         "## 3. Missing values",
         "**Caution:** in categorical columns some 'null-like' tokens are meaningful — `N/A`, `NA`, `-`, `0`, `none` "
         "in `Fault_Severity`/`Maintenance_Priority` mean *not applicable* (normal record), and `none`/`nil` in "
         "`Observed_Symptoms` mean *no abnormal symptoms*. They are variants, not missing data.",
         "",
         "Empty cells and null-like tokens (`N/A`, `--`, `ERR`, `?`, `null`, `sensor fault`, `#VALUE!`) are counted. "
         "**Structural missingness:** `Maintenance_Date`, `Downtime_Hours` and `Maintenance_Cost` are legitimately "
         "empty for records with no maintenance event (`Maintenance_Action = No action required`), so their "
         "high missing rates are expected and must not be imputed.",
         "", md_table(miss.sort_values("missing_%", ascending=False)), "",
         "![missing by column](../visualizations/01_raw_missing_by_column.png)",
         "![missing matrix](../visualizations/02_raw_missing_matrix.png)", "",
         f"- Records with no maintenance event: **{(raw.Maintenance_Action.str.lower().str.strip() == 'no action required').sum():,}**",
         "",
         "## 4. Duplicates",
         "", md_table(pd.DataFrame(list(dup.items()), columns=["check", "count"])), "",
         "Example partial duplicates (same pump and date after normalising ID/date formats):", "",
         md_table(dup_examples[["Record_ID", "Pump_ID", "Observation_Date", "Vibration_mm_s", "Fault_Type"]]), "",
         "## 5. Value formats in numeric columns",
         "", md_table(patt), "",
         "## 6. Statistical summary (values that parse as numbers only)",
         "", md_table(stats), "",
         "## 7. Outliers and implausible values",
         "IQR fences (1.5×IQR) and robust z-score (median/MAD, |z|>3.5) are computed on parseable values. "
         f"Because ~{100 * (1 - raw.Fault_Type.str.strip().str.lower().isin(['normal', 'ok', 'normal operation']).mean()):.0f}% "
         "of records are not labelled normal, many statistical outliers are expected to be "
         "**genuine abnormal operation**, not errors. Physically implausible values (outside the limits in "
         "`common.PLAUSIBLE`) are a different category: they cannot be real.",
         "", md_table(outl), "",
         "Outliers split by the (raw) fault label:", "", md_table(by_label), "",
         "Interpretation: for vibration, temperatures and pressure fluctuation almost all outliers sit in fault "
         "records, i.e. they are genuine abnormal operation. Pooled `Motor_Current` and `Motor_Speed_RPM` outliers "
         "in 'normal' records are an artefact of mixing pump sizes (rated current 20–250 A) and two synchronous "
         "speeds (≈1475 / ≈2950 rpm); scaling current by its pump's median removes almost all of them. Speed is "
         "nearly constant within a pump (±0.3%), so after scaling the IQR becomes so narrow that trivial "
         "deviations are flagged — IQR is not a meaningful test for near-constant signals; a ±5% band around "
         "rated speed is used instead in cleaning. The few "
         "remaining 'normal' outliers after scaling are the genuinely suspicious values (possible entry errors such "
         "as decimal shifts) and are flagged — not deleted — during cleaning.",
         "",
         "## 8. Date formats",
         "", md_table(dates), "",
         "`DD/MM/YYYY` is assumed (not `MM/DD`) — documented site convention; see cleaning report.", "",
         "## 9. Categorical inconsistencies",
    ]
    for c in CAT_COLS:
        L += [f"### {c}", "", md_table(category_variants(raw, c, top=40 if c == "Fault_Type" else 14)), ""]
    L += ["## 10. Free-text: Observed_Symptoms",
          "", md_table(sep_tbl), "",
          f"Distinct symptom tokens after naive splitting: **{tok.size}** (canonical vocabulary has 20 + 'no abnormal symptoms').",
          "", md_table(tok.head(40).rename_axis("token").reset_index(name="count")), "",
          "## 11. Key findings to address in cleaning",
          "1. Numeric columns stored as text because of unit suffixes (°F, psi, kPa, gpm, L/s, hrs, $), "
          "comma decimals, thousands separators and error tokens.",
          "2. Exact duplicate rows and re-keyed partial duplicates (same pump/date, different Record_ID).",
          "3. Five date formats across three date columns.",
          "4. Many spellings of the same category (case, punctuation, abbreviations, typos) — including "
          "fault labels and several ways of writing 'unknown'.",
          "5. Physically impossible sentinel values (999, 9999, negative pressure/flow, zero current/noise).",
          "6. Statistical outliers that are mostly explained by fault records and must be kept.",
          "7. Missing equipment attributes that are recoverable from the asset register (Pump_ID is a key).",
          "8. Missing diagnostic labels that are **not** recoverable and must not be guessed.",
          ]
    (REPORTS / "data_quality_report.md").write_text("\n".join(L), encoding="utf-8")
    print(f"Data quality report written: {len(raw)} rows, {raw.shape[1]} columns.")


if __name__ == "__main__":
    main()
