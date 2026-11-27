"""Tests for the behavioural equivalence harness."""

import json

from migration.equivalence import run_scenarios


def _load_scenarios():
    with open("scenarios/scenarios.json") as fh:
        return json.load(fh)


def test_scenarios_match():
    report = run_scenarios(_load_scenarios())
    assert report["ops_match"] is True
    assert report["final_state_match"] is True
    assert report["modern_final"]["ada"]["balance"] == "100.20"
    assert report["modern_final"]["bob"]["balance"] == "0.10"


def test_failed_ops_match():
    report = run_scenarios(_load_scenarios())
    failed = [op for op in report["ops"] if op["legacy"] == "fail"]
    # Insufficient funds and the wrong password. Both must fail on both.
    assert len(failed) == 2
    assert all(op["modern"] == "fail" for op in failed)
    assert all(op["match"] for op in report["ops"])


def test_duplicate_create_is_a_known_divergence_not_a_mismatch():
    """Legacy silently succeeds on a duplicate account, modern raises.

    The harness must record this as a known divergence and still match,
    because the state is identical on both sides.
    """
    scenarios = [
        {"op": "create_account", "name": "ada", "password": "s3cret"},
        {"op": "create_account", "name": "ada", "password": "s3cret"},
    ]
    report = run_scenarios(scenarios)
    assert report["ops_match"] is True
    assert report["final_state_match"] is True
    duplicate = report["ops"][1]
    assert duplicate["legacy"] == "ok"
    assert duplicate["modern_error"] == "AccountExists"
    assert duplicate["divergence"] is not None
