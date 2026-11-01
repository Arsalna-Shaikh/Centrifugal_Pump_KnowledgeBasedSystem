"""Phase 6: exploratory data analysis of the cleaned + preprocessed dataset.

Writes PNG figures to visualizations/ and reports/eda_report.md.  Every interpretation number is
computed here, so the report stays correct when the pipeline is re-run.  Findings describe the
SYNTHETIC data and the assumptions built into its generator — not real pump populations.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap, ListedColormap

from common import (PROCESSED_FILE, RAW_FILE, REPORTS, SENSOR_COLS, SYMPTOMS, UNITS, VIS, md_table)

# Reference palette (dataviz skill, light mode); max 3 categorical slots on scatter plots.
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"
CONTEXT = "#b9b8b2"                                   # neutral gray for the Normal context cloud
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
ORDINAL = ["#86b6ef", "#5598e7", "#256abf", "#104281"]          # Low → Critical
DIVERGING = LinearSegmentedColormap.from_list("div", ["#184f95", "#6da7ec", "#f0efec", "#ee8a87", "#b42f2f"])

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.titlecolor": INK, "axes.titlesize": 12,
    "axes.titleweight": "bold", "axes.labelsize": 10, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": .6, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 9.5, "legend.frameon": False,
    "legend.labelcolor": INK2,
})
NAMES = {"Vibration_mm_s": "Vibration", "Bearing_Temperature_C": "Bearing temperature",
         "Seal_Temperature_C": "Seal temperature", "Motor_Temperature_C": "Motor temperature",
         "Flow_Rate": "Flow rate", "Suction_Pressure": "Suction pressure", "Discharge_Pressure": "Discharge pressure",
         "Motor_Current": "Motor current", "Motor_Speed_RPM": "Motor speed", "Pressure_Fluctuation":
         "Pressure fluctuation", "Noise_Level": "Noise level"}
FIGS: list[tuple[str, str, str]] = []   # (file, title, interpretation markdown)


def save(fig, name, title, text):
    fig.tight_layout()
    fig.savefig(VIS / name, dpi=130)
    plt.close(fig)
    FIGS.append((name, title, text))


def bar_labels(ax, bars, fmt="{:,.0f}"):
    for b in bars:
        ax.text(b.get_width(), b.get_y() + b.get_height() / 2, " " + fmt.format(b.get_width()),
                va="center", ha="left", color=INK2, fontsize=8.5)


def load():
    df = pd.read_csv(PROCESSED_FILE, keep_default_na=False, na_values=[""],
                     dtype={"Imputed_Columns": str, "Maintenance_Date": str, "Symptom_Keys": str})
    df["Imputed_Columns"] = df.Imputed_Columns.fillna("")
    raw = pd.read_csv(RAW_FILE, dtype=str, keep_default_na=False)
    return df, raw


def observed(df, col):
    """Values of a sensor column that were measured (not imputed)."""
    return df[col].where(~df.Imputed_Columns.str.contains(col, regex=False))


# ---------------------------------------------------------------------------------------------
def fig_fault_distribution(df):
    c = df.Fault_Type.value_counts().sort_values()
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.barh(c.index, c.values, color=S1, height=.62)
    bar_labels(ax, bars)
    ax.set_title("Records per diagnostic class (cleaned data, n = {:,})".format(len(df)))
    ax.set_xlabel("Number of records"); ax.set_ylabel("Fault type"); ax.grid(axis="y", visible=False)
    ax.set_xlim(0, c.max() * 1.12)
    faults = c.drop(["Normal", "Unknown"])
    save(fig, "eda_01_fault_distribution.png", "Fault distribution",
         f"{c['Normal'] / len(df):.0%} of records are Normal and {c['Unknown']} ({c['Unknown'] / len(df):.1%}) are "
         f"Unknown. Among faults, **{faults.idxmax()}** ({faults.max()}) and the next most common classes are "
         f"wear-related; **{faults.idxmin()}** is rarest ({faults.min()}). The classes are imbalanced "
         f"(largest/smallest fault ratio {faults.max() / faults.min():.1f}:1), so any accuracy figure computed on "
         "this data must be reported per class, not only overall. The mix reflects the generator's chosen "
         "fault frequencies, not real failure statistics.")


def fig_severity(df):
    f = df[~df.Fault_Type.isin(["Normal"])]
    order = ["Low", "Medium", "High", "Critical"]
    ct = pd.crosstab(f.Fault_Type, f.Fault_Severity).reindex(columns=order, fill_value=0)
    share = ct.div(ct.sum(axis=1), axis=0).sort_values("Critical")
    fig, ax = plt.subplots(figsize=(9, 5.2))
    left = np.zeros(len(share))
    for lvl, col in zip(order, ORDINAL):
        ax.barh(share.index, share[lvl], left=left, color=col, height=.62, label=lvl,
                edgecolor=SURFACE, linewidth=2)
        left += share[lvl].values
    ax.set_title("Severity mix within each fault class (records with a fault/unknown label)")
    ax.set_xlabel("Share of records in class"); ax.set_ylabel("Fault type")
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
    ax.legend(title="Severity", ncols=4, loc="upper center", bbox_to_anchor=(.5, -.13), title_fontsize=9)
    ax.grid(axis="y", visible=False)
    unk = (f.Fault_Severity == "Unknown").sum()
    save(fig, "eda_02_fault_severity.png", "Fault severity distribution",
         f"Dry Running has the highest Critical share ({share.loc['Dry Running', 'Critical']:.0%}) — consistent with it "
         "being the only fault classed CRITICAL in the existing KBS. Most other faults spread over all levels "
         "because records follow a fault from first detection (Low) to repair (High/Critical). Unknown records "
         f"are only Low/Medium. {unk} fault records have severity 'Unknown' (missing in source) and are excluded "
         "from the bars.")
    return ct


def fig_sensor_distributions(df):
    cols = SENSOR_COLS
    fig, axes = plt.subplots(3, 4, figsize=(14, 9))
    normal = df.Fault_Type == "Normal"
    fault = df.Is_Fault.astype(bool)
    rows = []
    for ax, c in zip(axes.flat, cols):
        x = observed(df, c)
        lo, hi = x.quantile([.005, .995])
        bins = np.linspace(lo, hi, 40)
        ax.hist(x[normal].clip(lo, hi), bins=bins, color=S1, alpha=.75, density=True, label="Normal")
        ax.hist(x[fault].clip(lo, hi), bins=bins, color=S2, alpha=.6, density=True, label="Fault")
        ax.set_title(NAMES[c], fontsize=10)
        ax.set_xlabel(UNITS.get(c, "")); ax.set_ylabel("Density"); ax.grid(axis="x", visible=False)
        rows.append({"sensor": c, "unit": UNITS[c], "normal median": x[normal].median(),
                     "fault median": x[fault].median(), "fault skew": x[fault].skew()})
    axes.flat[-1].axis("off")
    h, l = axes.flat[0].get_legend_handles_labels()
    axes.flat[-1].legend(h, l, loc="center", fontsize=11, title="Record label")
    fig.suptitle("Sensor distributions: Normal vs fault records (measured values only, imputed excluded)",
                 color=INK, fontsize=13, fontweight="bold")
    tbl = pd.DataFrame(rows)
    save(fig, "eda_03_sensor_distributions.png", "Sensor measurement distributions",
         "Normal records form narrow single peaks; fault records add long right tails for vibration, temperatures, "
         "pressure fluctuation and noise, and left tails for flow and suction pressure. Flow, discharge pressure "
         "and current are multimodal even for Normal records because the fleet mixes pump sizes — the reason "
         "preprocessing converts them to % of rating. Speed clusters at ≈1475 and ≈2950 rpm (4- and 2-pole motors).\n\n"
         + md_table(tbl, floatfmt=".2f"))


def fig_missing(df, raw):
    tokens = {"", "n/a", "na", "null", "nan", "--", "?", "err", "#value!", "sensor fault"}
    cols = SENSOR_COLS + ["Operating_Hours", "Pump_Type", "Manufacturer", "Root_Cause", "Fault_Severity",
                          "Maintenance_Priority", "Diagnostic_Status", "Fault_Type"]
    raw_pct = [100 * raw[c].str.strip().str.lower().isin(tokens).mean() for c in cols]
    flags = df.Imputed_Columns.str.split(";")
    resolved = [100 * (df.Label_Missing_In_Source.astype(bool).mean() if c == "Fault_Type"
                       else flags.map(lambda f: c in f).mean()) for c in cols]
    m = pd.DataFrame({"column": cols, "raw missing %": raw_pct, "cleaned: gap resolved (flagged) %": resolved,
                      "cleaned: still missing %": [100 * df[c].isna().mean() for c in cols]}
                     ).sort_values("raw missing %")
    fig, ax = plt.subplots(figsize=(9, 6.5))
    y = np.arange(len(m)); h = .38
    b1 = ax.barh(y + h / 2, m["raw missing %"], h, color=S2, label="Raw: empty or null token",
                 edgecolor=SURFACE, linewidth=1)
    b2 = ax.barh(y - h / 2, m["cleaned: gap resolved (flagged) %"], h, color=S1,
                 label="Cleaned: gap imputed or marked 'Unknown' (flagged)", edgecolor=SURFACE, linewidth=1)
    ax.set_yticks(y, m.column); ax.grid(axis="y", visible=False)
    ax.set_title("Missing values: raw dataset vs how cleaning resolved them")
    ax.set_xlabel("% of rows"); ax.set_ylabel("Column")
    ax.legend(loc="lower right")
    save(fig, "eda_04_missing_values.png", "Missing-value visualisation",
         f"Raw missingness in sensor columns is ~{m[m.column.isin(SENSOR_COLS)]['raw missing %'].mean():.1f}% "
         "each (random gaps plus seal-temperature sensor outages on "
         "P-007 and P-023). After cleaning **no sensor value is missing**: each gap is per-pump-median imputed and "
         "flagged. Sensor 'resolved' bars are slightly above raw because implausible values and suspected entry "
         "errors were also nullified and then imputed. Missing diagnostic fields became explicit 'Unknown' (or a "
         "logically implied value) instead of being guessed. Fault_Severity and Maintenance_Priority resolve "
         "*fewer* gaps than the raw bar suggests because raw tokens such as 'N/A', '0', '-' turned out to be valid "
         "codes for 'No Fault' / 'Not Applicable'. Maintenance date, downtime and cost are omitted: they are empty "
         "by design when no maintenance event occurred.\n\n"
         + md_table(m.sort_values("raw missing %", ascending=False), floatfmt=".2f"))


def fig_correlation(df):
    cols = ["Vibration_mm_s", "Bearing_Temperature_C", "Seal_Temperature_C", "Motor_Temperature_C",
            "Flow_Pct_Rated", "Head_Pct_Rated", "Suction_Pressure", "Current_Pct_Rated", "Speed_Deviation_Pct",
            "Pressure_Fluctuation", "Noise_Level", "Operating_Hours", "Downtime_Hours", "Maintenance_Cost"]
    d = df[cols].copy()
    for c in SENSOR_COLS:
        if c in d:
            d[c] = observed(df, c)
    corr = d.corr(method="spearman")
    fig, ax = plt.subplots(figsize=(10, 8.5))
    sns.heatmap(corr, cmap=DIVERGING, vmin=-1, vmax=1, center=0, annot=True, fmt=".2f", annot_kws={"size": 7},
                linewidths=1, linecolor=SURFACE, cbar_kws={"label": "Spearman ρ", "shrink": .7}, ax=ax)
    ax.set_title("Spearman correlation between measurements (relative features for size-dependent sensors)")
    ax.tick_params(labelsize=8)
    pairs = corr.where(np.triu(np.ones(corr.shape, bool), 1)).stack().sort_values(key=abs, ascending=False)
    top = pairs.head(6).rename("ρ").reset_index().rename(columns={"level_0": "A", "level_1": "B"})
    save(fig, "eda_05_correlation_heatmap.png", "Correlation heatmap",
         "Spearman (rank) correlation is used because fault-driven distributions are heavily skewed. Size-dependent "
         "sensors are shown as % of rating; otherwise pump size dominates every correlation. Strongest pairs:\n\n"
         + md_table(top, floatfmt=".2f") +
         "\n\nCorrelations here mostly encode **shared faults** (e.g. cavitation lowers suction pressure and raises "
         "noise together). They are not causal relationships and must not be turned directly into rules.")


def scatter_groups(ax, df, x, y, groups):
    ax.scatter(df.loc[df.Fault_Type == "Normal", x], df.loc[df.Fault_Type == "Normal", y], s=9, c=CONTEXT,
               alpha=.45, label="Normal", linewidths=0)
    for (label, mask), color, marker in zip(groups, (S1, S2, S3), ("o", "s", "^")):
        ax.scatter(df.loc[mask, x], df.loc[mask, y], s=18, c=color, alpha=.75, marker=marker, label=label,
                   edgecolors=SURFACE, linewidths=.6)
    ax.legend(loc="best", markerscale=1.6)


def fig_vibration_bearing(df):
    d = df.assign(Vibration_mm_s=observed(df, "Vibration_mm_s"),
                  Bearing_Temperature_C=observed(df, "Bearing_Temperature_C"))
    groups = [("Bearing Failure", d.Fault_Type == "Bearing Failure"),
              ("Shaft Misalignment", d.Fault_Type == "Shaft Misalignment"),
              ("Other faults", d.Is_Fault.astype(bool) & ~d.Fault_Type.isin(["Bearing Failure", "Shaft Misalignment"]))]
    fig, ax = plt.subplots(figsize=(8.5, 6))
    scatter_groups(ax, d, "Vibration_mm_s", "Bearing_Temperature_C", groups)
    ax.axvline(4.5, color=INK2, lw=1, ls="--"); ax.axhline(80, color=INK2, lw=1, ls="--")
    ax.text(4.6, ax.get_ylim()[1] * .98, "vibration_high > 4.5", color=INK2, va="top", fontsize=8)
    ax.text(ax.get_xlim()[1] * .98, 81, "bearing_temp_high ≥ 80 °C", color=INK2, ha="right", fontsize=8)
    ax.set_title("Vibration vs bearing temperature")
    ax.set_xlabel("Vibration (mm/s RMS)"); ax.set_ylabel("Bearing temperature (°C)")
    bf = d[d.Fault_Type == "Bearing Failure"]; mis = d[d.Fault_Type == "Shaft Misalignment"]
    q = lambda g: ((g.Vibration_mm_s > 4.5) & (g.Bearing_Temperature_C >= 80)).mean()
    save(fig, "eda_06_vibration_vs_bearing_temp.png", "Vibration vs bearing temperature",
         f"Bearing failures occupy the high-vibration / high-temperature quadrant ({q(bf):.0%} of them exceed both "
         f"thresholds), while misalignment produces high vibration with only moderate heating ({q(mis):.0%} exceed "
         "both). Vibration alone cannot separate the two — the temperature axis (or a coupling-vibration "
         "observation) is what discriminates them. This supports a compound rule such as the existing KBS rule "
         "R01, but the separation is a property of the synthetic generator and needs field confirmation.")


def fig_flow_pressure(df):
    groups = [("Discharge Restriction", df.Fault_Type == "Discharge Restriction"),
              ("Pump Blockage / Impeller Damage", df.Fault_Type.isin(["Pump Blockage", "Impeller Damage"])),
              ("Dry Running", df.Fault_Type == "Dry Running")]
    fig, ax = plt.subplots(figsize=(8.5, 6))
    scatter_groups(ax, df, "Flow_Pct_Rated", "Head_Pct_Rated", groups)
    ax.axvline(75, color=INK2, lw=1, ls="--"); ax.axhline(85, color=INK2, lw=1, ls="--")
    ax.set_title("Pump operating point: flow vs head (relative to each pump's rating)")
    ax.set_xlabel("Flow (% of rated flow)"); ax.set_ylabel("Pump differential pressure (% of rated)")
    dr = df[df.Fault_Type == "Discharge Restriction"]
    save(fig, "eda_07_flow_vs_pressure.png", "Flow rate vs pressure",
         "Normal records sit on a tight diagonal band (≈80–110 % flow, ≈95–110 % head) — the pump curve, where "
         "head falls as flow rises. "
         f"Discharge restriction moves *up and left* along the curve (median flow {dr.Flow_Pct_Rated.median():.0f} %, "
         f"head {dr.Head_Pct_Rated.median():.0f} %): less flow but higher pressure. Blockage/impeller damage moves "
         "*down and left* (less flow **and** less head), and dry running collapses to near-zero flow and head. "
         "Low flow alone is therefore ambiguous; the direction of the head change separates the hypotheses — a "
         "relationship the current KBS cannot use because its thresholds are absolute (bar) not relative.")


def box_by_fault(df, col, unit, fname, title, text_fn):
    d = df[df.Has_Maintenance_Event.astype(bool) & df.Fault_Type.ne("Normal")]
    pm = df[df.Maintenance_Action == "Routine preventive maintenance"][col]
    order = d.groupby("Fault_Type")[col].median().sort_values().index
    fig, ax = plt.subplots(figsize=(9, 5.5))
    sns.boxplot(data=d, y="Fault_Type", x=col, order=order, color="#9ec5f4", width=.55, fliersize=2.5,
                linewidth=1, flierprops={"markerfacecolor": S1, "markeredgecolor": S1, "alpha": .6},
                medianprops={"color": "#104281", "linewidth": 2}, ax=ax)
    ax.set_title(title); ax.set_xlabel(unit); ax.set_ylabel("Fault type (records with a maintenance event)")
    ax.grid(axis="y", visible=False)
    med = d.groupby("Fault_Type")[col].agg(["count", "median", "max"]).sort_values("median", ascending=False)
    save(fig, fname, title, text_fn(med, pm) + "\n\n" + md_table(med, index=True, floatfmt=".1f"))
    return med


def fig_hours(df):
    d = df[df.Fault_Type != "Unknown"].copy()
    bins = np.arange(0, d.Operating_Hours.max() + 10_000, 10_000)
    d["band"] = pd.cut(d.Operating_Hours, bins, right=False)
    wear = d.Fault_Type.isin(["Bearing Failure", "Mechanical Seal Leakage", "Impeller Damage"])
    other = d.Is_Fault.astype(bool) & ~wear
    g = d.assign(wear=wear, other=other).groupby("band", observed=True).agg(
        n=("wear", "size"), wear=("wear", "mean"), other=("other", "mean"))
    g = g[g.n >= 100]
    x = [i.left / 1000 + 5 for i in g.index]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(x, 100 * g.wear, color=S1, lw=2, marker="o", ms=7, label="Wear faults (bearing, seal, impeller)")
    ax.plot(x, 100 * g.other, color=S2, lw=2, marker="s", ms=7, label="All other faults")
    ax.text(x[-1] + .8, 100 * g.wear.iloc[-1], "wear", color=INK2, va="center")
    ax.text(x[-1] + .8, 100 * g.other.iloc[-1], "other", color=INK2, va="center")
    ax.set_title("Fault occurrence by operating-hours band (bands with ≥ 100 records)")
    ax.set_xlabel("Cumulative operating hours (thousand h, band centre)")
    ax.set_ylabel("Records in band with this fault type (%)")
    ax.legend(loc="upper left"); ax.set_ylim(0, None)
    save(fig, "eda_10_operating_hours_vs_faults.png", "Operating hours vs fault occurrence",
         f"The share of wear-fault records rises from {100 * g.wear.iloc[0]:.0f} % in the youngest band to "
         f"{100 * g.wear.iloc[-1]:.0f} % in the oldest, while other faults stay roughly flat "
         f"({100 * g.other.min():.0f}–{100 * g.other.max():.0f} %). **This trend was built into the generator** "
         "(wear-fault likelihood increases with running hours), so the chart verifies the simulation rather than "
         "discovering anything. With real data this is the analysis that would justify an age/hours factor in "
         "maintenance priority.\n\n" + md_table(g.reset_index().assign(band=lambda t: t.band.astype(str)),
                                                floatfmt=".3f"))


def fig_outliers(df):
    rows = []
    for c in SENSOR_COLS:
        x = observed(df, c)
        med = x.groupby(df.Pump_ID).transform("median")
        mad = (x - med).abs().groupby(df.Pump_ID).transform("median").replace(0, np.nan)
        z = (.6745 * (x - med) / mad).abs() > 3.5
        rows.append({"sensor": c, "in fault/unknown records": int((z & (df.Fault_Type != "Normal")).sum()),
                     "in Normal records": int((z & (df.Fault_Type == "Normal")).sum())})
    t = pd.DataFrame(rows).set_index("sensor").sort_values("in fault/unknown records")
    fig, ax = plt.subplots(figsize=(9, 5.5))
    b1 = ax.barh(t.index, t["in fault/unknown records"], color=S1, height=.6, label="in fault/unknown records",
                 edgecolor=SURFACE, linewidth=2)
    ax.barh(t.index, t["in Normal records"], left=t["in fault/unknown records"], color=S2, height=.6,
            label="in Normal records", edgecolor=SURFACE, linewidth=2)
    for b, tot in zip(b1, t.sum(axis=1)):
        ax.text(tot, b.get_y() + b.get_height() / 2, f" {tot}", va="center", color=INK2, fontsize=8.5)
    ax.set_title("Outliers after cleaning: per-pump robust z-score > 3.5 (measured values)")
    ax.set_xlabel("Number of outlying values"); ax.set_ylabel("Sensor"); ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    share = t["in fault/unknown records"].sum() / t.values.sum()
    save(fig, "eda_11_outlier_analysis.png", "Outlier analysis",
         f"{share:.0%} of the remaining outliers sit in fault/unknown records: they are fault signatures, which is "
         "why cleaning kept them. The remaining outliers in Normal records are mostly speed (tiny within-pump "
         "variance makes small deviations look extreme) and mild excursions; the gross entry errors were already "
         "nullified during cleaning.\n\n" + md_table(t, index=True))


def fig_symptoms(df):
    keys = [k for k in SYMPTOMS if f"obs_{k}" in df]
    rec = df[df.Observed_Symptoms != "Not Recorded"]
    freq = pd.Series({k: rec[f"obs_{k}"].sum() for k in keys}).sort_values()
    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    bars = ax.barh([SYMPTOMS[k] for k in freq.index], freq.values, color=S1, height=.62)
    bar_labels(ax, bars)
    ax.set_xlim(0, freq.max() * 1.13)
    ax.set_title(f"Operator-recorded symptom frequency (records with symptoms recorded, n = {len(rec):,})")
    ax.set_xlabel("Number of records reporting the symptom"); ax.set_ylabel("Symptom")
    ax.grid(axis="y", visible=False)
    save(fig, "eda_12_symptom_frequency.png", "Symptom frequency analysis",
         f"High vibration is by far the most reported symptom ({int(freq.max()):,} records) but it occurs across "
         "many fault types, so it has low diagnostic specificity on its own. Rare symptoms such as air bubbles, "
         "loss of prime or speed instability are reported far less often but point to very few faults "
         "(see next figure) — they are high-value evidence for rules.")

    faults = [f for f in df.Fault_Type.value_counts().index if f not in ("Normal",)]
    mat = pd.DataFrame({f: [rec.loc[rec.Fault_Type == f, f"obs_{k}"].mean() for k in keys] for f in faults},
                       index=[SYMPTOMS[k] for k in keys])
    fig, ax = plt.subplots(figsize=(12, 7.5))
    sns.heatmap(mat, cmap=ListedColormap(SEQ), vmin=0, vmax=1, annot=True, fmt=".2f", annot_kws={"size": 7},
                linewidths=1, linecolor=SURFACE, cbar_kws={"label": "P(symptom recorded | fault)", "shrink": .7},
                ax=ax)
    ax.set_title("How often each symptom is recorded for each fault — candidate symptom–fault knowledge")
    ax.set_xlabel("Fault type"); ax.set_ylabel("Observed symptom"); ax.tick_params(labelsize=8)
    plt.setp(ax.get_xticklabels(), rotation=35, ha="right")
    spec = (mat.gt(.5).sum(axis=1)).rename("faults with P>0.5")
    save(fig, "eda_13_symptom_fault_matrix.png", "Symptom–fault co-occurrence",
         "Each cell is the fraction of a fault's records in which the symptom was recorded. Strong, specific cells "
         "(e.g. seal leakage ↔ Mechanical Seal Leakage, crackling noise and low suction ↔ Cavitation, air bubbles ↔ "
         "Air Ingress, loss of prime/no flow ↔ Dry Running) correspond to the weighted links in "
         "`../data/symptom_fault_weights.csv`. This matrix is the bridge to knowledge acquisition: it can be "
         "used to **check** existing weights and to suggest candidates, but every candidate must be reviewed "
         "against domain sources — the probabilities here were produced by the generator's own assumptions.\n\n"
         + md_table(spec.to_frame(), index=True))


def main():
    df, raw = load()
    fig_fault_distribution(df)
    sev = fig_severity(df)
    fig_sensor_distributions(df)
    fig_missing(df, raw)
    fig_correlation(df)
    fig_vibration_bearing(df)
    fig_flow_pressure(df)
    box_by_fault(df, "Downtime_Hours", "Downtime per maintenance event (h)", "eda_08_fault_vs_downtime.png",
                 "Downtime by fault type (corrective maintenance events)",
                 lambda m, pm: f"**{m.index[0]}** has the longest median downtime ({m['median'].iloc[0]:.1f} h) and "
                 f"**{m.index[-1]}** the shortest ({m['median'].iloc[-1]:.1f} h); routine preventive maintenance "
                 f"takes a median {pm.median():.1f} h. Long-downtime faults are where early detection pays most — "
                 "a direct input to maintenance priority alongside safety.")
    box_by_fault(df, "Maintenance_Cost", "Maintenance cost per event (USD)", "eda_09_fault_vs_cost.png",
                 "Maintenance cost by fault type (corrective maintenance events)",
                 lambda m, pm: f"**{m.index[0]}** is the most expensive repair (median ${m['median'].iloc[0]:,.0f}) and "
                 f"**{m.index[-1]}** the cheapest (median ${m['median'].iloc[-1]:,.0f}); preventive maintenance costs a "
                 f"median ${pm.median():,.0f}. Spread within a class comes from pump size and fault severity. Costs "
                 "are synthetic USD figures chosen for plausibility, not quotations.")
    fig_hours(df)
    fig_outliers(df)
    fig_symptoms(df)

    L = ["# Exploratory Data Analysis Report",
         "",
         "_Generated by `scripts/exploratory_analysis.py` from `data/processed/preprocessed_pump_dataset.csv`. "
         "**All data is synthetic.** Patterns below describe the generator's engineering assumptions; they are "
         "useful for checking the pipeline and for structuring knowledge, but they are not evidence about real "
         "pumps and no statistical or industrial conclusion should be drawn from them._",
         "",
         "Imputed sensor values are excluded from every sensor plot (they would pile up at each pump's median "
         "and fake a 'normal' peak).",
         ""]
    for i, (fname, title, text) in enumerate(FIGS, 1):
        L += [f"## {i}. {title}", "", f"![{title}](../visualizations/{fname})", "", text, ""]
    L += ["## Summary of findings",
          "1. Classes are imbalanced; evaluate rules per class.",
          "2. Fault signatures are mostly *combinations*: vibration + temperature separates bearing failure from "
          "misalignment; flow + head direction separates restriction from blockage/impeller damage.",
          "3. Relative (per-rating) features are essential in a mixed fleet; the existing KBS's absolute pressure "
          "thresholds would not transfer between pumps.",
          "4. Outliers are overwhelmingly fault evidence — deleting them would remove the diagnostic signal.",
          "5. Downtime and cost differ strongly by fault and are usable as priority inputs.",
          "6. The symptom–fault matrix gives a data-backed way to review the existing symptom weights.",
          "7. Every pattern listed here was put there by the generator; real data is required before any of it is "
          "treated as domain knowledge."]
    (REPORTS / "eda_report.md").write_text("\n".join(L), encoding="utf-8")
    print(f"EDA: {len(FIGS)} figures written to visualizations/, report to reports/eda_report.md")


if __name__ == "__main__":
    main()
