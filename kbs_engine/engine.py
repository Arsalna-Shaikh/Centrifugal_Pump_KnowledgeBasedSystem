"""Layered forward-chaining inference engine for the structured pump knowledge base (KR-2).

Pipeline
  L1  evidence abstraction: measurements + equipment parameters -> symptom states via thresholds;
      merge with manual observations; apply implies/excludes; record conflicts.
  L2  fault rules -> fault hypotheses;  L2 negative rules -> lower/block hypotheses.
  L3  cause rules and chain rules (use L2 results).
  L4  test-request rules (use L2/L3 results).
  L5  actions (recommends/corrects) and safety rules evaluated for EVERY hypothesis.

Layers are stratified and each layer is run to a fixed point over a working memory, so conclusions
of earlier layers feed later ones (genuine forward chaining).  Knowledge support quality
(support_level) and diagnostic likelihood are kept as separate fields throughout.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .knowledge import KnowledgeBase, split

STATUS_ORDER = ["blocked", "unlikely", "pending", "possible", "likely", "confirmed"]
SUPPORT_RANK = {"Definitional": 0, "Unvalidated": 1, "Moderate": 2, "Strong": 3}
HAZARD_RANK = {"NONE": 0, "UNASSIGNED": 1, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
BASIS_PREFERENCE = ["pct_baseline", "pct_rated", "absolute"]       # kb_meta policies.threshold_selection
LAYERS = ["L2_fault", "L2_negative", "L3_cause", "L3_chain", "L4_test_request"]


def _rank(status: str) -> int:
    return STATUS_ORDER.index(status)


@dataclass
class Case:
    """Input to the engine.  Keys may be KB IDs or readable names/keys."""
    equipment: dict = field(default_factory=dict)        # PAR id or name -> value
    measurements: dict = field(default_factory=dict)     # IND id or name -> float or None
    observations: dict = field(default_factory=dict)     # SYM id or key -> present / absent / unknown
    test_results: dict = field(default_factory=dict)     # TST id -> result value
    imputed: set = field(default_factory=set)            # IND ids or names whose value is imputed/estimated
    threshold_overrides: dict = field(default_factory=dict)  # THR id -> equipment-specific numeric value


@dataclass
class Hypothesis:
    entity_id: str
    kind: str                                   # fault | cause
    fired: list = field(default_factory=list)   # dicts: rule_id, likelihood, reported, support, ...
    pending: list = field(default_factory=list)
    lowered_by: list = field(default_factory=list)
    blocked_by: list = field(default_factory=list)
    status: str = "pending"
    support: str = "n/a"                        # no fired rule -> no knowledge support to report

    @property
    def likelihood(self) -> str:
        """Best stored likelihood among fired rules (before display cap and negative evidence)."""
        if not self.fired:
            return "pending" if self.pending else "unlikely"
        return max((f["likelihood"] for f in self.fired), key=_rank)


class InferenceEngine:
    def __init__(self, kb: KnowledgeBase | None = None):
        self.kb = kb or KnowledgeBase()
        pol = self.kb.meta["policies"]
        self.cap_unvalidated = pol.get("likelihood_display_cap", {}).get("enabled", True)

    # ======================================================================== L1 evidence
    def _normalise(self, case: Case):
        kb = self.kb
        params = {kb.parameter_id(k): v for k, v in case.equipment.items() if v not in (None, "")}
        meas = {kb.indicator_id(k): (None if v is None else float(v)) for k, v in case.measurements.items()}
        imputed = {kb.indicator_id(k) for k in case.imputed}
        obs = {}
        for k, v in case.observations.items():
            if v not in ("present", "absent", "unknown"):
                raise ValueError(f"Observation for {k} must be present/absent/unknown, got {v!r}")
            obs[kb.symptom_id(k)] = v
        for t, res in case.test_results.items():
            if t not in kb.tests or res not in split(kb.tests[t]["result_values"]):
                raise ValueError(f"Invalid test result {t}={res!r}")
        notes, conflicts = [], []
        # indicators whose value must not be turned into evidence, with the reason shown to the user
        untrusted = {i: "input value is imputed/estimated - evidence not derived from it" for i in imputed}
        d, s = meas.get("IND-12"), meas.get("IND-07")
        if d is not None and s is not None and d < s:
            reason = "discharge pressure is below suction pressure - readings inconsistent, evidence not derived"
            untrusted.update({"IND-12": reason, "IND-07": reason})
            conflicts.append({"type": "inconsistent_measurements", "symptoms": [],
                              "detail": f"discharge pressure {d} bar is below suction pressure {s} bar; both "
                                        "readings are treated as unknown"})
        # differential pressure can be derived from discharge and suction pressure
        if meas.get("IND-06") is None and d is not None and s is not None:
            meas["IND-06"] = d - s
            notes.append("IND-06 differential pressure derived as discharge (IND-12) minus suction (IND-07)")
            src = [untrusted[i] for i in ("IND-12", "IND-07") if i in untrusted]
            if src:
                untrusted["IND-06"] = src[0]
        return params, meas, untrusted, obs, notes, conflicts

    def _threshold_value(self, t, overrides):
        if t["threshold_id"] in overrides:
            return float(overrides[t["threshold_id"]]), "equipment-specific override"
        if t["value"]:
            return float(t["value"]), "knowledge base"
        return None, None

    def _evaluate_symptom(self, sid, params, meas, untrusted, overrides, allow_non_default):
        """Return (state, detail) for one sensor symptom; detail is None if not assessable."""
        ths = self.kb.thresholds_by_symptom.get(sid, [])
        candidates = []
        for pass_default in (["yes"] + (["no"] if allow_non_default else [])):
            for basis in BASIS_PREFERENCE:
                candidates += [t for t in ths if t["basis"] == basis and t["default_for_basis"] == pass_default]
        applicable = []
        for t in candidates:
            value, value_origin = self._threshold_value(t, overrides)
            ind = self.kb.indicators[t["indicator_id"]]
            ref_param = {"pct_rated": ind["rated_parameter_id"], "pct_baseline": ind["baseline_parameter_id"]}.get(
                t["basis"])
            if ref_param and params.get(ref_param) in (None, 0, 0.0):
                continue                          # no rated/baseline reference for this equipment
            if t["value_parameter_id"]:
                if params.get(t["value_parameter_id"]) is None:
                    continue
                value, value_origin = float(params[t["value_parameter_id"]]), f"equipment parameter {t['value_parameter_id']}"
            if value is None:
                continue                          # threshold value not sourced -> cannot be used
            applicable.append((t, value, value_origin, ref_param))
        if not applicable:
            return "unknown", None
        measured = [a for a in applicable if meas.get(a[0]["indicator_id"]) is not None]
        if not measured:
            t = applicable[0][0]
            return "unknown", {"threshold_id": t["threshold_id"], "indicator_id": t["indicator_id"],
                               "reason": "measurement missing"}
        t, value, value_origin, ref_param = measured[0]
        raw = meas[t["indicator_id"]]
        x = raw if not ref_param else 100.0 * raw / float(params[ref_param])
        hit = {"<": x < value, "<=": x <= value, ">": x > value, ">=": x >= value}[t["operator"]]
        detail = {"threshold_id": t["threshold_id"], "indicator_id": t["indicator_id"], "basis": t["basis"],
                  "raw_value": raw, "compared_value": round(x, 3), "operator": t["operator"], "limit": value,
                  "limit_origin": value_origin, "threshold_support": t["support_level"],
                  "threshold_sources": split(t["source_ids"]), "default": t["default_for_basis"] == "yes"}
        if t["indicator_id"] in untrusted:
            detail["reason"] = untrusted[t["indicator_id"]]
            return "unknown", detail
        return ("present" if hit else "absent"), detail

    def derive_evidence(self, case: Case, allow_non_default_thresholds: bool = False):
        params, meas, untrusted, obs, notes, conflicts = self._normalise(case)
        states, evidence, assessable = {}, {}, set()
        for sid in self.kb.symptoms:
            sensor_state, detail = "unknown", None
            if sid in self.kb.thresholds_by_symptom:
                sensor_state, detail = self._evaluate_symptom(sid, params, meas, untrusted, case.threshold_overrides,
                                                              allow_non_default_thresholds)
                if detail is not None:
                    assessable.add(sid)
            manual = obs.get(sid, "unknown")
            if sensor_state != "unknown" and manual != "unknown" and sensor_state != manual:
                conflicts.append({"type": "sensor_vs_observation", "symptoms": [sid],
                                  "detail": f"sensor says {sensor_state}, observation says {manual}"})
                state, source = "unknown", "conflict"
            elif sensor_state != "unknown":
                state, source = sensor_state, "sensor"
            elif manual != "unknown":
                state, source = manual, "observation"
            else:
                state, source = "unknown", None
            states[sid] = state
            evidence[sid] = {"state": state, "source": source, "sensor": detail,
                             "observation": obs.get(sid)}
        # symptom relations
        for r in self.kb.rels_by_type["implies"]:
            a, b = r["from_id"], r["to_id"]
            if states[a] == "present" and states[b] == "absent":
                conflicts.append({"type": "implication_violated", "symptoms": [a, b], "relationship": r["rel_id"],
                                  "detail": f"{a} present requires {b}"})
                states[a] = states[b] = "unknown"
            elif states[a] == "present" and states[b] == "unknown":
                states[b] = "present"
                evidence[b].update(state="present", source=f"implied by {a} ({r['rel_id']})")
            elif states[b] == "absent" and states[a] == "unknown":
                states[a] = "absent"
                evidence[a].update(state="absent", source=f"implied by absence of {b} ({r['rel_id']})")
        for r in self.kb.rels_by_type["excludes"]:
            a, b = r["from_id"], r["to_id"]
            if states[a] == "present" and states[b] == "present":
                conflicts.append({"type": "mutually_exclusive", "symptoms": [a, b], "relationship": r["rel_id"],
                                  "detail": f"{a} and {b} cannot both be present - both set to unknown"})
                states[a] = states[b] = "unknown"
        for sid in states:
            evidence[sid]["state"] = states[sid]
        return params, states, evidence, conflicts, assessable, notes

    # ======================================================================== rule evaluation
    def _eval_conditions(self, rule, wm):
        """Return ('fired' | 'pending' | 'blocked', details)."""
        c, states = rule["conditions"], wm["states"]
        det = {"satisfied": [], "unknown": [], "failed": []}

        def mark(ok, item):
            det["satisfied" if ok is True else "unknown" if ok is None else "failed"].append(item)

        for s in c.get("symptoms_all", []):
            mark({"present": True, "unknown": None}.get(states[s], False), f"{s} present")
        if c.get("symptoms_any"):
            vals = [states[s] for s in c["symptoms_any"]]
            ok = True if "present" in vals else (None if "unknown" in vals else False)
            mark(ok, "any of " + "/".join(c["symptoms_any"]) + " present")
        for s in c.get("symptoms_absent", []):
            mark({"absent": True, "unknown": None}.get(states[s], False), f"{s} absent")
        for t in c.get("tests", []):
            got = wm["tests"].get(t["test_id"])
            mark(None if got is None else got == t["result"], f"{t['test_id']} = {t['result']}")
        for p, v in c.get("context", {}).items():
            got = wm["params"].get(p)
            mark(None if got is None else got == v, f"{p} = {v}")

        def fstatus(fid):
            h = wm["hyp"].get(fid)
            return h.status if h else "unlikely"

        for f in c.get("faults_all", []):
            mark(_rank(fstatus(f["fault_id"])) >= _rank(f["min_status"]), f"{f['fault_id']} >= {f['min_status']}")
        if c.get("faults_any"):
            ok = any(_rank(fstatus(f["fault_id"])) >= _rank(f["min_status"]) for f in c["faults_any"])
            mark(ok, "any of " + "/".join(f["fault_id"] for f in c["faults_any"]))
        if "faults_count" in c:
            fc = c["faults_count"]
            n = sum(_rank(fstatus(f)) >= _rank(fc["min_status"]) for f in fc["fault_ids"])
            mark(n >= fc["min"], f"at least {fc['min']} of {'/'.join(fc['fault_ids'])} >= {fc['min_status']}")

        if det["failed"]:
            return "blocked", det
        if det["unknown"]:
            return "pending", det
        return "fired", det

    def _reported(self, rule):
        like = rule["conclusion"]["likelihood"]
        if self.cap_unvalidated and rule["support_level"] == "Unvalidated" and _rank(like) > _rank("possible"):
            return "possible", True
        return like, False

    def _hyp(self, wm, eid, kind):
        if eid not in wm["hyp"]:
            wm["hyp"][eid] = Hypothesis(eid, kind)
        return wm["hyp"][eid]

    @staticmethod
    def _recompute(h: Hypothesis):
        if h.fired:
            best = max(_rank(f["reported"]) for f in h.fired)
            status = STATUS_ORDER[best]
            h.support = max((f["support"] for f in h.fired if _rank(f["reported"]) == best),
                            key=lambda s: SUPPORT_RANK.get(s, 0))
        else:
            status = "pending" if h.pending else "unlikely"
            h.support = "n/a"
        for _ in h.lowered_by:
            if status == "confirmed":
                break                             # a test-confirmed fault is not lowered by symptom evidence
            status = {"likely": "possible", "possible": "unlikely", "pending": "unlikely"}.get(status, status)
        if h.blocked_by and status != "confirmed":
            status = "blocked"
        h.status = status

    def _fire(self, rule, det, wm, cycle):
        con = rule["conclusion"]
        reported, capped = self._reported(rule)
        event = {"rule_id": rule["rule_id"], "layer": rule["layer"], "cycle": cycle, "conclusion": con["type"],
                 "targets": con["targets"], "likelihood": con["likelihood"], "reported": reported,
                 "capped_for_display": capped, "support": rule["support_level"],
                 "validation_status": rule["validation_status"], "satisfied": det["satisfied"],
                 "relationships": rule["relationship_ids"], "sources": rule["source_ids"],
                 "assumptions": rule.get("assumptions", []), "explanation": rule["explanation"]}
        wm["agenda"].append(event)
        if con["type"] in ("fault", "cause"):
            for t in con["targets"]:
                h = self._hyp(wm, t, con["type"])
                h.fired.append(event)
                self._recompute(h)
        elif con["type"] == "lower":
            for t in con["targets"]:
                if t in wm["hyp"]:
                    h = wm["hyp"][t]
                    h.lowered_by.append(event)
                    self._recompute(h)
        elif con["type"] == "block":
            for t in con["targets"]:
                h = self._hyp(wm, t, "fault")
                h.blocked_by.append(event)
                self._recompute(h)
        elif con["type"] == "chain":
            for rel_id in con["targets"]:
                r = self.kb.relationships[rel_id]
                wm["chains"].append({"relationship": rel_id, "from": r["from_id"], "to": r["to_id"],
                                     "support": r["support_level"], "rule_id": rule["rule_id"],
                                     "reported": reported})
        elif con["type"] == "request_tests":
            for t in con["targets"]:
                if t not in wm["tests"]:
                    wm["test_requests"].setdefault(t, []).append(rule["rule_id"])

    def _partial_evidence(self, rule, det, wm):
        """A pending rule counts toward a 'pending' hypothesis only if some positive evidence is present."""
        c = rule["conditions"]
        positive = c.get("symptoms_all", []) + c.get("symptoms_any", [])
        return any(wm["states"].get(s) == "present" for s in positive) or \
            any(wm["tests"].get(t["test_id"]) == t["result"] for t in c.get("tests", []))

    def _forward_chain(self, wm):
        fired_ids, cycle = set(), 0
        for layer in LAYERS:
            changed = True
            while changed:                        # fixed point within the layer
                changed = False
                cycle += 1
                for rule in self.kb.rules_by_layer[layer]:
                    if rule["rule_id"] in fired_ids:
                        continue
                    outcome, det = self._eval_conditions(rule, wm)
                    if outcome == "fired":
                        self._fire(rule, det, wm, cycle)
                        fired_ids.add(rule["rule_id"])
                        changed = True
            # final status of rules in this layer that did not fire
            for rule in self.kb.rules_by_layer[layer]:
                if rule["rule_id"] in fired_ids:
                    continue
                outcome, det = self._eval_conditions(rule, wm)
                rec = {"rule_id": rule["rule_id"], "layer": layer, "outcome": outcome,
                       "satisfied": det["satisfied"], "unknown": det["unknown"], "failed": det["failed"]}
                wm["not_fired"].append(rec)
                if outcome == "pending" and rule["conclusion"]["type"] in ("fault", "cause") \
                        and self._partial_evidence(rule, det, wm):
                    for t in rule["conclusion"]["targets"]:
                        h = self._hyp(wm, t, rule["conclusion"]["type"])
                        h.pending.append(rec)
                        self._recompute(h)
                    wm["observation_requests"].extend(
                        {"needed": u, "rule_id": rule["rule_id"]} for u in det["unknown"])
                elif outcome == "pending" and rule["conclusion"]["type"] == "lower" and \
                        any(wm["states"].get(s) == "present" for s in rule["conditions"].get("symptoms_all", [])):
                    wm["observation_requests"].extend(
                        {"needed": u, "rule_id": rule["rule_id"]} for u in det["unknown"])

    # ======================================================================== L5 actions & safety
    def _actions(self, wm):
        acts = {}
        active = {eid: h for eid, h in wm["hyp"].items() if _rank(h.status) >= _rank("possible")}
        for r in self.kb.rels_by_type["recommends"]:
            if r["from_id"] in active:
                seq = int(r["qualifier"].split("=")[1]) if r["qualifier"].startswith("sequence=") else 1
                acts.setdefault(r["to_id"], {"action_id": r["to_id"], "for": [], "support": [], "sequence": seq})
                acts[r["to_id"]]["for"].append(r["from_id"])
                acts[r["to_id"]]["support"].append((r["rel_id"], r["support_level"]))
                acts[r["to_id"]]["sequence"] = min(acts[r["to_id"]]["sequence"], seq)
        for r in self.kb.rels_by_type["corrects"]:
            if r["to_id"] in active:
                acts.setdefault(r["from_id"], {"action_id": r["from_id"], "for": [], "support": [], "sequence": 1})
                acts[r["from_id"]]["for"].append(r["to_id"])
                acts[r["from_id"]]["support"].append((r["rel_id"], r["support_level"]))
        for a in acts.values():
            a["precautions"] = [p["to_id"] for p in self.kb.rels_by_type["requires_precaution"]
                                if p["from_id"] == a["action_id"]]
        return sorted(acts.values(), key=lambda a: (a["sequence"], a["action_id"]))

    def _safety(self, wm, actions):
        out = []
        action_ids = {a["action_id"] for a in actions}
        for s in self.kb.safety.values():
            reasons = []
            for fid in split(s["trigger_fault_ids"]):
                h = wm["hyp"].get(fid)
                if h and _rank(h.status) >= _rank(s["trigger_min_status"] or "possible"):
                    reasons.append(f"{fid} hypothesis status '{h.status}' (rank irrelevant)")
            syms = split(s["trigger_symptoms_all"])
            if syms and all(wm["states"].get(x) == "present" for x in syms):
                reasons.append("symptoms present: " + ", ".join(syms))
            hit_actions = sorted(set(split(s["trigger_action_ids"])) & action_ids)
            if hit_actions:
                reasons.append("recommended action(s): " + ", ".join(hit_actions))
            if reasons:
                out.append({"safety_id": s["safety_id"], "message": s["message"], "reasons": reasons,
                            "support": s["support_level"], "sources": split(s["source_ids"])})
        return out

    # ======================================================================== main entry
    def run(self, case: Case, allow_non_default_thresholds: bool = False) -> dict:
        params, states, evidence, conflicts, assessable, notes = self.derive_evidence(
            case, allow_non_default_thresholds)
        wm = {"params": params, "states": states, "tests": dict(case.test_results), "hyp": {}, "agenda": [],
              "chains": [], "test_requests": {}, "not_fired": [], "observation_requests": []}
        self._forward_chain(wm)
        actions = self._actions(wm)
        safety = self._safety(wm, actions)

        def ordered(kind):
            hs = [h for h in wm["hyp"].values() if h.kind == kind]
            table = self.kb.faults if kind == "fault" else self.kb.causes
            return sorted(hs, key=lambda h: (_rank(h.status), SUPPORT_RANK.get(h.support, 0), len(h.fired),
                                             HAZARD_RANK.get(table.get(h.entity_id, {}).get("hazard_class", ""), 0)),
                          reverse=True)

        faults, causes = ordered("fault"), ordered("cause")
        present = [s for s, v in states.items() if v == "present"]
        best = max((_rank(h.status) for h in faults), default=0)
        if best >= _rank("likely"):
            outcome = "diagnosis"
        elif not present and assessable and all(states[s] == "absent" for s in assessable) \
                and best < _rank("possible"):
            outcome = "OUT-N"
        else:
            outcome = "OUT-U"
        if outcome == "OUT-U":
            actions.append({"action_id": "ACT-17", "for": ["OUT-U"], "support": [("RC-14", "Definitional")],
                            "sequence": 99, "precautions": []})
            # request confirming tests for the open hypotheses
            for h in faults:
                if h.status in ("possible", "pending"):
                    for r in self.kb.rels_by_type["confirmed_by"]:
                        if r["from_id"] == h.entity_id and r["to_id"] not in wm["tests"]:
                            wm["test_requests"].setdefault(r["to_id"], []).append(f"confirm {h.entity_id}")
        # candidate causes for active faults (from caused_by), with the tests that would confirm them
        candidates = {}
        for h in faults:
            if _rank(h.status) < _rank("possible"):
                continue
            for r in self.kb.rels_by_type["caused_by"]:
                if r["from_id"] == h.entity_id:
                    tests = [c["to_id"] for c in self.kb.rels_by_type["confirmed_by"] if c["from_id"] == r["to_id"]]
                    candidates.setdefault(h.entity_id, []).append(
                        {"cause_id": r["to_id"], "relationship": r["rel_id"], "support": r["support_level"],
                         "confirming_tests": tests})
        differential = [h.entity_id for h in faults if h.status in ("likely", "possible")]
        if len(differential) > 1:
            conflicts.append({"type": "competing_hypotheses", "symptoms": [], "faults": differential,
                              "detail": "several faults remain plausible; see test requests"})
        seen, obs_req = set(), []
        for o in wm["observation_requests"]:
            key = (o["needed"], o["rule_id"])
            if key not in seen:
                seen.add(key)
                obs_req.append(o)
        return {
            "outcome": outcome,
            "faults": [self._hyp_dict(h) for h in faults],
            "causes": [self._hyp_dict(h) for h in causes],
            "candidate_causes": candidates,
            "chains": wm["chains"],
            "safety": safety,
            "actions": actions,
            "test_requests": [{"test_id": t, "requested_by": sorted(set(v))} for t, v in wm["test_requests"].items()],
            "observation_requests": obs_req,
            "conflicts": conflicts,
            "symptoms": {s: e for s, e in evidence.items() if e["state"] != "unknown" or e["sensor"] or e["observation"]},
            "assessable_symptoms": sorted(assessable),
            "agenda": wm["agenda"],
            "rules_not_fired": wm["not_fired"],
            "notes": notes,
        }

    @staticmethod
    def _hyp_dict(h: Hypothesis) -> dict:
        return {"id": h.entity_id, "kind": h.kind, "status": h.status, "likelihood": h.likelihood,
                "support": h.support, "fired_rules": [f["rule_id"] for f in h.fired],
                "pending_rules": [p["rule_id"] for p in h.pending],
                "lowered_by": [l["rule_id"] for l in h.lowered_by],
                "blocked_by": [b["rule_id"] for b in h.blocked_by]}


def diagnose(case: Case, kb: KnowledgeBase | None = None, **kw) -> dict:
    return InferenceEngine(kb).run(case, **kw)
