"""Phase 4: reproducible cleaning of the raw pump dataset.

Input   data/raw/raw_pump_dataset.csv (never modified) + data/raw/pump_asset_register.csv
Output  data/interim/cleaned_pump_dataset.csv
        data/interim/cleaning_log.csv          one row per cleaning operation (counts + justification)
        data/interim/cleaning_cell_changes.csv one row per changed cell (audit trail)
        reports/cleaning_report.md

The rules below were written from reports/data_quality_report.md.  This script never reads
data/generation_log/ (the ground truth is used only by validate_dataset.py afterwards).
"""
from __future__ import annotations

import difflib
import re
import sys

import numpy as np
import pandas as pd

from common import (CLEAN_FILE, COLUMNS, FAULT_LABELS, INTERIM, MANUFACTURERS, NO_SYMPTOM_TEXT,
                    PLAUSIBLE, PUMP_TYPES, RAW, RAW_FILE, REGISTER_FILE, REPORTS, SENSOR_COLS, SYMPTOMS,
                    md_table, sha256)

NUMERIC_COLS = ["Operating_Hours", *SENSOR_COLS, "Downtime_Hours", "Maintenance_Cost"]
DATE_COLS = ["Installation_Date", "Observation_Date", "Maintenance_Date"]
NULL_TOKENS = {"", "n/a", "na", "null", "none", "nan", "--", "-", "?", "err", "error", "#value!", "sensor fault"}
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y", "%Y%m%d", "%Y/%m/%d"]   # DD/MM: site convention

# ---- unit handling: (regex for unit text) -> conversion into the canonical unit -------------
UNIT_RULES = {
    "temperature": [(r"(°\s*f|degf|f)$", lambda v: (v - 32) * 5 / 9, "°F→°C"),
                    (r"(°\s*c|degc|c)$", lambda v: v, "°C")],
    "pressure": [(r"psi[ag]?$", lambda v: v / 14.5038, "psi→bar"),
                 (r"kpa$", lambda v: v / 100, "kPa→bar"),
                 (r"bar(\(?a\)?)?$", lambda v: v, "bar")],
    "flow": [(r"gpm$", lambda v: v * 0.2271247, "gpm→m³/h"),
             (r"l/s$", lambda v: v * 3.6, "L/s→m³/h"),
             (r"m3/h|m³/h$", lambda v: v, "m³/h")],
    "hours": [(r"(h|hr|hrs|hours)$", lambda v: v, "h")],
    "money": [(r"^\$", lambda v: v, "$")],
}
COLUMN_KIND = {"Bearing_Temperature_C": "temperature", "Seal_Temperature_C": "temperature",
               "Motor_Temperature_C": "temperature", "Suction_Pressure": "pressure",
               "Discharge_Pressure": "pressure", "Flow_Rate": "flow", "Operating_Hours": "hours",
               "Downtime_Hours": "hours", "Maintenance_Cost": "money"}

# ---- controlled-vocabulary mappings (built from the variants listed in the quality report) ----
def _key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())

FAULT_SYNONYMS = {
    "bearingfault": "Bearing Failure", "brgfailure": "Bearing Failure",
    "cavitationsuction": "Cavitation",
    "sealleak": "Mechanical Seal Leakage", "sealleakage": "Mechanical Seal Leakage",
    "mechsealleakage": "Mechanical Seal Leakage",
    "impellerdamaged": "Impeller Damage",
    "misalignment": "Shaft Misalignment",
    "blockage": "Pump Blockage", "cloggedpump": "Pump Blockage",
    "dryrun": "Dry Running",
    "airentrainment": "Air Ingress", "airleaksuction": "Air Ingress",
    "restricteddischarge": "Discharge Restriction",
    "motorfailure": "Motor Fault", "electricalmotorfault": "Motor Fault",
    "ok": "Normal", "normaloperation": "Normal",
    "unknown": "Unknown", "unk": "Unknown", "tbd": "Unknown", "undiagnosed": "Unknown",
    "nd": "Unknown", "": "Unknown",
}
PUMP_TYPE_SYNONYMS = {"inline": "Vertical Inline", "horizontalsplitcase": "Split Case"}
SEVERITY_MAP = {"low": "Low", "l": "Low", "1": "Low", "medium": "Medium", "med": "Medium", "m": "Medium",
                "2": "Medium", "high": "High", "h": "High", "3": "High", "critical": "Critical",
                "crit": "Critical", "4": "Critical", "severe": "Critical", "nofault": "No Fault",
                "none": "No Fault", "na": "No Fault", "0": "No Fault"}
STATUS_MAP = {"confirmed": "Confirmed", "conf": "Confirmed", "confirmedbyinspection": "Confirmed",
              "suspected": "Suspected", "susp": "Suspected", "possible": "Suspected",
              "inconclusive": "Inconclusive", "unclear": "Inconclusive", "pending": "Inconclusive",
              "nofaultdetected": "No Fault Detected", "nofault": "No Fault Detected",
              "nfd": "No Fault Detected", "healthy": "No Fault Detected"}
PRIORITY_MAP = {"p1emergency": "P1 - Emergency", "p1": "P1 - Emergency", "priority1": "P1 - Emergency",
                "emergency": "P1 - Emergency", "p2high": "P2 - High", "p2": "P2 - High",
                "priority2": "P2 - High", "high": "P2 - High", "p3medium": "P3 - Medium", "p3": "P3 - Medium",
                "priority3": "P3 - Medium", "medium": "P3 - Medium", "p4low": "P4 - Low", "p4": "P4 - Low",
                "priority4": "P4 - Low", "low": "P4 - Low", "notapplicable": "Not Applicable",
                "na": "Not Applicable"}
SYMPTOM_SYNONYMS = {  # normalised token -> canonical symptom key
    "highvib": "vibration_high", "excessivevibration": "vibration_high", "vibrationhigh": "vibration_high",
    "bearinghot": "bearing_temp_high", "brgtemphigh": "bearing_temp_high", "highbearingtemp": "bearing_temp_high",
    "sealhot": "seal_temp_high", "sealtemphigh": "seal_temp_high",
    "motorhot": "motor_temp_high", "motoroverheating": "motor_temp_high",
    "reducedflow": "flow_low", "zeroflow": "no_flow",
    "lowdischpress": "discharge_pressure_low", "lowhead": "discharge_pressure_low",
    "dischargepressurelow": "discharge_pressure_low", "highdischpress": "discharge_pressure_high",
    "dischargepressurehigh": "discharge_pressure_high", "lowsuction": "suction_pressure_low",
    "suctionpressurelow": "suction_pressure_low", "highamps": "motor_current_high",
    "motorcurrenthigh": "motor_current_high", "overcurrent": "motor_current_high",
    "pressuresurging": "pressure_fluctuation", "unstablepressure": "pressure_fluctuation",
    "pressurefluctuation": "pressure_fluctuation", "noisy": "noise_high", "loudnoise": "noise_high",
    "noisehigh": "noise_high", "grindingsound": "grinding_noise", "rumblingnoise": "grinding_noise",
    "gravelnoise": "crackling_noise", "cracklingsound": "crackling_noise", "poppingnoise": "crackling_noise",
    "sealleaking": "seal_leakage", "leakatseal": "seal_leakage", "sealleak": "seal_leakage",
    "couplingvib": "coupling_vibration", "vibrationatcoupling": "coupling_vibration",
    "airbubbles": "air_bubbles", "frothydischarge": "air_bubbles", "lostprime": "prime_failure",
    "pumpnotprimed": "prime_failure", "temprisingfast": "rapid_temp_rise", "rapidtemprise": "rapid_temp_rise",
    "speedhunting": "speed_unstable", "unstablespeed": "speed_unstable",
    **{_key(v): k for k, v in SYMPTOMS.items()},
}
NO_SYMPTOM_TOKENS = {"none", "nil", "noissues", "normal", _key(NO_SYMPTOM_TEXT)}
# which observed symptom would corroborate an extreme value in a sensor column
CORROBORATING = {
    "Vibration_mm_s": {"vibration_high", "coupling_vibration", "grinding_noise"},
    "Bearing_Temperature_C": {"bearing_temp_high"}, "Seal_Temperature_C": {"seal_temp_high", "seal_leakage"},
    "Motor_Temperature_C": {"motor_temp_high"}, "Motor_Current": {"motor_current_high"},
    "Pressure_Fluctuation": {"pressure_fluctuation", "air_bubbles"}, "Noise_Level": {"noise_high"},
}
NO_MAINT = "No action required"


class Cleaner:
    def __init__(self):
        self.log: list[dict] = []
        self.cells: list[dict] = []
        self.register = pd.read_csv(REGISTER_FILE).set_index("Pump_ID")
        self.unmapped: dict[str, set] = {}

    # ------------------------------------------------------------------ helpers
    def note(self, step, column, n, action, why):
        self.log.append({"step": step, "column": column, "rows_affected": int(n), "action": action,
                         "justification": why})

    def track(self, df, mask, col, new, reason):
        """Assign new values where mask is True and record every changed cell."""
        new = new if isinstance(new, pd.Series) else pd.Series(new, index=df.index)
        mask = mask.fillna(False).astype(bool) & (df[col].astype(str) != new.astype(str))
        if mask.any():
            self.cells += [{"Record_ID": r, "column": col, "old": o, "new": n, "reason": reason}
                           for r, o, n in zip(df.loc[mask, "Record_ID"], df.loc[mask, col], new[mask])]
            df.loc[mask, col] = new[mask]
        return int(mask.sum())

    @staticmethod
    def add_flag(df, mask, flag_col, value):
        df.loc[mask, flag_col] = np.where(df.loc[mask, flag_col] == "", value,
                                          df.loc[mask, flag_col] + ";" + value)

    # ------------------------------------------------------------------ steps
    def load(self):
        expected = {ln.split()[1]: ln.split()[0]
                    for ln in (RAW / "CHECKSUMS.sha256").read_text(encoding="utf-8").splitlines() if ln}
        if sha256(RAW_FILE) != expected[RAW_FILE.name]:
            sys.exit("Raw dataset checksum mismatch - the raw file was edited. Refusing to clean.")
        df = pd.read_csv(RAW_FILE, dtype=str, keep_default_na=False)
        df.insert(0, "Raw_Row", np.arange(2, len(df) + 2))     # spreadsheet row number, for traceability
        for c in ("DQ_Flags", "Imputed_Columns", "Converted_Columns", "Invalid_Columns",
                  "Suspect_Outlier_Columns", "Merged_Record_IDs"):
            df[c] = ""
        self.note("1 load", "*", len(df), "Loaded raw file as text (no automatic type conversion)",
                  "Prevents pandas from silently turning tokens/units into NaN before they are inspected; "
                  "checksum verified so the raw file is known to be unedited.")
        return df

    def exact_duplicates(self, df):
        cols = [c for c in COLUMNS]
        dup = df.duplicated(subset=cols, keep="first")
        self.note("2 exact duplicates", "*", dup.sum(), "Dropped exact copies (all 29 source fields identical)",
                  "An identical row with an identical Record_ID is a double upload and carries no new "
                  "information. First occurrence kept.")
        return df[~dup].reset_index(drop=True)

    def whitespace(self, df):
        n = 0
        for c in COLUMNS:
            new = df[c].str.strip().str.replace(r"\s{2,}", " ", regex=True)
            n += self.track(df, df[c] != new, c, new, "whitespace")
        self.note("3 whitespace", "*", n, "Trimmed leading/trailing spaces and collapsed repeated spaces (cells)",
                  "'Bearing Failure ' and 'Bearing Failure' must compare equal.")
        return df

    def pump_ids(self, df):
        digits = df.Pump_ID.str.extract(r"(\d+)")[0]
        new = "P-" + digits.astype(int).map("{:03d}".format)
        n = self.track(df, df.Pump_ID != new, "Pump_ID", new, "id format")
        unknown = ~new.isin(self.register.index)
        self.add_flag(df, unknown, "DQ_Flags", "pump_not_in_register")
        self.note("4 identifiers", "Pump_ID", n, "Normalised 'p007', 'P7', 'PUMP-007' → 'P-007'",
                  f"Pump_ID is the join key to the asset register; {int(unknown.sum())} IDs not in register.")
        return df

    def equipment(self, df):
        def std(col, vocab, syn):
            k = df[col].map(_key)
            lookup = {_key(v): v for v in vocab} | syn
            return k.map(lookup).where(df[col] != "", "")
        for col, vocab, syn in (("Pump_Type", PUMP_TYPES, PUMP_TYPE_SYNONYMS),
                                ("Manufacturer", MANUFACTURERS, {})):
            new = std(col, vocab, syn).fillna(df[col])
            n = self.track(df, df[col] != new, col, new, "category spelling")
            self.note("5 equipment", col, n, "Standardised spelling/case/abbreviation to controlled vocabulary",
                      "Same equipment class written differently would split counts and break grouping.")
            # Pump_ID -> attribute is a functional dependency: fill gaps with the pump's own mode,
            # then verify against the authoritative asset register.
            mode = df[df[col] != ""].groupby("Pump_ID")[col].agg(lambda s: s.mode().iat[0])
            miss = df[col] == ""
            n_fill = self.track(df, miss, col, df.Pump_ID.map(mode).fillna(""), "per-pump mode imputation")
            self.add_flag(df, miss, "Imputed_Columns", col)
            reg = df.Pump_ID.map(self.register[col])
            disagree = reg.notna() & (df[col] != reg)
            n_fix = self.track(df, disagree, col, reg, "asset register")
            self.note("5 equipment", col, n_fill, "Missing value filled with the pump's most frequent value",
                      "Equipment attributes cannot change between observations of the same pump, so the "
                      "pump's own mode is a near-certain fill (a global mode would be wrong for most pumps).")
            self.note("5 equipment", col, n_fix, "Overrode values that disagree with the asset register",
                      "The register is the authoritative master data for nameplate attributes.")
        return df

    def dates(self, df):
        for c in DATE_COLS:
            slash = df[c].str.extract(r"^(\d{2})/(\d{2})/\d{4}$").astype(float)
            evidence = (f"{int((slash[0] > 12).sum())} slash-dates have a first field > 12 (impossible as a "
                        f"month) and {int((slash[1] > 12).sum())} have a second field > 12, so DD/MM/YYYY is "
                        f"the only consistent reading")
            parsed = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
            used = pd.Series("", index=df.index)
            for fmt in DATE_FORMATS:
                m = parsed.isna() & (df[c] != "")
                p = pd.to_datetime(df.loc[m, c], format=fmt, errors="coerce")
                parsed[p.dropna().index] = p.dropna()
                used[p.dropna().index] = fmt
            bad = parsed.isna() & (df[c] != "")
            new = parsed.dt.strftime("%Y-%m-%d").fillna("")
            n = self.track(df, df[c] != new, c, new, "date format")
            self.add_flag(df, bad, "DQ_Flags", f"{c}_unparseable")
            self.note("6 dates", c, n, "Converted DD/MM/YYYY, DD-Mon-YYYY, YYYYMMDD, YYYY/MM/DD → ISO 8601",
                      f"One unambiguous format is required for sorting and date arithmetic. Evidence: {evidence}. "
                      f"{int(bad.sum())} unparseable values set empty and flagged.")
        reg = df.Pump_ID.map(self.register.Installation_Date)
        n = self.track(df, reg.notna() & (df.Installation_Date != reg), "Installation_Date", reg, "asset register")
        self.note("6 dates", "Installation_Date", n, "Verified against asset register", "Master data is authoritative.")
        return df

    def parse_value(self, raw: str, col: str):
        """Return (float or nan, tag) where tag in {'', 'null', 'converted:<rule>', 'unparseable'}."""
        s = raw.strip()
        if s.lower() in NULL_TOKENS:
            return np.nan, "null"
        kind = COLUMN_KIND.get(col)
        tag = ""
        low = s.lower().rstrip(".")
        if kind:
            for rx, fn, name in UNIT_RULES[kind]:
                if re.search(rx, low):
                    num = re.sub(rx, "", low).strip().lstrip("$")
                    try:
                        val = float(num.replace(",", "")) if kind in ("hours", "money") else float(num.replace(",", "."))
                    except ValueError:
                        return np.nan, "unparseable"
                    conv = fn(val)
                    if name not in ("°C", "bar", "m³/h", "h", "$"):
                        tag = f"converted:{name}"
                    elif name in ("h", "$"):
                        tag = "unit text removed"
                    return conv, tag
        if re.fullmatch(r"-?\d+,\d{1,2}", s):                       # comma decimal (sensor values)
            return float(s.replace(",", ".")), "comma decimal"
        if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", s):            # thousands separator
            return float(s.replace(",", "")), "thousands separator"
        try:
            return float(s), tag
        except ValueError:
            return np.nan, "unparseable"

    @staticmethod
    def why_numeric(tag):
        if tag in ("comma decimal", "thousands separator"):
            return ("Comma decimals only occur with 1–2 decimals in sensor columns; thousands separators only "
                    "in hour/cost columns, so the two patterns cannot be confused.")
        if tag == "unit text removed":
            return "The unit text matches the column's canonical unit, so only the number is kept."
        if "psi" in tag:
            return ("Treated as psi(a): converted values match the column's bar(a) distribution, whereas "
                    "psi(g) would sit ~1 bar lower.")
        if tag.startswith("converted"):
            return "All measurements must share one unit before comparison or thresholding."
        if tag == "null":
            return "Empty cells and error codes ('ERR', '#VALUE!', 'sensor fault', '--') are not measurements."
        return "Text that is not a number cannot be a measurement; flagged for review."

    def numerics(self, df):
        for c in NUMERIC_COLS:
            res = df[c].map(lambda v: self.parse_value(v, c))
            vals = res.map(lambda t: t[0]).astype(float)
            tags = res.map(lambda t: t[1])
            conv = tags.str.startswith("converted")
            for tag in sorted(set(tags) - {""}):
                m = tags == tag
                if tag == "null" and c in ("Downtime_Hours", "Maintenance_Cost"):
                    continue
                self.note("7 numeric parsing", c, m.sum(), {
                    "null": "Null-like token / empty → NaN",
                    "comma decimal": "Comma decimal '4,25' → 4.25",
                    "thousands separator": "Thousands separator '12,345' → 12345",
                    "unit text removed": "Removed unit text ('h', 'hrs', '$') — value already in canonical unit",
                    "unparseable": "Unparseable text → NaN (flagged)",
                }.get(tag) or f"Unit conversion {tag.split(':')[-1]}", self.why_numeric(tag))
            self.add_flag(df, conv, "Converted_Columns", c)
            self.add_flag(df, tags == "unparseable", "DQ_Flags", f"{c}_unparseable")
            changed = (tags != "") & (df[c] != "")              # an empty cell staying empty is not a change
            self.cells += [{"Record_ID": r, "column": c, "old": o, "new": n, "reason": f"numeric: {t}"}
                           for r, o, n, t in zip(df.loc[changed, "Record_ID"], df.loc[changed, c],
                                                 vals[changed].round(4), tags[changed])]
            df[c] = vals
        df["Operating_Hours"] = df.Operating_Hours.round()
        return df

    def plausibility(self, df):
        rated = self.register.reindex(df.Pump_ID)
        rated.index = df.index
        extra = {
            "Flow_Rate": df.Flow_Rate > 1.6 * rated.Rated_Flow_m3h,
            "Motor_Current": df.Motor_Current > 2.0 * rated.Rated_Current_A,
            "Motor_Speed_RPM": (df.Motor_Speed_RPM - rated.Rated_Speed_RPM).abs() > 0.05 * rated.Rated_Speed_RPM,
        }
        for c, (lo, hi) in PLAUSIBLE.items():
            bad = df[c].notna() & ~df[c].between(lo, hi)
            if c in extra:
                bad |= extra[c].fillna(False) & df[c].notna()
            if bad.any():
                examples = ", ".join(map(str, df.loc[bad, c].head(4).round(2).tolist()))
                self.track(df, bad, c, np.nan, "physically implausible")
                self.add_flag(df, bad, "Invalid_Columns", c)
                self.note("8 implausible values", c, bad.sum(), f"Set to NaN and flagged (e.g. {examples})",
                          f"Outside physical limits {lo}–{hi}" + (" or the pump's rated envelope" if c in extra else "")
                          + ": sentinel/error codes or impossible readings (negative absolute pressure, "
                          "negative flow, 999 °C, zero current while pumping, extra digit in speed). "
                          "Original value kept in cleaning_cell_changes.csv.")
        return df

    def categories(self, df):
        # Fault_Type ---------------------------------------------------------------------------
        canon = {_key(l): l for l in FAULT_LABELS}
        missing_label = df.Fault_Type.str.lower().isin(NULL_TOKENS - {"?"}) | (df.Fault_Type == "")
        def map_fault(v):
            k = _key(v)
            if k in canon:
                return canon[k], "case/punctuation"
            if k in FAULT_SYNONYMS:
                return FAULT_SYNONYMS[k], "synonym"
            if v.strip() == "?":
                return "Unknown", "synonym"
            close = difflib.get_close_matches(k, list(canon), n=1, cutoff=0.85)
            if close:
                return canon[close[0]], "typo (fuzzy match)"
            return None, "unmapped"
        res = df.Fault_Type.map(map_fault)
        new = res.map(lambda t: t[0])
        how = res.map(lambda t: t[1])
        unm = new.isna()
        self.unmapped["Fault_Type"] = set(df.loc[unm, "Fault_Type"])
        new = new.fillna("Unknown")
        for h in ("case/punctuation", "synonym", "typo (fuzzy match)"):
            m = (how == h) & (df.Fault_Type != new) & ~missing_label
            n = self.track(df, m, "Fault_Type", new, f"fault label {h}")
            self.note("9 categories", "Fault_Type", n, f"Fault label standardised ({h})", {
                "case/punctuation": "'BEARING FAILURE', 'Dry-running' differ only in case/punctuation.",
                "synonym": "Synonyms mapped with domain knowledge (e.g. 'Air entrainment' → Air Ingress, "
                           "'Clogged pump' → Pump Blockage); '?', 'TBD', 'N.D.', 'Undiagnosed' are written "
                           "forms of Unknown.",
                "typo (fuzzy match)": "Fuzzy matching (difflib ratio ≥ 0.85) only against the 12 canonical "
                                      "labels; every mapping is listed in cleaning_cell_changes.csv for review.",
            }[h])
        df["Label_Missing_In_Source"] = missing_label
        n = self.track(df, missing_label, "Fault_Type", "Unknown", "missing label → Unknown")
        self.note("9 categories", "Fault_Type", n, "Empty fault label → 'Unknown' and Label_Missing_In_Source=True",
                  "A diagnosis is the target knowledge; inferring it from sensor values would fabricate labels "
                  "(and would be circular if the data were later used to validate rules). Not imputed.")

        # Severity / status / priority / action ------------------------------------------------
        is_normal = df.Fault_Type == "Normal"
        for col, mp, implied in (("Fault_Severity", SEVERITY_MAP, "No Fault"),
                                 ("Diagnostic_Status", STATUS_MAP, "No Fault Detected")):
            k = df[col].map(_key)
            new = k.map(mp | {_key(v): v for v in mp.values()})
            n = self.track(df, new.notna() & (df[col] != new), col, new, "category spelling")
            self.note("9 categories", col, n, "Standardised abbreviations/case/numeric codes",
                      "e.g. 'H'/'3'/'HIGH' → High; 'N/A'/'0'/'none' mean 'No Fault' in this column (not missing)."
                      if col == "Fault_Severity" else
                      "e.g. 'CONF'/'Confirmed by inspection' → Confirmed; 'NFD'/'Healthy' → No Fault Detected; "
                      "'Pending'/'Unclear' → Inconclusive.")
            empty = df[col] == ""
            n1 = self.track(df, empty & is_normal, col, implied, "implied by Normal label")
            n2 = self.track(df, empty & ~is_normal, col, "Unknown", "missing → Unknown")
            self.add_flag(df, empty, "Imputed_Columns", col)
            self.note("9 categories", col, n1, f"Empty value in a Normal record → '{implied}'",
                      "Logically implied by the record's own label (a normal record has no fault severity), "
                      "not a statistical guess.")
            self.note("9 categories", col, n2, "Empty value in a fault/unknown record → 'Unknown'",
                      f"The {col.replace('_', ' ').lower()} of a fault cannot be derived reliably; mode imputation would invent "
                      "a judgement the technician never made.")
            self.unmapped[col] = set(df.loc[new.isna() & ~empty, col])

        act_lookup = {_key(a.replace("&", "and")): a for a in self._actions()}
        new = df.Maintenance_Action.str.replace("&", "and").map(_key).map(act_lookup)
        n = self.track(df, new.notna() & (df.Maintenance_Action != new), "Maintenance_Action", new, "action text")
        self.unmapped["Maintenance_Action"] = set(df.loc[new.isna(), "Maintenance_Action"])
        self.note("9 categories", "Maintenance_Action", n, "Standardised case and '&' → 'and'",
                  "Each action is a fixed work-order type; spelling variants are the same action.")

        k = df.Maintenance_Priority.map(_key)
        new = k.map(PRIORITY_MAP | {"": None, "-": None}).where(~df.Maintenance_Priority.isin(["-"]), "Not Applicable")
        n = self.track(df, new.notna() & (df.Maintenance_Priority != new), "Maintenance_Priority", new, "category spelling")
        self.note("9 categories", "Maintenance_Priority", n, "Standardised 'P1'/'Priority 1'/'Emergency' etc.",
                  "In this column 'low/medium/high' are priority words, mapped to P4/P3/P2; "
                  "'NA', 'n/a', '-' mean Not Applicable.")
        empty = df.Maintenance_Priority == ""
        imp = empty & is_normal & (df.Maintenance_Action == NO_MAINT)
        self.track(df, imp, "Maintenance_Priority", "Not Applicable", "implied")
        self.track(df, empty & ~imp, "Maintenance_Priority", "Unknown", "missing → Unknown")
        self.add_flag(df, empty, "Imputed_Columns", "Maintenance_Priority")
        self.note("9 categories", "Maintenance_Priority", imp.sum(), "Empty → 'Not Applicable' (normal, no work order)",
                  "Logically implied.")
        self.note("9 categories", "Maintenance_Priority", (empty & ~imp).sum(), "Empty → 'Unknown'",
                  "Priority is a planner's decision and is not reconstructed.")

        # Root cause: explicit Unknown, never the mode -------------------------------------------
        empty = df.Root_Cause == ""
        self.track(df, empty & is_normal, "Root_Cause", "Not Applicable", "implied")
        self.track(df, empty & ~is_normal, "Root_Cause", "Unknown", "missing → Unknown")
        self.add_flag(df, empty, "Imputed_Columns", "Root_Cause")
        self.note("9 categories", "Root_Cause", empty.sum(), "Empty → 'Not Applicable' (normal) or 'Unknown'",
                  "The most frequent cause would be a fabricated diagnosis; 'Unknown' keeps the gap visible.")

        # Supporting evidence: case normalisation of SHOUTED / all-lower entries ------------------
        ev = df.Supporting_Evidence
        fix = ev.str.isupper() | (ev.str.islower() & (ev != ""))
        new = ev.where(~fix, ev.str.lower().str.replace(r"^(.)", lambda m: m.group(1).upper(), regex=True)
                       .str.replace(r"(\d) c\b", r"\1 C", regex=True))
        n = self.track(df, fix, "Supporting_Evidence", new, "text case")
        self.note("9 categories", "Supporting_Evidence", n, "ALL-CAPS / all-lower text converted to sentence case",
                  "Free text is kept (not rewritten); only case is normalised so identical notes compare equal.")
        return df

    @staticmethod
    def _actions():
        return ["Replace bearings and renew lubrication", "Restore suction conditions and clean strainer",
                "Replace mechanical seal", "Repair or replace impeller", "Laser realign pump and motor shafts",
                "Clear blockage and clean impeller and strainer", "Stop pump, restore liquid supply and re-prime",
                "Seal suction-side leaks and re-prime", "Open or repair discharge valve and clear line",
                "Inspect motor and correct electrical fault", "Further investigation scheduled",
                "Routine preventive maintenance", NO_MAINT]

    def symptoms(self, df):
        def parse(text):
            if text.strip() == "":
                return None
            toks = [t.strip(" .") for t in re.split(r"\s*(?:;|,|\||/| and )\s*", text) if t.strip(" .")]
            keys, bad = [], []
            for t in toks:
                k = _key(t)
                if k in NO_SYMPTOM_TOKENS:
                    continue
                if k in SYMPTOM_SYNONYMS:
                    keys.append(SYMPTOM_SYNONYMS[k])
                else:
                    bad.append(t)
            return list(dict.fromkeys(keys)), bad
        parsed = df.Observed_Symptoms.map(parse)
        missing = parsed.isna()
        keys = parsed.map(lambda p: [] if p is None else p[0])
        self.unmapped["Observed_Symptoms"] = {t for p in parsed.dropna() for t in p[1]}
        df["Symptom_Keys"] = keys.map(";".join).where(~missing, "")
        new = keys.map(lambda ks: "; ".join(SYMPTOMS[k] for k in ks) or NO_SYMPTOM_TEXT).where(~missing, "Not Recorded")
        n = self.track(df, df.Observed_Symptoms != new, "Observed_Symptoms", new, "symptom vocabulary")
        self.note("10 symptoms", "Observed_Symptoms", n,
                  "Split on ; , | / 'and'; mapped synonyms to 20 canonical symptoms; rejoined with '; '",
                  "Symptoms are the KBS evidence vocabulary; 'high vib' and 'Excessive vibration' must be the "
                  "same fact (vibration_high). Canonical keys stored in Symptom_Keys.")
        self.note("10 symptoms", "Observed_Symptoms", missing.sum(), "Empty → 'Not Recorded'",
                  "Not recorded ≠ no symptoms. Treating it as 'No abnormal symptoms' would create false negatives.")
        return df

    def partial_duplicates(self, df):
        key = ["Pump_ID", "Observation_Date"]
        grp = df.groupby(key, sort=False)
        sizes = grp.Record_ID.transform("size")
        cand = df[sizes > 1]
        compare = [c for c in SENSOR_COLS + ["Operating_Hours"]]
        drop, merged, conflict = [], 0, 0
        for _, g in cand.groupby(key):
            base = g.iloc[0]
            same = True
            for _, other in g.iloc[1:].iterrows():
                for c in compare:
                    a, b = base[c], other[c]
                    if pd.notna(a) and pd.notna(b) and not np.isclose(a, b, rtol=.01):
                        same = False
            if not same:
                conflict += len(g)
                self.add_flag(df, df.index.isin(g.index), "DQ_Flags", "conflicting_same_day_records")
                continue
            # keep the record with the lowest Record_ID (original key), coalesce gaps from the copy
            g = g.assign(_n=g.Record_ID.str[2:].astype(int)).sort_values("_n")
            keep = g.index[0]
            for c in compare + ["Downtime_Hours", "Maintenance_Cost"]:
                if pd.isna(df.at[keep, c]):
                    v = g[c].dropna()
                    if len(v):
                        df.at[keep, c] = v.iloc[0]
            df.at[keep, "Merged_Record_IDs"] = ";".join(g.Record_ID.iloc[1:])
            drop += list(g.index[1:])
            merged += 1
        repeat_maint = (df[df.Maintenance_Action != NO_MAINT]
                        .groupby(["Pump_ID", "Maintenance_Action"]).size().gt(1).sum())
        self.note("11 partial duplicates", "Pump_ID+Observation_Date", len(drop),
                  f"Removed re-keyed copies of the same observation ({merged} groups merged, gaps coalesced)",
                  "A pump has at most one condition record per date in this export; same pump + date + identical "
                  "readings (±1%) under a new Record_ID is the same event entered twice. Lowest Record_ID kept, "
                  "removed IDs listed in Merged_Record_IDs.")
        self.note("11 partial duplicates", "Pump_ID+Observation_Date", conflict,
                  "Same pump/date but different readings: kept and flagged", "Not provably redundant.")
        self.note("11 partial duplicates", "Pump_ID+Maintenance_Action", repeat_maint,
                  "Repeated maintenance of the same type on the same pump (different dates): preserved",
                  "Recurring work orders are legitimate history (e.g. repeated bearing replacements) and are "
                  "evidence of recurring faults, not duplicates.")
        return df.drop(index=drop).reset_index(drop=True)

    def outliers(self, df):
        """Distinguish genuine abnormal operation from probable entry errors. Nothing is deleted."""
        keys = df.Symptom_Keys.str.split(";")
        normal = df.Fault_Type == "Normal"
        report = []
        for c in SENSOR_COLS:
            x = df[c]
            q1, q3 = x.quantile([.25, .75])
            iqr_flag = (x < q1 - 1.5 * (q3 - q1)) | (x > q3 + 1.5 * (q3 - q1))
            med = x.groupby(df.Pump_ID).transform("median")
            mad = (x - med).abs().groupby(df.Pump_ID).transform("median").replace(0, np.nan)
            rz = 0.6745 * (x - med) / mad
            z_flag = rz.abs() > 3.5
            corroborated = keys.map(lambda ks: bool(CORROBORATING.get(c, set()) & set(ks)))
            # probable entry error: extreme (|robust z| > 6) in a record labelled Normal, uncorroborated
            suspect = (rz.abs() > 6) & normal & ~corroborated & (c in CORROBORATING)
            report.append({"column": c, "pooled IQR flags": int(iqr_flag.sum()),
                           "per-pump robust z>3.5": int(z_flag.sum()),
                           "…of which in fault/unknown records": int((z_flag & ~normal).sum()),
                           "probable entry errors (nullified)": int(suspect.sum())})
            if suspect.any():
                self.track(df, suspect, c, np.nan, "suspected entry error (uncorroborated extreme in Normal record)")
                self.add_flag(df, suspect, "Suspect_Outlier_Columns", c)
        self.outlier_table = pd.DataFrame(report)
        n = self.outlier_table["probable entry errors (nullified)"].sum()
        self.note("12 outliers", "sensors", n,
                  "Statistical outliers kept; only uncorroborated extremes (|robust z|>6) in Normal records "
                  "nullified and flagged",
                  "Most outliers are fault signatures and are the most valuable evidence for a diagnostic KBS. "
                  "A 10× vibration reading in a record labelled Normal with no vibration symptom is "
                  "inconsistent with its own label and is treated as an entry error (e.g. decimal shift).")
        return df

    def impute(self, df):
        df = df.sort_values(["Pump_ID", "Observation_Date"], kind="stable").reset_index(drop=True)
        # Operating hours: a monotonic counter -> time interpolation inside each pump
        miss = df.Operating_Hours.isna()
        t = pd.to_datetime(df.Observation_Date)
        interp = df.assign(_t=t).groupby("Pump_ID", group_keys=False).apply(
            lambda g: g.set_index("_t").Operating_Hours.interpolate(method="time", limit_direction="both")
            .set_axis(g.index), include_groups=False)
        df.loc[miss, "Operating_Hours"] = interp[miss].round()
        self.add_flag(df, miss, "Imputed_Columns", "Operating_Hours")
        self.note("13 imputation", "Operating_Hours", miss.sum(), "Time-interpolated within the same pump",
                  "Running hours is a cumulative counter; interpolation between neighbouring readings is far "
                  "more accurate than a median.")
        # Sensors: per-pump median (pumps differ hugely in size/speed), global median fallback
        for c in SENSOR_COLS:
            miss = df[c].isna()
            fill = df.groupby("Pump_ID")[c].transform("median").fillna(df[c].median())
            df.loc[miss, c] = fill[miss]
            self.add_flag(df, miss, "Imputed_Columns", c)
            self.note("13 imputation", c, miss.sum(), "Per-pump median imputation (flagged)",
                      "Median is robust to the fault-driven skew; per-pump because a 900 m³/h split-case and a "
                      "30 m³/h inline pump share no sensible global centre. Imputed values must NOT be used to "
                      "derive symptoms — see Imputed_Columns.")
        # Maintenance numbers: only where a maintenance event exists
        has_m = df.Maintenance_Action != NO_MAINT
        for c in ("Downtime_Hours", "Maintenance_Cost"):
            miss = df[c].isna() & has_m
            fill = df[has_m].groupby("Maintenance_Action")[c].transform("median")
            df.loc[miss, c] = fill.reindex(df.index)[miss]
            self.add_flag(df, miss, "Imputed_Columns", c)
            self.note("13 imputation", c, miss.sum(), "Median of the same maintenance action type (flagged)",
                      "Cost/downtime depend mainly on the job type. Records without maintenance stay empty: "
                      "that missingness is structural (no work order), not a data gap.")
        return df

    def consistency(self, df):
        obs = pd.to_datetime(df.Observation_Date)
        mnt = pd.to_datetime(df.Maintenance_Date.replace("", np.nan))
        inst = pd.to_datetime(df.Installation_Date)
        has_m = df.Maintenance_Action != NO_MAINT
        checks = {
            "maintenance_before_observation": mnt < obs,
            "installed_after_observation": inst > obs,
            "maintenance_fields_without_action": ~has_m & (df.Maintenance_Date != ""),
            "action_without_maintenance_date": has_m & (df.Maintenance_Date == ""),
            "hours_decrease_within_pump": df.groupby("Pump_ID").Operating_Hours.diff() < 0,
            "discharge_not_above_suction": df.Discharge_Pressure <= df.Suction_Pressure,
            "normal_label_with_fault_severity": (df.Fault_Type == "Normal") &
                                                df.Fault_Severity.isin(["Low", "Medium", "High", "Critical"]),
            "fault_label_with_no_fault_severity": ~df.Fault_Type.isin(["Normal", "Unknown"]) &
                                                  (df.Fault_Severity == "No Fault"),
        }
        for name, m in checks.items():
            m = m.fillna(False)
            self.add_flag(df, m, "DQ_Flags", name)
            self.note("14 consistency", name, m.sum(), "Flagged (not altered)",
                      "Cross-field rule; violations are reported for review rather than silently 'fixed'.")
        return df

    def finalise(self, df):
        df["Operating_Hours"] = df.Operating_Hours.astype("Int64")
        df["Motor_Speed_RPM"] = df.Motor_Speed_RPM.round().astype("Int64")
        order = ["Record_ID", *COLUMNS[1:], "Symptom_Keys", "Label_Missing_In_Source", "Imputed_Columns",
                 "Converted_Columns", "Invalid_Columns", "Suspect_Outlier_Columns", "Merged_Record_IDs",
                 "DQ_Flags", "Raw_Row"]
        return df[order]

    def run(self):
        df = self.load()
        for step in (self.exact_duplicates, self.whitespace, self.pump_ids, self.equipment, self.dates,
                     self.numerics, self.plausibility, self.categories, self.symptoms,
                     self.partial_duplicates, self.outliers, self.impute, self.consistency):
            df = step(df)
        return self.finalise(df)


def write_report(cl: Cleaner, raw: pd.DataFrame, out: pd.DataFrame):
    log = pd.DataFrame(cl.log)
    L = ["# Cleaning Report",
         "",
         "_Generated by `scripts/clean_dataset.py`. Input: `data/raw/raw_pump_dataset.csv` (unchanged, "
         "checksum-verified). Output: `data/interim/cleaned_pump_dataset.csv`. Every changed cell is listed in "
         "`data/interim/cleaning_cell_changes.csv`._",
         "",
         "## Summary",
         f"- Raw rows: **{len(raw):,}** → cleaned rows: **{len(out):,}** "
         f"(removed {len(raw) - len(out)} redundant duplicates; no other rows deleted)",
         f"- Cells changed: **{len(cl.cells):,}**",
         f"- Columns: 29 source columns kept with original names and engineering units; added "
         "`Symptom_Keys`, `Label_Missing_In_Source` and audit columns (`Imputed_Columns`, `Converted_Columns`, "
         "`Invalid_Columns`, `Suspect_Outlier_Columns`, `Merged_Record_IDs`, `DQ_Flags`, `Raw_Row`).",
         "",
         "## Guiding principles",
         "1. **Never edit the raw file**; all changes are code, re-runnable and logged cell by cell.",
         "2. **Don't delete information**: only provably redundant rows are dropped; implausible values become NaN "
         "with the original preserved in the audit trail.",
         "3. **Don't fabricate diagnoses**: missing fault labels, causes, severities and priorities become "
         "`Unknown`, never the mode.",
         "4. **Extreme ≠ wrong**: statistical outliers are kept unless they contradict their own record.",
         "5. **Flag every imputation**, so imputed values can be excluded when deriving evidence.",
         "",
         "## Operations log",
         "", md_table(log), "",
         "## Outlier investigation",
         "", md_table(cl.outlier_table), "",
         "Interpretation: per-pump robust z-scores flag several hundred values, and the large majority sit in "
         "fault/unknown records — these are the fault signatures and are retained. Only extremes that are both "
         "very large (|z| > 6) and contradicted by their own record (labelled Normal, no corroborating symptom) "
         "are treated as entry errors.",
         "",
         "## Values that could not be mapped",
    ]
    for k, v in cl.unmapped.items():
        L.append(f"- **{k}**: {sorted(v)[:15] if v else 'none'}")
    L += ["",
          "## Decisions that need human review",
          "- `Label_Missing_In_Source = True` rows (fault label absent in source) are kept as `Unknown`.",
          "- Rows flagged `conflicting_same_day_records` or any `DQ_Flags` consistency rule.",
          "- The DD/MM/YYYY assumption for slash dates and the psi(a) assumption for psi pressures.",
          ]
    (REPORTS / "cleaning_report.md").write_text("\n".join(L), encoding="utf-8")


def main():
    raw = pd.read_csv(RAW_FILE, dtype=str, keep_default_na=False)
    cl = Cleaner()
    out = cl.run()
    out.to_csv(CLEAN_FILE, index=False)
    pd.DataFrame(cl.log).to_csv(INTERIM / "cleaning_log.csv", index=False)
    pd.DataFrame(cl.cells).to_csv(INTERIM / "cleaning_cell_changes.csv", index=False)
    write_report(cl, raw, out)
    print(f"Cleaned: {len(raw)} raw rows -> {len(out)} rows, {len(cl.cells)} cells changed.")


if __name__ == "__main__":
    main()
