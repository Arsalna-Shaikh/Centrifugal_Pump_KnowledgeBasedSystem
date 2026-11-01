"""Decision-support layer (DS-1): turn a kbs_engine result into an operator-friendly diagnostic report.

Principles
- Nothing is invented: every hypothesis, action, test, hazard class and warning comes from the engine
  result or the knowledge base, with its provenance.  Where the KB has no knowledge (e.g. case-specific
  severity) the report says so instead of guessing.
- Uncertainty is preserved: competing, possible, pending and ruled-out hypotheses are all shown, and
  diagnostic status (likelihood) is always shown next to - never merged with - knowledge support quality.
"""
from __future__ import annotations

import re

from kbs_engine.knowledge import KnowledgeBase, split

STATUS_TEXT = {
    "confirmed": "Confirmed by a diagnostic test",
    "likely": "Likely - characteristic evidence present",
    "possible": "Possible - compatible evidence, or lowered by contradicting evidence",
    "pending": "Under investigation - some evidence present, more information needed",
    "unlikely": "Unlikely - argued against by the evidence",
    "blocked": "Ruled out by known absent evidence",
}
SUPPORT_TEXT = {
    "Strong": "Strong - stated by an independent engineering source",
    "Moderate": "Moderate - stated by a manufacturer/trade source only",
    "Unvalidated": "Unvalidated - project knowledge only, not yet confirmed by a source",
    "Disputed": "Disputed - contradicted by an independent source",
    "Definitional": "Definitional",
    "n/a": "Not applicable - no rule has fired yet",
}
OUTCOME_TEXT = {
    "diagnosis": "Fault diagnosis available",
    "OUT-N": "Normal - no fault evidence and all assessable symptoms known to be absent",
    "OUT-U": "Unknown - the evidence is not sufficient for a diagnosis; further investigation required",
}
PRIORITY_ORDER = ["P1-immediate", "P2-high", "P3-planned"]
COST_NOTE = ("Qualitative class inherited from the legacy knowledge base; no monetary or time estimate is "
             "available from any source.")
SECTIONS = [("diagnoses", ("confirmed", "likely")), ("also_possible", ("possible",)),
            ("under_investigation", ("pending",)), ("ruled_out_or_argued_against", ("unlikely", "blocked"))]


def _fmt(x) -> str:
    """Readable number: removes floating-point artefacts such as 3.9000000000000004 (display only)."""
    return f"{round(float(x), 3):g}" if isinstance(x, (int, float)) else str(x)


class ReportBuilder:
    def __init__(self, kb: KnowledgeBase | None = None):
        self.kb = kb or KnowledgeBase()
        self.rules = {r["rule_id"]: r for r in self.kb.rules}

    # ------------------------------------------------------------------ helpers
    def _humanize(self, text: str) -> str:
        """'SYM-19 present' -> 'Rapid temperature rise (SYM-19) present'."""
        return re.sub(r"\b((?:SYM|TST|FLT|CAU|PAR)-\d{2})\b", lambda m: f"{self.kb.name(m.group(1))} ({m.group(1)})",
                      text)

    def _source(self, sid):
        s = self.kb.sources.get(sid, {})
        return {"id": sid, "title": s.get("title", sid), "type": s.get("source_type", ""),
                "read_status": s.get("read_status", "")}

    def _evidence_item(self, result, sid):
        e = result["symptoms"].get(sid, {"state": "unknown", "source": None, "sensor": None})
        item = {"symptom_id": sid, "symptom": self.kb.name(sid), "state": e["state"], "source": e.get("source")}
        d = e.get("sensor") or {}
        if "compared_value" in d:
            unit = "% of " + ("rated" if d["basis"] == "pct_rated" else "baseline") if d["basis"].startswith("pct") \
                else self.kb.indicators[d["indicator_id"]]["unit"]
            limit = ("site limit entered by the user" if d.get("limit_origin") == "equipment-specific override"
                     else f"threshold {d['threshold_support'].lower()}")
            item["reading"] = (f"{self.kb.name(d['indicator_id'])} = {_fmt(d['raw_value'])} "
                               f"({_fmt(d['compared_value'])} {unit}; limit {d['operator']} {_fmt(d['limit'])}, "
                               f"{d['threshold_id']}, {limit})")
            if d.get("reason"):                   # reading present but not trusted (estimated / inconsistent)
                item["reading"] += f" - NOT USED: {d['reason']}"
        elif d.get("reason"):
            item["reading"] = d["reason"]
        return item

    def _cost_downtime(self, row):
        """Cost/downtime classes of a fault or action row, with their own provenance (never merged with hazard)."""
        return {"cost_class": row.get("cost_class") or "UNKNOWN", "downtime_class": row.get("downtime_class") or "UNKNOWN",
                "knowledge_support": row.get("cost_downtime_support_level"),
                "validation_status": row.get("cost_downtime_validation_status"),
                "sources": split(row.get("cost_downtime_source_ids")),
                "source_locator": row.get("cost_downtime_source_locator"), "note": COST_NOTE}

    def _priority(self, action, status_of, warned):
        """Maintenance priority per the KB policy: safety warnings, action purpose and diagnostic status only."""
        purpose = self.kb.actions[action["action_id"]]["purpose"]
        if purpose == "make_safe" or warned & set(action["for"]):
            return "P1-immediate"
        if any(status_of.get(x) in ("confirmed", "likely") for x in action["for"]):
            return "P2-high"
        return "P3-planned"

    def _symptoms_of(self, rule, kinds=("symptoms_all", "symptoms_any")):
        out = []
        for k in kinds:
            out += rule["conditions"].get(k, [])
        return out

    # ------------------------------------------------------------------ per hypothesis
    def _hypothesis(self, result, h, rank):
        kb = self.kb
        table = kb.faults if h["kind"] == "fault" else kb.causes
        row = table.get(h["id"], {})
        agenda = {ev["rule_id"]: ev for ev in result["agenda"]}
        supporting, explanation, seen = [], [], set()
        for rid in h["fired_rules"]:
            rule, ev = self.rules[rid], agenda[rid]
            for sid in self._symptoms_of(rule):
                if result["symptoms"].get(sid, {}).get("state") == "present" and sid not in seen:
                    seen.add(sid)
                    supporting.append(self._evidence_item(result, sid))
            for t in rule["conditions"].get("tests", []):
                supporting.append({"test_id": t["test_id"], "test": kb.name(t["test_id"]), "result": t["result"]})
            explanation.append({
                "rule_id": rid, "because": ev["satisfied"], "reasoning": rule["explanation"],
                "rule_likelihood": ev["likelihood"], "reported_as": ev["reported"],
                "capped_because_unvalidated": ev["capped_for_display"], "knowledge_support": ev["support"],
                "sources": [self._source(s) for s in ev["sources"]],
                "assumptions": [a["text"] + f" ({a['validation_status']})" for a in ev["assumptions"]]})
        # evidence already present for rules that are still waiting on unknown conditions
        for rid in h["pending_rules"]:
            for sid in self._symptoms_of(self.rules[rid]):
                if result["symptoms"].get(sid, {}).get("state") == "present" and sid not in seen:
                    seen.add(sid)
                    supporting.append(dict(self._evidence_item(result, sid), partial=True, for_rule=rid))
        contradicting = []
        for rid in h["lowered_by"] + h["blocked_by"]:
            rule = self.rules[rid]
            ev = agenda[rid]
            contradicting.append({"rule_id": rid, "effect": "lowered" if rid in h["lowered_by"] else "ruled out",
                                  "evidence": [self._evidence_item(result, s) for s in
                                               self._symptoms_of(rule, ("symptoms_all", "symptoms_absent"))],
                                  "reasoning": rule["explanation"], "knowledge_support": ev["support"],
                                  "sources": [self._source(s) for s in ev["sources"]]})
        # expected symptoms (manifests_as) that are known to be absent - shown, not used to rule out
        expected_absent = []
        if h["kind"] == "fault":
            for r in kb.rels_by_type["manifests_as"]:
                if r["from_id"] == h["id"] and r["support_level"] in ("Strong", "Moderate") \
                        and result["symptoms"].get(r["to_id"], {}).get("state") == "absent" \
                        and not r["qualifier"]:
                    expected_absent.append({"symptom_id": r["to_id"], "symptom": kb.name(r["to_id"]),
                                            "relationship": r["rel_id"], "knowledge_support": r["support_level"]})
        missing = []
        for rid in h["pending_rules"]:
            rec = next(x for x in result["rules_not_fired"] if x["rule_id"] == rid)
            missing.append({"rule_id": rid, "needs": [self._humanize(u) for u in rec["unknown"]],
                            "reasoning": self.rules[rid]["explanation"]})
        hazard = impact = None
        if h["kind"] == "fault":
            impact = self._cost_downtime(row)
            hazard = {"class": row.get("hazard_class"), "knowledge_support": row.get("hazard_support_level"),
                      "validation_status": row.get("hazard_validation_status"),
                      "sources": split(row.get("hazard_source_ids")),
                      "note": "Hazard class of the fault type (static). Case-specific severity is not assessed: "
                              "the knowledge base has no validated severity model."}
        return {
            "rank": rank, "id": h["id"], "name": row.get("name", h["id"]), "kind": h["kind"],
            "diagnostic_status": h["status"], "diagnostic_status_text": STATUS_TEXT.get(h["status"], h["status"]),
            "rule_likelihood_before_adjustment": h["likelihood"],
            "knowledge_support": h["support"], "knowledge_support_text": SUPPORT_TEXT.get(h["support"], h["support"]),
            "hazard": hazard, "case_severity": None, "maintenance_impact": impact,
            "supporting_evidence": supporting, "contradicting_evidence": contradicting,
            "expected_but_absent": expected_absent, "missing_evidence": missing, "explanation": explanation,
        }

    # ------------------------------------------------------------------ whole report
    def build(self, result: dict) -> dict:
        kb = self.kb
        faults = result["faults"]
        hyps = {k: [] for k, _ in SECTIONS}
        rank = 0
        for h in faults:
            for key, statuses in SECTIONS:
                if h["status"] in statuses:
                    rank += 1 if key != "ruled_out_or_argued_against" else 0
                    hyps[key].append(self._hypothesis(result, h, rank if key != "ruled_out_or_argued_against" else None))
        causes = [self._hypothesis(result, c, i + 1) for i, c in enumerate(result["causes"])]
        # present evidence that no fired or pending rule accounts for: show its KB links (not diagnoses)
        explained = {e["symptom_id"] for k, _ in SECTIONS for h in hyps[k] for e in h["supporting_evidence"]
                     if "symptom_id" in e} | {e["symptom_id"] for c in causes for e in c["supporting_evidence"]
                                              if "symptom_id" in e}
        unexplained = []
        for sid, e in result["symptoms"].items():
            if e["state"] != "present" or sid in explained:
                continue
            links = [{"id": r["from_id"], "name": kb.name(r["from_id"]), "relationship": r["rel_id"],
                      "condition": r["qualifier"], "knowledge_support": r["support_level"],
                      "confirm_with": [{"test_id": c["to_id"], "test": kb.name(c["to_id"])}
                                       for c in kb.rels_by_type["confirmed_by"] if c["from_id"] == r["from_id"]]}
                     for t in ("manifests_as", "indicated_by") for r in kb.rels_by_type[t] if r["to_id"] == sid]
            unexplained.append({**self._evidence_item(result, sid), "linked_to": links})
        candidate_causes = []
        for fid, cs in result["candidate_causes"].items():
            for c in cs:
                candidate_causes.append({"fault_id": fid, "fault": kb.name(fid), "cause_id": c["cause_id"],
                                         "cause": kb.name(c["cause_id"]), "knowledge_support": c["support"],
                                         "relationship": c["relationship"],
                                         "confirm_with": [{"test_id": t, "test": kb.name(t)}
                                                          for t in c["confirming_tests"]]})
        tests = []
        for t in result["test_requests"]:
            row = kb.tests[t["test_id"]]
            tests.append({"test_id": t["test_id"], "test": row["name"], "measures": row["measures"],
                          "why": t["requested_by"], "knowledge_support": row["support_level"],
                          "kind": "discriminating" if any(x.startswith("R-T-") for x in t["requested_by"])
                          else "confirming"})
        tests.sort(key=lambda x: (x["kind"] != "discriminating", x["test_id"]))
        warnings, precautions, warned = [], [], set()
        for s in result["safety"]:
            # Safety rules that trigger only on actions are work precautions, not operating hazards (KB-defined).
            row = kb.safety[s["safety_id"]]
            action_only = not split(row["trigger_fault_ids"]) and not split(row["trigger_symptoms_all"])
            if not action_only:
                warned |= set(split(row["trigger_fault_ids"]))
            (precautions if action_only else warnings).append({"safety_id": s["safety_id"], "message": s["message"], "triggered_by": s["reasons"],
                             "knowledge_support": s["support"], "sources": [self._source(x) for x in s["sources"]]})
        status_of = {h["id"]: h["status"] for h in result["faults"] + result["causes"]}
        policy = kb.meta["policies"]["maintenance_priority"]
        actions = []
        for a in result["actions"]:
            row = kb.actions[a["action_id"]]
            prio = self._priority(a, status_of, warned)
            actions.append({"action_id": a["action_id"], "action": row["name"], "purpose": row["purpose"],
                            "competence": row["competence"], "opens_pump": row["opens_pump"] == "yes",
                            "details": row["description"], "for": [{"id": x, "name": kb.name(x)} for x in a["for"]],
                            "knowledge_support": [{"relationship": r, "support": s} for r, s in a["support"]],
                            "maintenance_priority": {"level": prio,
                                                     "meaning": kb.meta["vocabularies"]["maintenance_priority"][prio],
                                                     "knowledge_support": policy["support_level"],
                                                     "sources": policy["source_ids"]},
                            "cost_downtime": self._cost_downtime(row),
                            "precautions": [{"safety_id": p, "message": kb.safety[p]["message"]}
                                            for p in a["precautions"]]})
        actions.sort(key=lambda x: PRIORITY_ORDER.index(x["maintenance_priority"]["level"]))  # stable: engine order kept
        critical = [h for k in ("diagnoses", "also_possible", "under_investigation") for h in hyps[k]
                    if h["hazard"] and h["hazard"]["class"] == "CRITICAL"]
        # count over every symptom in the KB: the engine omits symptoms it has no information about
        counts = {"present": 0, "absent": 0, "unknown": 0}
        for sid in kb.symptoms:
            counts[result["symptoms"].get(sid, {}).get("state", "unknown")] += 1
        competing = [c for c in result["conflicts"] if c["type"] == "competing_hypotheses"]
        data_conflicts = [c for c in result["conflicts"] if c["type"] != "competing_hypotheses"]
        unvalidated_thresholds = sorted({e["sensor"]["threshold_id"] for e in result["symptoms"].values()
                                         if e.get("sensor") and e["sensor"].get("threshold_support") == "Unvalidated"})
        return {
            "outcome": result["outcome"], "outcome_text": OUTCOME_TEXT[result["outcome"]],
            "headline": self._headline(result, hyps, warnings),
            "safety_warnings": warnings,
            "work_precautions": precautions,
            "critical_hazard_hypotheses": [{"id": h["id"], "name": h["name"], "status": h["diagnostic_status"]}
                                           for h in critical],
            "hypotheses": hyps,
            "competing_diagnoses": [{"faults": [{"id": f, "name": kb.name(f)} for f in c["faults"]],
                                     "note": "Several faults remain plausible; carry out the discriminating tests"}
                                    for c in competing],
            "root_causes": causes, "candidate_root_causes": candidate_causes,
            "fault_chains": [{"from": kb.name(c["from"]), "to": kb.name(c["to"]), "relationship": c["relationship"],
                              "knowledge_support": c["support"], "rule_id": c["rule_id"]} for c in result["chains"]],
            "unexplained_evidence": unexplained,
            "recommended_tests": tests,
            "information_needed": [{"needed": self._humanize(o["needed"]), "for_rule": o["rule_id"]}
                                   for o in result["observation_requests"]],
            "maintenance_actions": actions,
            "evidence_summary": counts,
            "evidence": [self._evidence_item(result, s) for s in result["symptoms"]],
            "data_conflicts": [{"type": c["type"], "detail": c["detail"]} for c in data_conflicts],
            "limitations": [
                "All numeric symptom thresholds are provisional (Unvalidated) until confirmed against ISO 10816-7, "
                "ANSI/HI 9.6.1/9.6.3 or OEM data." + (f" Used here: {', '.join(unvalidated_thresholds)}."
                                                      if unvalidated_thresholds else ""),
                "Diagnostic status and knowledge support are separate: a 'likely' diagnosis can rest on "
                "Moderate or Unvalidated knowledge, and Strong knowledge can still give only 'possible'.",
                "Unknown evidence is never treated as absent; missing observations are listed above.",
                "Cost and downtime are qualitative classes inherited from the legacy knowledge base (Unvalidated); "
                "no monetary or time estimates are given. Maintenance priority is a project policy (Unvalidated) "
                "based on safety warnings, action purpose and diagnostic status; it is separate from hazard class "
                "and does not affect the diagnosis.",
            ],
            "notes": result["notes"],
        }

    def _headline(self, result, hyps, warnings):
        if result["outcome"] == "OUT-N":
            text = "No fault indicated. All assessable symptoms are within limits."
        elif hyps["diagnoses"]:
            top = hyps["diagnoses"]
            names = ", ".join(f"{h['name']} ({h['diagnostic_status']})" for h in top)
            text = f"Most likely: {names}."
            if hyps["also_possible"]:
                text += " Also possible: " + ", ".join(h["name"] for h in hyps["also_possible"]) + "."
        else:
            open_h = hyps["also_possible"] + hyps["under_investigation"]
            text = "No diagnosis yet." + (" Open hypotheses: " + ", ".join(
                f"{h['name']} ({h['diagnostic_status']})" for h in open_h) + "." if open_h else "")
        if warnings:
            text = f"SAFETY WARNING ({len(warnings)}). " + text
        return text


def build_report(result: dict, kb: KnowledgeBase | None = None) -> dict:
    return ReportBuilder(kb).build(result)


# ====================================================================== text rendering
def render_text(report: dict) -> str:
    L = ["=" * 72, "CENTRIFUGAL PUMP DIAGNOSTIC REPORT", "=" * 72, report["headline"],
         f"Outcome: {report['outcome_text']}", ""]
    if report["safety_warnings"]:
        L.append("SAFETY WARNINGS (checked against every hypothesis, not only the top one)")
        for w in report["safety_warnings"]:
            L.append(f"  !! {w['message']} [{w['safety_id']}; knowledge support {w['knowledge_support']}]")
            L.append(f"     triggered by: {'; '.join(w['triggered_by'])}")
        L.append("")
    labels = {"diagnoses": "DIAGNOSES", "also_possible": "ALSO POSSIBLE",
              "under_investigation": "UNDER INVESTIGATION (need more information)",
              "ruled_out_or_argued_against": "RULED OUT / ARGUED AGAINST"}
    for key, title in labels.items():
        hs = report["hypotheses"][key]
        if not hs:
            continue
        L.append(title)
        for h in hs:
            r = f"{h['rank']}. " if h["rank"] else "- "
            L.append(f"  {r}{h['name']} [{h['id']}]")
            L.append(f"     Diagnostic status : {h['diagnostic_status_text']}")
            L.append(f"     Knowledge support : {h['knowledge_support_text']}")
            if h["hazard"]:
                hz = h["hazard"]
                L.append(f"     Hazard class      : {hz['class']} (support {hz['knowledge_support']}); "
                         "case severity not assessed")
            if h["maintenance_impact"]:
                mi = h["maintenance_impact"]
                L.append(f"     Repair cost/downtime: {mi['cost_class']} / {mi['downtime_class']} "
                         f"(qualitative; support {mi['knowledge_support']})")
            for e in h["supporting_evidence"]:
                if "symptom" in e:
                    part = f" [partial: {e['for_rule']} still needs more information]" if e.get("partial") else ""
                    L.append(f"     + {e['symptom']}: {e['state']}" + (f" - {e['reading']}" if e.get("reading") else
                                                                       f" ({e['source']})") + part)
                else:
                    L.append(f"     + test {e['test']}: {e['result']}")
            for c in h["contradicting_evidence"]:
                ev = ", ".join(f"{x['symptom']} {x['state']}" for x in c["evidence"])
                L.append(f"     - {c['effect']} by {c['rule_id']}: {ev} - {c['reasoning']}")
            for x in h["expected_but_absent"]:
                L.append(f"     ~ expected symptom absent: {x['symptom']} (support {x['knowledge_support']})")
            for m in h["missing_evidence"]:
                L.append(f"     ? {m['rule_id']} needs: {', '.join(m['needs'])}")
            for ex in h["explanation"]:
                src = ", ".join(s["id"] for s in ex["sources"])
                cap = " -> shown as 'possible' (unvalidated knowledge)" if ex["capped_because_unvalidated"] else ""
                L.append(f"     why: {ex['rule_id']} ({ex['rule_likelihood']}{cap}; support {ex['knowledge_support']}; "
                         f"sources {src}) - {ex['reasoning']}")
                for a in ex["assumptions"]:
                    L.append(f"          assumption: {a}")
        L.append("")
    if report["unexplained_evidence"]:
        L.append("EVIDENCE NOT EXPLAINED BY ANY RULE (knowledge-base links only - not diagnoses)")
        for u in report["unexplained_evidence"]:
            links = "; ".join(f"{x['name']} ({x['knowledge_support']}{', ' + x['condition'] if x['condition'] else ''})"
                              for x in u["linked_to"]) or "no link in the knowledge base"
            L.append(f"  * {u['symptom']}: linked to {links}")
        L.append("")
    if report["competing_diagnoses"]:
        L.append("COMPETING DIAGNOSES")
        for c in report["competing_diagnoses"]:
            L.append("  " + " vs ".join(f["name"] for f in c["faults"]) + f" - {c['note']}")
        L.append("")
    if report["root_causes"] or report["candidate_root_causes"]:
        L.append("ROOT CAUSES")
        for c in report["root_causes"]:
            L.append(f"  * {c['name']} [{c['id']}]: {c['diagnostic_status']} (knowledge support {c['knowledge_support']})")
        for c in report["candidate_root_causes"]:
            t = ", ".join(x["test"] for x in c["confirm_with"]) or "no confirming test in knowledge base"
            L.append(f"  candidate for {c['fault']}: {c['cause']} (support {c['knowledge_support']}); confirm: {t}")
        for ch in report["fault_chains"]:
            L.append(f"  chain: {ch['from']} -> {ch['to']} (support {ch['knowledge_support']})")
        L.append("")
    if report["work_precautions"]:
        L.append("WORK PRECAUTIONS (apply when carrying out the actions below)")
        for w in report["work_precautions"]:
            L.append(f"  - {w['message']} [{w['safety_id']}; knowledge support {w['knowledge_support']}]")
        L.append("")
    if report["recommended_tests"]:
        L.append("RECOMMENDED DIAGNOSTIC TESTS")
        for t in report["recommended_tests"]:
            L.append(f"  [{t['kind']}] {t['test']} ({t['test_id']}) - {t['measures']}; requested by {', '.join(t['why'])}")
        L.append("")
    if report["information_needed"]:
        L.append("INFORMATION NEEDED (unknown is not treated as absent)")
        for o in report["information_needed"]:
            L.append(f"  - {o['needed']} (for {o['for_rule']})")
        L.append("")
    if report["maintenance_actions"]:
        L.append("MAINTENANCE ACTIONS (ordered by maintenance priority - a project policy, Unvalidated)")
        for a in report["maintenance_actions"]:
            sup = ", ".join(f"{k['support']}" for k in a["knowledge_support"])
            cd = a["cost_downtime"]
            L.append(f"  - [{a['maintenance_priority']['level']}] {a['action']} [{a['action_id']}] for "
                     f"{', '.join(f['name'] for f in a['for'])} "
                     f"(purpose {a['purpose']}; competence {a['competence']}; support {sup})")
            L.append(f"      cost {cd['cost_class']}, downtime {cd['downtime_class']} "
                     f"(qualitative; support {cd['knowledge_support']})")
            for p in a["precautions"]:
                L.append(f"      precaution: {p['message']}")
        L.append("")
    if report["data_conflicts"]:
        L.append("DATA CONFLICTS")
        for c in report["data_conflicts"]:
            L.append(f"  - {c['type']}: {c['detail']}")
        L.append("")
    s = report["evidence_summary"]
    L.append(f"EVIDENCE: {s['present']} present, {s['absent']} absent, {s['unknown']} unknown")
    L.append("LIMITATIONS")
    L += [f"  - {x}" for x in report["limitations"]]
    return "\n".join(L)
