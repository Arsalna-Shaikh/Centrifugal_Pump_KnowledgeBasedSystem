"""Read-only loader for the structured knowledge base in ../knowledge_base/."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

KB_DIR = Path(__file__).resolve().parents[1] / "knowledge_base"


def split(value: str | None) -> list[str]:
    return [x.strip() for x in (value or "").split(";") if x.strip()]


def _read(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


class KnowledgeBase:
    """All knowledge as dictionaries keyed by ID, plus the indexes the engine needs."""

    def __init__(self, kb_dir: Path | str = KB_DIR):
        d = Path(kb_dir)
        load = lambda name, key: {r[key]: r for r in _read(d / name)}
        self.sources = load("sources.csv", "source_id")
        self.equipment = load("equipment.csv", "equipment_id")
        self.parameters = load("equipment_parameters.csv", "parameter_id")
        self.components = load("components.csv", "component_id")
        self.indicators = load("indicators.csv", "indicator_id")
        self.thresholds = load("thresholds.csv", "threshold_id")
        self.symptoms = load("symptoms.csv", "symptom_id")
        self.faults = load("faults.csv", "fault_id")
        self.causes = load("root_causes.csv", "cause_id")
        self.tests = load("diagnostic_tests.csv", "test_id")
        self.actions = load("maintenance_actions.csv", "action_id")
        self.safety = load("safety_rules.csv", "safety_id")
        self.relationships = load("relationships.csv", "rel_id")
        self.meta = json.loads((d / "kb_meta.json").read_text(encoding="utf-8"))
        self.rules = json.loads((d / "diagnostic_rules.json").read_text(encoding="utf-8"))["rules"]

        self.symptom_by_key = {s["key"]: sid for sid, s in self.symptoms.items()}
        self.parameter_by_name = {p["name"]: pid for pid, p in self.parameters.items()}
        self.indicator_by_name = {i["name"]: iid for iid, i in self.indicators.items()}
        self.thresholds_by_symptom = defaultdict(list)
        for t in self.thresholds.values():
            self.thresholds_by_symptom[t["symptom_id"]].append(t)
        self.rels_by_type = defaultdict(list)
        for r in self.relationships.values():
            self.rels_by_type[r["rel_type"]].append(r)
        self.rules_by_layer = defaultdict(list)
        for r in self.rules:
            self.rules_by_layer[r["layer"]].append(r)

    # ---- name resolution (callers may use IDs or readable names) ----------------------
    def symptom_id(self, key_or_id: str) -> str:
        if key_or_id in self.symptoms:
            return key_or_id
        if key_or_id in self.symptom_by_key:
            return self.symptom_by_key[key_or_id]
        raise KeyError(f"Unknown symptom '{key_or_id}'")

    def parameter_id(self, name_or_id: str) -> str:
        if name_or_id in self.parameters:
            return name_or_id
        if name_or_id in self.parameter_by_name:
            return self.parameter_by_name[name_or_id]
        raise KeyError(f"Unknown equipment parameter '{name_or_id}'")

    def indicator_id(self, name_or_id: str) -> str:
        if name_or_id in self.indicators:
            return name_or_id
        if name_or_id in self.indicator_by_name:
            return self.indicator_by_name[name_or_id]
        raise KeyError(f"Unknown indicator '{name_or_id}'")

    def name(self, entity_id: str) -> str:
        for table, field in ((self.symptoms, "name"), (self.faults, "name"), (self.causes, "name"),
                             (self.tests, "name"), (self.actions, "name"), (self.safety, "name"),
                             (self.components, "name"), (self.indicators, "name"), (self.parameters, "name")):
            if entity_id in table:
                return table[entity_id][field]
        return entity_id
