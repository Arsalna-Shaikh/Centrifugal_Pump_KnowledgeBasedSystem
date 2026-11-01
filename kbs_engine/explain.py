"""Human-readable explanation of an engine result."""
from __future__ import annotations

from .knowledge import KnowledgeBase


def _sym_line(kb: KnowledgeBase, sid: str, e: dict) -> str:
    s = f"{sid} {kb.name(sid)}: {e['state']}"
    d = e.get("sensor")
    if d and "compared_value" in d:
        unit = "%" if d["basis"].startswith("pct") else ""
        s += (f"  [{d['indicator_id']} = {d['raw_value']} -> {d['compared_value']}{unit} {d['operator']} "
              f"{d['limit']} ({d['threshold_id']}, {d['basis']}, threshold support: {d['threshold_support']})]")
        if d.get("reason"):
            s += f" - {d['reason']}"
    elif d and d.get("reason"):
        s += f"  [{d['reason']} for {d['threshold_id']}]"
    if e.get("source") and e["source"] not in ("sensor",):
        s += f"  (source: {e['source']})"
    return s


def explain(result: dict, kb: KnowledgeBase | None = None) -> str:
    kb = kb or KnowledgeBase()
    outcome = {"diagnosis": "Diagnosis", "OUT-N": "Normal - no fault evidence",
               "OUT-U": "Unknown - further investigation required"}[result["outcome"]]
    L = [f"OUTCOME: {outcome}", ""]
    if result["safety"]:
        L.append("SAFETY (evaluated for every hypothesis):")
        for s in result["safety"]:
            L.append(f"  ! {s['safety_id']}: {s['message']}  <- {'; '.join(s['reasons'])} "
                     f"[support: {s['support']}]")
        L.append("")
    L.append("EVIDENCE:")
    for sid, e in result["symptoms"].items():
        L.append("  " + _sym_line(kb, sid, e))
    for n in result["notes"]:
        L.append(f"  note: {n}")
    L.append("")
    agenda = {ev["rule_id"]: ev for ev in result["agenda"]}
    for title, key in (("FAULT HYPOTHESES", "faults"), ("ROOT-CAUSE HYPOTHESES", "causes")):
        if not result[key]:
            continue
        L.append(title + " (status = diagnostic likelihood; support = quality of the knowledge):")
        for h in result[key]:
            L.append(f"  {h['id']} {kb.name(h['id'])}: status {h['status']} | support {h['support']}")
            for rid in h["fired_rules"]:
                ev = agenda[rid]
                cap = " (capped to 'possible' for display: rule is unvalidated)" if ev["capped_for_display"] else ""
                L.append(f"    fired {rid}: likelihood {ev['likelihood']}{cap}; support {ev['support']}; "
                         f"because {', '.join(ev['satisfied'])}; sources {', '.join(ev['sources'])}")
                for a in ev["assumptions"]:
                    L.append(f"      assumption ({a['type']}, {a['validation_status']}): {a['text']}")
            for rid in h["lowered_by"]:
                L.append(f"    lowered by {rid}: {agenda[rid]['explanation']}")
            for rid in h["blocked_by"]:
                L.append(f"    ruled out by {rid}: {agenda[rid]['explanation']}")
            for rid in h["pending_rules"]:
                rec = next(r for r in result["rules_not_fired"] if r["rule_id"] == rid)
                L.append(f"    pending {rid}: needs {', '.join(rec['unknown'])}")
        L.append("")
    if result["chains"]:
        L.append("FAULT CHAINS:")
        for c in result["chains"]:
            L.append(f"  {c['from']} -> {c['to']} ({c['relationship']}, support {c['support']}, rule {c['rule_id']})")
        L.append("")
    if result["candidate_causes"]:
        L.append("CANDIDATE ROOT CAUSES (from caused_by knowledge, not yet confirmed):")
        for fid, cs in result["candidate_causes"].items():
            for c in cs:
                t = f"; confirm with {', '.join(c['confirming_tests'])}" if c["confirming_tests"] else ""
                L.append(f"  {fid} <- {c['cause_id']} {kb.name(c['cause_id'])} [support {c['support']}]{t}")
        L.append("")
    if result["conflicts"]:
        L.append("CONFLICTS:")
        for c in result["conflicts"]:
            L.append(f"  {c['type']}: {c['detail']}")
        L.append("")
    if result["test_requests"]:
        L.append("TESTS REQUESTED:")
        for t in result["test_requests"]:
            L.append(f"  {t['test_id']} {kb.name(t['test_id'])} (requested by {', '.join(t['requested_by'])})")
        L.append("")
    if result["observation_requests"]:
        L.append("OBSERVATIONS NEEDED (unknown evidence is never treated as absent):")
        for o in result["observation_requests"]:
            L.append(f"  {o['needed']}  (for rule {o['rule_id']})")
        L.append("")
    if result["actions"]:
        L.append("RECOMMENDED ACTIONS:")
        for a in result["actions"]:
            pre = f"  precautions: {', '.join(a['precautions'])}" if a["precautions"] else ""
            sup = ", ".join(f"{r}:{s}" for r, s in a["support"])
            L.append(f"  {a['action_id']} {kb.name(a['action_id'])} - for {', '.join(a['for'])} [{sup}]{pre}")
    return "\n".join(L)
