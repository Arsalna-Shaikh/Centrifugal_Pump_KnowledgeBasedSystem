"""Validate the structured knowledge base in this folder.

Checks schemas, ID uniqueness and format, controlled vocabularies, references between files,
provenance/validation consistency, rule integrity, and coverage of the legacy KB (read-only).
Standard library only.  Usage (from the repository root or this folder):

    python knowledge_base/validate_kb.py

Writes VALIDATION_REPORT.md next to this file; exit code 1 if any error is found.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

KB = Path(__file__).resolve().parent
LEGACY = KB.parent / "data"

SCHEMAS = {
    "sources.csv": ["source_id", "source_type", "read_status", "title", "author_publisher", "year", "location", "notes"],
    "equipment.csv": ["equipment_id", "name", "boundary", "description", "legacy_ids"],
    "equipment_parameters.csv": ["parameter_id", "equipment_id", "name", "unit", "value_type", "allowed_values",
                                 "required", "role", "source_ids", "source_locator", "notes"],
    "components.csv": ["component_id", "name", "kind", "equipment_id", "legacy_ids", "description"],
    "indicators.csv": ["indicator_id", "name", "unit", "supported_bases", "rated_parameter_id",
                       "baseline_parameter_id", "description"],
    "thresholds.csv": ["threshold_id", "symptom_id", "indicator_id", "basis", "operator", "value", "value_parameter_id",
                       "unit", "default_for_basis", "support_level", "validation_status", "source_ids",
                       "source_locator", "replace_with", "notes"],
    "symptoms.csv": ["symptom_id", "key", "name", "kind", "legacy_ids", "description"],
    "faults.csv": ["fault_id", "name", "entity_type", "hazard_class", "hazard_support_level",
                   "hazard_validation_status", "hazard_source_ids", "hazard_source_locator", "cost_class",
                   "downtime_class", "cost_downtime_support_level", "cost_downtime_validation_status",
                   "cost_downtime_source_ids", "cost_downtime_source_locator", "legacy_ids", "description"],
    "root_causes.csv": ["cause_id", "name", "category", "legacy_ids", "description"],
    "diagnostic_tests.csv": ["test_id", "name", "measures", "result_values", "support_level", "validation_status",
                             "source_ids", "source_locator"],
    "maintenance_actions.csv": ["action_id", "name", "purpose", "competence", "opens_pump", "cost_class",
                                "downtime_class", "cost_downtime_support_level", "cost_downtime_validation_status",
                                "cost_downtime_source_ids", "cost_downtime_source_locator", "legacy_ids",
                                "description"],
    "safety_rules.csv": ["safety_id", "name", "trigger_fault_ids", "trigger_symptoms_all", "trigger_action_ids",
                         "trigger_min_status", "message", "support_level", "validation_status", "source_ids",
                         "source_locator", "legacy_ref"],
    "relationships.csv": ["rel_id", "rel_type", "from_id", "to_id", "qualifier", "support_level",
                          "validation_status", "source_ids", "source_locator", "legacy_ref", "legacy_weight", "notes"],
    "legacy_mapping.csv": ["legacy_id", "legacy_type", "legacy_location", "new_ids", "mapping", "notes"],
}
ID_PATTERNS = {
    "sources.csv": r"^(S|L|P)-\d{2}$", "equipment.csv": r"^EQ-\d{2}$", "equipment_parameters.csv": r"^PAR-\d{2}$",
    "components.csv": r"^(CMP|EXT)-\d{2}$", "indicators.csv": r"^IND-\d{2}$", "thresholds.csv": r"^THR-\d{2}$",
    "symptoms.csv": r"^SYM-\d{2}$", "faults.csv": r"^(FLT-\d{2}|OUT-[NU])$", "root_causes.csv": r"^CAU-\d{2}$",
    "diagnostic_tests.csv": r"^TST-\d{2}$", "maintenance_actions.csv": r"^ACT-\d{2}$",
    "safety_rules.csv": r"^SAF-\d{2}$", "relationships.csv": r"^(HC|MS|SR|FL|MA|IB|AA|CB|CL|LT|CF|RC|CO|PR)-\d{2}$",
}
REL_PREFIX = {"has_component": "HC", "measured_on": "MS", "implies": "SR", "excludes": "SR",
              "fault_located_in": "FL", "manifests_as": "MA", "indicated_by": "IB", "argues_against": "AA",
              "caused_by": "CB", "cause_located_at": "CL", "leads_to": "LT", "confirmed_by": "CF",
              "recommends": "RC", "corrects": "CO", "requires_precaution": "PR"}
SUPPORT_RANK = {"Unvalidated": 1, "Moderate": 2, "Strong": 3}
SUPPORT_TO_STATUS = {"Strong": "validated", "Moderate": "validated", "Unvalidated": "unvalidated",
                     "Disputed": "disputed", "Definitional": "not_applicable"}
STATUS_LEVELS = ["blocked", "unlikely", "pending", "possible", "likely", "confirmed"]


class Report:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.checks: Counter = Counter()

    def check(self, ok: bool, msg: str, warn: bool = False):
        self.checks["warning checks" if warn else "error checks"] += 1
        if not ok:
            (self.warnings if warn else self.errors).append(msg)


def read_csv(name, rep):
    path = KB / name
    if not path.exists():
        rep.check(False, f"{name}: file missing")
        return []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        rep.check(cols == SCHEMAS[name], f"{name}: columns {cols} != expected {SCHEMAS[name]}")
        rows = list(reader)
    for i, r in enumerate(rows, start=2):
        rep.check(None not in r and all(v is not None for v in r.values()),
                  f"{name}:{i}: wrong number of fields")
        for k in list(r):
            if r[k] is not None:
                r[k] = r[k].strip()
        r["_line"] = i
    return rows


def split(v):
    return [x.strip() for x in (v or "").split(";") if x.strip()]


def main():
    rep = Report()
    T = {name: read_csv(name, rep) for name in SCHEMAS}
    meta = json.loads((KB / "kb_meta.json").read_text(encoding="utf-8"))
    rules_doc = json.loads((KB / "diagnostic_rules.json").read_text(encoding="utf-8"))
    rules = rules_doc.get("rules", [])
    voc = meta["vocabularies"]

    # ---------------------------------------------------------------- IDs: format and uniqueness
    entity_files = [n for n in ID_PATTERNS]
    id_owner: dict[str, str] = {}
    for name in entity_files:
        key = SCHEMAS[name][0]
        ids = [r[key] for r in T[name]]
        for i, c in Counter(ids).items():
            rep.check(c == 1, f"{name}: duplicate id {i}")
        for r in T[name]:
            rep.check(bool(re.match(ID_PATTERNS[name], r[key])), f"{name}:{r['_line']}: bad id format '{r[key]}'")
            rep.check(r[key] not in id_owner or id_owner[r[key]] == name,
                      f"id {r[key]} used in both {id_owner.get(r[key])} and {name}")
            id_owner[r[key]] = name
    for r in rules:
        rep.check(r.get("rule_id") not in id_owner, f"rule id {r.get('rule_id')} collides with an entity id")
    for i, c in Counter(r.get("rule_id") for r in rules).items():
        rep.check(c == 1, f"diagnostic_rules.json: duplicate rule id {i}")

    ids = {name: {r[SCHEMAS[name][0]]: r for r in T[name]} for name in entity_files}
    src, eq, par = ids["sources.csv"], ids["equipment.csv"], ids["equipment_parameters.csv"]
    cmp_, ind, thr = ids["components.csv"], ids["indicators.csv"], ids["thresholds.csv"]
    sym, flt, cau = ids["symptoms.csv"], ids["faults.csv"], ids["root_causes.csv"]
    tst, act, saf, rel = (ids["diagnostic_tests.csv"], ids["maintenance_actions.csv"], ids["safety_rules.csv"],
                          ids["relationships.csv"])
    kind_of = {}
    for d, k in ((eq, "equipment"), (cmp_, "component"), (ind, "indicator"), (sym, "symptom"), (flt, "fault"),
                 (cau, "cause"), (tst, "test"), (act, "action"), (saf, "safety")):
        for i in d:
            kind_of[i] = k

    # ---------------------------------------------------------------- provenance helper
    def check_provenance(where, support, status, source_ids, locator):
        rep.check(support in SUPPORT_TO_STATUS, f"{where}: unknown support_level '{support}'")
        rep.check(status in voc["validation_status"], f"{where}: unknown validation_status '{status}'")
        rep.check(SUPPORT_TO_STATUS.get(support) == status,
                  f"{where}: support_level {support} inconsistent with validation_status {status}")
        sids = split(source_ids)
        rep.check(bool(sids), f"{where}: no source_ids (provenance required)")
        rep.check(bool(locator), f"{where}: no source_locator", warn=True)
        for s in sids:
            rep.check(s in src, f"{where}: unknown source {s}")
        read = [src[s] for s in sids if s in src and src[s]["read_status"] == "read"]
        if support == "Strong":
            rep.check(any(s["source_type"] == "independent" for s in read),
                      f"{where}: Strong requires a read independent source")
        if support == "Moderate":
            rep.check(any(s["source_type"] in ("manufacturer", "trade", "independent") for s in read),
                      f"{where}: Moderate requires a read manufacturer/trade source")
            rep.check(not any(s["source_type"] == "independent" for s in read),
                      f"{where}: Moderate but cites a read independent source (consider Strong)", warn=True)
        if support == "Disputed":
            rep.check(any(s["source_type"] == "independent" for s in read),
                      f"{where}: Disputed requires a read independent source")

    # ---------------------------------------------------------------- sources
    for s in T["sources.csv"]:
        rep.check(s["source_type"] in {"independent", "manufacturer", "trade", "peer_reviewed", "textbook", "project"},
                  f"sources.csv:{s['_line']}: bad source_type")
        rep.check(s["read_status"] in {"read", "scope_only", "not_read"}, f"sources.csv:{s['_line']}: bad read_status")

    # ---------------------------------------------------------------- equipment, parameters, components
    for p in T["equipment_parameters.csv"]:
        rep.check(p["equipment_id"] in eq, f"equipment_parameters.csv:{p['_line']}: unknown equipment")
        rep.check(p["value_type"] in {"enum", "number"}, f"equipment_parameters.csv:{p['_line']}: bad value_type")
        rep.check(p["value_type"] != "enum" or bool(split(p["allowed_values"])),
                  f"equipment_parameters.csv:{p['_line']}: enum without allowed_values")
        rep.check(p["required"] in {"yes", "optional"}, f"equipment_parameters.csv:{p['_line']}: bad required")
        rep.check(p["role"] in {"context", "rated_reference", "baseline_reference", "limit"},
                  f"equipment_parameters.csv:{p['_line']}: bad role")
        for s in split(p["source_ids"]):
            rep.check(s in src, f"equipment_parameters.csv:{p['_line']}: unknown source {s}")
    for c in T["components.csv"]:
        rep.check(c["equipment_id"] in eq, f"components.csv:{c['_line']}: unknown equipment")
        rep.check(c["kind"] in {"pump", "drive_train", "driver", "structure", "piping", "external"},
                  f"components.csv:{c['_line']}: bad kind")

    # ---------------------------------------------------------------- indicators and thresholds
    bases = set(voc["measurement_basis"])
    for i in T["indicators.csv"]:
        b = split(i["supported_bases"])
        rep.check(bool(b) and set(b) <= bases, f"indicators.csv:{i['_line']}: bad supported_bases {b}")
        if "pct_rated" in b:
            rep.check(par.get(i["rated_parameter_id"], {}).get("role") == "rated_reference",
                      f"indicators.csv:{i['_line']}: pct_rated needs a rated_reference parameter")
        if "pct_baseline" in b:
            rep.check(par.get(i["baseline_parameter_id"], {}).get("role") == "baseline_reference",
                      f"indicators.csv:{i['_line']}: pct_baseline needs a baseline_reference parameter")
    defaults = Counter()
    for t in T["thresholds.csv"]:
        w = f"thresholds.csv:{t['_line']} ({t['threshold_id']})"
        rep.check(t["symptom_id"] in sym, f"{w}: unknown symptom")
        rep.check(t["indicator_id"] in ind, f"{w}: unknown indicator")
        rep.check(t["basis"] in split(ind.get(t["indicator_id"], {}).get("supported_bases", "")),
                  f"{w}: basis {t['basis']} not supported by indicator")
        rep.check(t["operator"] in {"<", "<=", ">", ">="}, f"{w}: bad operator")
        if t["value"]:
            try:
                float(t["value"])
            except ValueError:
                rep.check(False, f"{w}: value not numeric")
        if t["value_parameter_id"]:
            rep.check(t["value_parameter_id"] in par, f"{w}: unknown value_parameter_id")
        rep.check(bool(t["value"]) or bool(t["value_parameter_id"]) or t["support_level"] == "Unvalidated",
                  f"{w}: threshold without value must be Unvalidated")
        rep.check(t["default_for_basis"] in {"yes", "no"}, f"{w}: bad default_for_basis")
        if t["default_for_basis"] == "yes":
            defaults[(t["symptom_id"], t["indicator_id"], t["basis"])] += 1
        check_provenance(w, t["support_level"], t["validation_status"], t["source_ids"], t["source_locator"])
        rep.check(t["support_level"] in {"Unvalidated", "Definitional"},
                  f"{w}: numeric thresholds were not validated in KA-2; expected Unvalidated")
    for k, n in defaults.items():
        rep.check(n == 1, f"thresholds.csv: {n} defaults for symptom/indicator/basis {k}")

    # ---------------------------------------------------------------- symptoms, faults, causes, tests, actions, safety
    for s in T["symptoms.csv"]:
        rep.check(s["kind"] in {"sensor", "observed", "trend"}, f"symptoms.csv:{s['_line']}: bad kind")
    for k, c in Counter(s["key"] for s in T["symptoms.csv"]).items():
        rep.check(c == 1, f"symptoms.csv: duplicate key {k}")
    for f in T["faults.csv"]:
        w = f"faults.csv:{f['_line']} ({f['fault_id']}) hazard"
        rep.check(f["entity_type"] in {"fault", "outcome"}, f"{w}: bad entity_type")
        rep.check(f["hazard_class"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL", "UNASSIGNED", "NONE"}, f"{w}: bad class")
        check_provenance(w, f["hazard_support_level"], f["hazard_validation_status"], f["hazard_source_ids"],
                         f["hazard_source_locator"])
    for t in T["diagnostic_tests.csv"]:
        w = f"diagnostic_tests.csv:{t['_line']} ({t['test_id']})"
        rep.check(bool(split(t["result_values"])), f"{w}: no result_values")
        check_provenance(w, t["support_level"], t["validation_status"], t["source_ids"], t["source_locator"])
    for a in T["maintenance_actions.csv"]:
        rep.check(a["purpose"] in {"investigate", "correct", "prevent", "make_safe"},
                  f"maintenance_actions.csv:{a['_line']}: bad purpose")
        rep.check(a["opens_pump"] in {"yes", "no"}, f"maintenance_actions.csv:{a['_line']}: bad opens_pump")
    # cost / downtime classes: vocabulary, provenance, and inherited values equal to the legacy KB (read-only)
    legacy_cost = {"faults.csv": ("fault_id", "repair_cost", "downtime"),
                   "maintenance_actions.csv": ("action_id", "cost", "downtime")}
    order = ["LOW", "MEDIUM", "HIGH"]
    for name, (key, lc, ld) in legacy_cost.items():
        lp = LEGACY / name
        leg = {}
        if lp.exists():
            with open(lp, encoding="utf-8", newline="") as f:
                leg = {r[key]: r for r in csv.DictReader(f)}
        for r in T[name]:
            w = f"{name}:{r['_line']} ({r[SCHEMAS[name][0]]}) cost/downtime"
            outcome = r.get("entity_type") == "outcome"
            for col in ("cost_class", "downtime_class"):
                rep.check(r[col] in voc["cost_downtime_class"], f"{w}: bad {col} '{r[col]}'")
                rep.check((r[col] == "NOT_APPLICABLE") == outcome, f"{w}: NOT_APPLICABLE only for outcomes")
            check_provenance(w, r["cost_downtime_support_level"], r["cost_downtime_validation_status"],
                             r["cost_downtime_source_ids"], r["cost_downtime_source_locator"])
            if outcome:
                continue
            rep.check(r["cost_downtime_support_level"] == "Unvalidated",
                      f"{w}: no read source gives cost/downtime - must be Unvalidated")
            lids = split(r["legacy_ids"])
            if not lids:
                rep.check(r["cost_class"] == r["downtime_class"] == "UNKNOWN",
                          f"{w}: no legacy record - value must be UNKNOWN (do not invent)")
            elif leg:
                rep.check("P-01" in split(r["cost_downtime_source_ids"]), f"{w}: inherited value must cite P-01")
                for col, lcol in (("cost_class", lc), ("downtime_class", ld)):
                    vals = sorted({leg[x][lcol].upper() for x in lids if x in leg}, key=order.index)
                    exp = (vals[0] if len(vals) == 1 else f"{vals[0]}-{vals[-1]}") if vals else "UNKNOWN"
                    rep.check(r[col] == exp, f"{w}: {col} '{r[col]}' differs from legacy value(s) '{exp}'")
    pol = meta["policies"]
    rep.check(set(voc.get("maintenance_priority", {})) and pol.get("maintenance_priority", {}).get("support_level")
              in SUPPORT_TO_STATUS, "kb_meta.json: maintenance_priority vocabulary/policy missing")
    for s in T["safety_rules.csv"]:
        w = f"safety_rules.csv:{s['_line']} ({s['safety_id']})"
        trig = split(s["trigger_fault_ids"]) + split(s["trigger_symptoms_all"]) + split(s["trigger_action_ids"])
        rep.check(bool(trig), f"{w}: no trigger")
        for x in split(s["trigger_fault_ids"]):
            rep.check(x in flt, f"{w}: unknown fault {x}")
        for x in split(s["trigger_symptoms_all"]):
            rep.check(x in sym, f"{w}: unknown symptom {x}")
        for x in split(s["trigger_action_ids"]):
            rep.check(x in act, f"{w}: unknown action {x}")
        if split(s["trigger_fault_ids"]):
            rep.check(s["trigger_min_status"] in STATUS_LEVELS, f"{w}: bad trigger_min_status")
        check_provenance(w, s["support_level"], s["validation_status"], s["source_ids"], s["source_locator"])

    # ---------------------------------------------------------------- relationships
    allowed = voc["relationship_types"]
    pump_designs = split(par.get("PAR-01", {}).get("allowed_values", ""))
    for r in T["relationships.csv"]:
        w = f"relationships.csv:{r['_line']} ({r['rel_id']})"
        rt = r["rel_type"]
        rep.check(rt in allowed, f"{w}: unknown rel_type {rt}")
        if rt not in allowed:
            continue
        rep.check(r["rel_id"].startswith(REL_PREFIX[rt] + "-"), f"{w}: id prefix does not match type {rt}")
        dom, rng = allowed[rt]
        rep.check(kind_of.get(r["from_id"]) in dom.split("|"),
                  f"{w}: from_id {r['from_id']} is {kind_of.get(r['from_id'])}, expected {dom}")
        rep.check(kind_of.get(r["to_id"]) in rng.split("|"),
                  f"{w}: to_id {r['to_id']} is {kind_of.get(r['to_id'])}, expected {rng}")
        rep.check(r["from_id"] != r["to_id"], f"{w}: self relationship")
        q = r["qualifier"]
        if q:
            m = re.match(r"^(role|result|sequence|pump_design)=(.+)$", q)
            rep.check(bool(m), f"{w}: bad qualifier '{q}'")
            if m and m.group(1) == "result":
                rep.check(m.group(2) in split(tst.get(r["to_id"], {}).get("result_values", "")),
                          f"{w}: result '{m.group(2)}' not a result of {r['to_id']}")
            if m and m.group(1) == "pump_design":
                rep.check(m.group(2) in pump_designs, f"{w}: pump_design '{m.group(2)}' not allowed")
            if m and m.group(1) == "role":
                rep.check(m.group(2) in {"origin", "damage"}, f"{w}: bad role")
        rep.check(rt != "confirmed_by" or q.startswith("result="), f"{w}: confirmed_by needs result= qualifier")
        if r["legacy_weight"]:
            rep.check(r["legacy_weight"].isdigit() and 1 <= int(r["legacy_weight"]) <= 5, f"{w}: bad legacy_weight")
        check_provenance(w, r["support_level"], r["validation_status"], r["source_ids"], r["source_locator"])
    rel_keys = Counter((r["rel_type"], r["from_id"], r["to_id"], r["qualifier"]) for r in T["relationships.csv"])
    for k, c in rel_keys.items():
        rep.check(c == 1, f"relationships.csv: duplicate relationship {k}")

    # ---------------------------------------------------------------- rules
    cond_keys = {"symptoms_all", "symptoms_any", "symptoms_absent", "tests", "faults_all", "faults_any",
                 "faults_count", "context"}
    for r in rules:
        rid = r.get("rule_id", "?")
        w = f"diagnostic_rules.json {rid}"
        for k in ("rule_id", "layer", "legacy_ids", "conditions", "conclusion", "support_level", "validation_status",
                  "relationship_ids", "source_ids", "assumptions", "explanation"):
            rep.check(k in r, f"{w}: missing key {k}")
        rep.check(bool(re.match(r"^(R-[A-Z]+-\d+|R-[A-Z]-\d{2}|N-\d{2})$", rid)), f"{w}: bad rule id format")
        rep.check(r.get("layer") in voc["rule_layers"], f"{w}: bad layer")
        c = r.get("conditions", {})
        rep.check(set(c) <= cond_keys, f"{w}: unknown condition keys {set(c) - cond_keys}")
        rep.check(bool(c), f"{w}: no conditions")
        for k in ("symptoms_all", "symptoms_any", "symptoms_absent"):
            for s in c.get(k, []):
                rep.check(s in sym, f"{w}: unknown symptom {s}")
        rep.check(not (set(c.get("symptoms_all", [])) & set(c.get("symptoms_absent", []))),
                  f"{w}: symptom both required and absent")
        for t in c.get("tests", []):
            rep.check(t.get("test_id") in tst, f"{w}: unknown test {t.get('test_id')}")
            rep.check(t.get("result") in split(tst.get(t.get("test_id"), {}).get("result_values", "")),
                      f"{w}: invalid result {t.get('result')} for {t.get('test_id')}")
        for k in ("faults_all", "faults_any"):
            for f in c.get(k, []):
                rep.check(f.get("fault_id") in flt, f"{w}: unknown fault {f.get('fault_id')}")
                rep.check(f.get("min_status") in STATUS_LEVELS, f"{w}: bad min_status")
        if "faults_count" in c:
            fc = c["faults_count"]
            rep.check(all(x in flt for x in fc.get("fault_ids", [])), f"{w}: faults_count unknown fault")
            rep.check(isinstance(fc.get("min"), int) and 1 <= fc["min"] <= len(fc.get("fault_ids", [])),
                      f"{w}: faults_count bad min")
        for p, v in c.get("context", {}).items():
            rep.check(p in par, f"{w}: unknown context parameter {p}")
            rep.check(v in split(par.get(p, {}).get("allowed_values", "")), f"{w}: context value {v} not allowed")
        con = r.get("conclusion", {})
        ctype, targets, like = con.get("type"), con.get("targets", []), con.get("likelihood")
        expected = {"fault": "fault", "cause": "cause", "lower": "fault", "block": "fault",
                    "request_tests": "test", "chain": "rel"}
        rep.check(ctype in expected, f"{w}: bad conclusion type {ctype}")
        rep.check(bool(targets), f"{w}: no conclusion targets")
        for t in targets:
            if expected.get(ctype) == "rel":
                rep.check(rel.get(t, {}).get("rel_type") == "leads_to", f"{w}: chain target {t} not a leads_to")
            else:
                rep.check(kind_of.get(t) == expected.get(ctype), f"{w}: target {t} is not a {expected.get(ctype)}")
        rep.check(like in voc["likelihood"], f"{w}: bad likelihood {like}")
        if ctype in ("lower", "block", "request_tests"):
            rep.check(like == "not_applicable", f"{w}: {ctype} rules must use likelihood not_applicable")
        else:
            rep.check(like != "not_applicable", f"{w}: hypothesis rules need a likelihood")
        if like == "confirmed":
            rep.check(bool(c.get("tests")) or any(f.get("min_status") == "confirmed" for f in c.get("faults_all", [])),
                      f"{w}: 'confirmed' requires a test result or a confirmed fault condition")
        sup = r.get("support_level")
        rep.check(SUPPORT_TO_STATUS.get(sup) == r.get("validation_status"),
                  f"{w}: support_level {sup} inconsistent with validation_status {r.get('validation_status')}")
        for s in r.get("source_ids", []):
            rep.check(s in src, f"{w}: unknown source {s}")
        used = []
        for x in r.get("relationship_ids", []):
            rep.check(x in rel, f"{w}: unknown relationship {x}")
            if x in rel:
                used.append(rel[x])
                rep.check(rel[x]["support_level"] != "Disputed", f"{w}: uses disputed relationship {x}")
        ranks = [SUPPORT_RANK[u["support_level"]] for u in used if u["support_level"] in SUPPORT_RANK]
        if sup in SUPPORT_RANK and ranks:
            rep.check(SUPPORT_RANK[sup] <= min(ranks),
                      f"{w}: support {sup} stronger than its weakest relationship")
        if sup in SUPPORT_RANK:
            rep.check(bool(ranks), f"{w}: evidence-based support but no evidence relationships")
        for a in r.get("assumptions", []):
            rep.check(isinstance(a, dict) and a.get("type") in voc["assumption_types"],
                      f"{w}: assumption must be an object with a known type")
            if isinstance(a, dict) and a.get("type") == "discriminator" and a.get("validation_status") == "unvalidated":
                rep.check(sup == "Unvalidated", f"{w}: unvalidated discriminator requires Unvalidated support")
        if ctype == "fault":
            for s in c.get("symptoms_all", []) + c.get("symptoms_any", []):
                linked = any(u["rel_type"] == "manifests_as" and u["from_id"] in targets and u["to_id"] == s
                             for u in used)
                rep.check(linked, f"{w}: symptom {s} not backed by a listed manifests_as relationship", warn=True)
        if ctype == "lower":
            for t in targets:
                rep.check(any(u["rel_type"] == "argues_against" and u["to_id"] == t for u in used),
                          f"{w}: lowering {t} not backed by an argues_against relationship")
        if ctype == "cause":
            for t in targets:
                rep.check(any(u["rel_type"] == "caused_by" and u["to_id"] == t for u in used),
                          f"{w}: cause {t} not backed by a caused_by relationship", warn=True)

    # ---------------------------------------------------------------- legacy coverage (read-only)
    mapped = {m["legacy_id"]: m for m in T["legacy_mapping.csv"]}
    all_ids = set(id_owner) | {r.get("rule_id") for r in rules}
    for m in T["legacy_mapping.csv"]:
        for n in split(m["new_ids"]):
            rep.check(n in all_ids, f"legacy_mapping.csv:{m['_line']}: unknown new id {n}")
        rep.check(bool(split(m["new_ids"])) or m["mapping"] == "retired",
                  f"legacy_mapping.csv:{m['_line']}: no new id and not retired")
    legacy_files = {"components.csv": "component_id", "symptoms.csv": "symptom_id", "faults.csv": "fault_id",
                    "maintenance_actions.csv": "action_id"}
    legacy_seen = 0
    for fname, key in legacy_files.items():
        p = LEGACY / fname
        if p.exists():
            with open(p, encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    legacy_seen += 1
                    rep.check(row[key] in mapped, f"legacy {fname} id {row[key]} not in legacy_mapping.csv")
    rp = LEGACY / "rules.json"
    if rp.exists():
        for lr in json.loads(rp.read_text(encoding="utf-8")):
            legacy_seen += 1
            rep.check(lr["id"] in mapped, f"legacy rule {lr['id']} not in legacy_mapping.csv")
    # weights: every legacy line referenced by a relationship (or retired), and mapped consistently
    wp = LEGACY / "symptom_fault_weights.csv"
    legacy_sym = {}
    sp = LEGACY / "symptoms.csv"
    if sp.exists():
        with open(sp, encoding="utf-8", newline="") as f:
            legacy_sym = {r["key"]: r["symptom_id"] for r in csv.DictReader(f)}
    by_ref = defaultdict(list)
    for r in T["relationships.csv"]:
        for ref in split(r["legacy_ref"]):
            if ref.startswith("weights:"):
                by_ref[int(ref.split(":")[1])].append(r)
    if wp.exists():
        with open(wp, encoding="utf-8", newline="") as f:
            for line, row in enumerate(csv.DictReader(f), start=2):
                legacy_seen += 1
                refs = by_ref.get(line, [])
                retired = f"W-{line}" in mapped
                rep.check(bool(refs) or retired, f"legacy weight line {line} ({row['fault_id']}->{row['symptom_key']}) "
                                                 f"not mapped")
                for r in refs:
                    exp_from = split(mapped.get(row["fault_id"], {}).get("new_ids", ""))
                    exp_to = split(mapped.get(legacy_sym.get(row["symptom_key"], ""), {}).get("new_ids", ""))
                    rep.check(r["from_id"] in exp_from and r["to_id"] in exp_to,
                              f"{r['rel_id']}: legacy weights:{line} is {row['fault_id']}->{row['symptom_key']} "
                              f"but maps to {r['from_id']}->{r['to_id']}")
                    rep.check(r["legacy_weight"] == row["weight"], f"{r['rel_id']}: legacy_weight mismatch")

    # ---------------------------------------------------------------- orphans (warnings)
    rel_from = Counter((r["rel_type"], r["from_id"]) for r in T["relationships.csv"])
    rel_to = Counter((r["rel_type"], r["to_id"]) for r in T["relationships.csv"])
    rule_refs = set()
    for r in rules:
        c = r.get("conditions", {})
        rule_refs |= set(c.get("symptoms_all", []) + c.get("symptoms_any", []) + c.get("symptoms_absent", []))
        rule_refs |= {t["test_id"] for t in c.get("tests", [])} | set(r.get("conclusion", {}).get("targets", []))
    for f in T["faults.csv"]:
        if f["entity_type"] == "fault":
            rep.check(rel_from[("manifests_as", f["fault_id"])] > 0, f"fault {f['fault_id']} has no symptoms", warn=True)
            rep.check(rel_from[("caused_by", f["fault_id"])] > 0, f"fault {f['fault_id']} has no causes", warn=True)
            rep.check(rel_from[("recommends", f["fault_id"])] > 0, f"fault {f['fault_id']} has no action", warn=True)
            rep.check(f["fault_id"] in rule_refs, f"fault {f['fault_id']} is not concluded by any rule", warn=True)
    for c in T["root_causes.csv"]:
        rep.check(rel_to[("caused_by", c["cause_id"])] > 0, f"cause {c['cause_id']} not linked to a fault")
    for s in T["symptoms.csv"]:
        if s["kind"] == "sensor":
            rep.check(any(t["symptom_id"] == s["symptom_id"] for t in T["thresholds.csv"]),
                      f"sensor symptom {s['symptom_id']} has no threshold")
        rep.check(s["symptom_id"] in rule_refs or rel_to[("manifests_as", s["symptom_id"])] > 0,
                  f"symptom {s['symptom_id']} unused", warn=True)
    for a in T["maintenance_actions.csv"]:
        rep.check(rel_to[("recommends", a["action_id"])] + rel_from[("corrects", a["action_id"])] > 0,
                  f"action {a['action_id']} not used by any relationship", warn=True)
    cited = set()
    for name in SCHEMAS:
        for row in T[name]:
            for col in ("source_ids", "hazard_source_ids", "cost_downtime_source_ids"):
                cited |= set(split(row.get(col, "")))
    for r in rules:
        cited |= set(r.get("source_ids", []))
    for s in T["sources.csv"]:
        rep.check(s["source_id"] in cited or s["read_status"] != "read", f"source {s['source_id']} never cited",
                  warn=True)

    # ---------------------------------------------------------------- report
    support_counts = Counter(r["support_level"] for r in T["relationships.csv"])
    type_counts = Counter(r["rel_type"] for r in T["relationships.csv"])
    rule_support = Counter(r.get("support_level") for r in rules)
    L = ["# Knowledge Base Validation Report", "",
         f"Generated by `knowledge_base/validate_kb.py`. Result: **{'PASS' if not rep.errors else 'FAIL'}** - "
         f"{len(rep.errors)} errors, {len(rep.warnings)} warnings, "
         f"{rep.checks['error checks']} error checks and {rep.checks['warning checks']} warning checks run.", "",
         "## Entity counts", "", "| File | Records |", "|---|---|"]
    L += [f"| {n} | {len(T[n])} |" for n in SCHEMAS] + [f"| diagnostic_rules.json | {len(rules)} |", ""]
    L += ["## Relationships by type", "", "| Type | Count |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in sorted(type_counts.items())] + [""]
    L += ["## Support level of relationships", "", "| Support | Count |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in sorted(support_counts.items())] + [""]
    L += ["## Support level of rules", "", "| Support | Count |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in sorted(rule_support.items())] + [""]
    L += [f"Legacy records cross-checked (read-only, `data/`): {legacy_seen}", ""]
    L += ["## Errors", ""] + ([f"- {e}" for e in rep.errors] or ["None."]) + [""]
    L += ["## Warnings", ""] + ([f"- {w}" for w in rep.warnings] or ["None."]) + [""]
    (KB / "VALIDATION_REPORT.md").write_text("\n".join(L), encoding="utf-8")
    print(f"{'PASS' if not rep.errors else 'FAIL'}: {len(rep.errors)} errors, {len(rep.warnings)} warnings "
          f"({rep.checks['error checks']} + {rep.checks['warning checks']} checks)")
    for e in rep.errors[:60]:
        print("  ERROR", e)
    for w in rep.warnings[:60]:
        print("  WARN ", w)
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
