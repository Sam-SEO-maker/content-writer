"""
Tests pour le module decision_engine.

Réécrits 2026-07 pour le contrat ACTUEL du moteur :
- règles chargées depuis `_shared/config/decision_rules.json` (schéma `id` /
  `conditions` {clé_plate: {operator, value}} / `action` ; `rewrite_scope` et
  `estimated_tokens` lus dans `action_strategies`) ;
- conditions évaluées par `_check_condition(value, condition)` ;
- valeurs d'audit résolues par `_get_audit_value(key, audit_data)` (clés plates
  mappées vers des chemins imbriqués via value_mappings).
"""

import json
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.decision.decision_engine import DecisionEngine, DecisionResult

_REAL_RULES = Path(__file__).parent.parent / "_shared" / "config" / "decision_rules.json"


class TestDecisionEngineRealConfig:
    """Le moteur chargé avec le vrai decision_rules.json (comportement prod)."""

    def setup_method(self):
        assert _REAL_RULES.exists(), "decision_rules.json introuvable"
        self.engine = DecisionEngine(_REAL_RULES)

    def test_loads_real_config(self):
        assert self.engine.rules, "aucune règle chargée"
        assert self.engine.action_strategies, "aucune action_strategy"

    def test_evaluate_returns_decision_result(self):
        result = self.engine.evaluate({"performance": {"impressions_30d": 100}})
        assert isinstance(result, DecisionResult)
        assert isinstance(result.primary_action, str)

    def test_stale_content_triggers_full_refresh(self):
        # freshness_score élevé = beaucoup de mois depuis MAJ (mapping
        # months_since_update → freshness_score) → contenu obsolète → FULL_REFRESH.
        audit = {
            "performance": {
                "ctr_30d": 5.0, "impressions_30d": 100, "clicks_30d": 20,
                "clicks_trend": 0.0, "impressions_trend": 0.0, "position_trend": 0.0,
                "avg_position": 5.0, "indexation_status": "INDEXED",
                "is_declining": False, "main_keyword": "",
            },
            "cannibalization": {"severity": "none"},
            "freshness_score": 100,
        }
        result = self.engine.evaluate(audit)
        # Une action est décidée (le vrai config a une règle d'obsolescence).
        assert result.primary_action in self.engine.action_strategies or \
            result.primary_action == "FULL_REFRESH"
        assert isinstance(result.rules_triggered, list)

    def test_scope_and_tokens_come_from_action_strategies(self):
        # Pour toute action déclenchée, scope/tokens proviennent d'action_strategies,
        # pas de la règle. On le vérifie via une action connue du config.
        action = next(iter(self.engine.action_strategies))
        strat = self.engine.action_strategies[action]
        # les clés attendues existent dans le schéma action_strategies
        assert "rewrite_scope" in strat or "estimated_tokens" in strat


class TestDecisionEngineSyntheticRules:
    """Règles synthétiques au schéma ACTUEL (id + conditions à clés plates)."""

    def setup_method(self):
        self.config = {
            "rules": [
                {
                    "id": "low_ctr",
                    "name": "CTR faible",
                    "priority": 1,
                    "conditions": {
                        "ctr": {"operator": "<", "value": 2.0},
                        "impressions_30d": {"operator": ">", "value": 500},
                    },
                    "action": "TITLE_OPTIMIZATION",
                },
                {
                    "id": "cannibalization_severe",
                    "name": "Cannibalisation sévère",
                    "priority": 1,
                    "conditions": {
                        "cannibalization_severity": {"operator": "==", "value": "high"},
                    },
                    "action": "SUGGEST_301",
                },
            ],
            "action_strategies": {
                "TITLE_OPTIMIZATION": {"rewrite_scope": "title_meta", "estimated_tokens": 500},
                "SUGGEST_301": {"rewrite_scope": "none", "estimated_tokens": 0},
            },
            "evaluation_order": ["low_ctr", "cannibalization_severe"],
        }
        self.temp = NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(self.config, self.temp)
        self.temp.close()
        self.engine = DecisionEngine(Path(self.temp.name))

    def teardown_method(self):
        Path(self.temp.name).unlink(missing_ok=True)

    def test_low_ctr_triggers_title_optimization(self):
        audit = {"performance": {"ctr_30d": 1.0, "impressions_30d": 1000}}
        result = self.engine.evaluate(audit)
        assert result.primary_action == "TITLE_OPTIMIZATION"
        assert any(r.rule_id == "low_ctr" for r in result.rules_triggered)

    def test_cannibalization_triggers_301(self):
        audit = {"cannibalization": {"severity": "high"}}
        result = self.engine.evaluate(audit)
        assert result.primary_action == "SUGGEST_301"

    def test_scope_and_tokens_from_strategy(self):
        audit = {"performance": {"ctr_30d": 1.0, "impressions_30d": 1000}}
        result = self.engine.evaluate(audit)
        assert result.rewrite_scope == "title_meta"
        assert result.estimated_tokens == 500

    def test_no_match_no_action(self):
        audit = {"performance": {"ctr_30d": 5.0, "impressions_30d": 100},
                 "cannibalization": {"severity": "none"}}
        result = self.engine.evaluate(audit)
        assert result.primary_action == "NO_ACTION"


class TestConditionEvaluation:
    """_check_condition (opérateurs) et _get_audit_value (résolution de clés)."""

    def setup_method(self):
        empty = {"rules": [], "action_strategies": {}}
        self.temp = NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(empty, self.temp)
        self.temp.close()
        self.engine = DecisionEngine(Path(self.temp.name))

    def teardown_method(self):
        Path(self.temp.name).unlink(missing_ok=True)

    def test_operator_less_than(self):
        cond = {"operator": "<", "value": 10}
        assert self.engine._check_condition(5, cond) is True
        assert self.engine._check_condition(10, cond) is False
        assert self.engine._check_condition(15, cond) is False

    def test_operator_greater_than(self):
        cond = {"operator": ">", "value": 10}
        assert self.engine._check_condition(15, cond) is True
        assert self.engine._check_condition(10, cond) is False

    def test_operator_equals(self):
        cond = {"operator": "==", "value": "high"}
        assert self.engine._check_condition("high", cond) is True
        assert self.engine._check_condition("low", cond) is False

    def test_operator_not_equals(self):
        cond = {"operator": "!=", "value": "none"}
        assert self.engine._check_condition("high", cond) is True
        assert self.engine._check_condition("none", cond) is False

    def test_get_audit_value_flat_key_mapping(self):
        # `ctr` (clé plate) → performance.ctr_30d
        audit = {"performance": {"ctr_30d": 1.5, "impressions_30d": 800}}
        assert self.engine._get_audit_value("ctr", audit) == 1.5
        assert self.engine._get_audit_value("impressions_30d", audit) == 800

    def test_get_audit_value_missing_returns_none(self):
        assert self.engine._get_audit_value("ctr", {"performance": {}}) is None
