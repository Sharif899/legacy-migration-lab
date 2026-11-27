"""Tests for the AI migration evaluator."""

from migration.ai_eval import (
    EXPECTED_FUNCTIONS,
    EXPECTED_MODULES,
    evaluate_diff,
)


def _load(name):
    with open("migration/samples/" + name) as fh:
        return fh.read()


def test_bad_diff_fails():
    evaluation = evaluate_diff(
        _load("ai_migration_bad.diff"), EXPECTED_MODULES, EXPECTED_FUNCTIONS
    )
    assert evaluation.verdict == "FAIL"
    assert evaluation.total < 60
    assert any("MD5" in finding for finding in evaluation.findings)
    assert any("secret" in finding.lower() for finding in evaluation.findings)


def test_good_diff_passes():
    evaluation = evaluate_diff(
        _load("ai_migration_good.diff"), EXPECTED_MODULES, EXPECTED_FUNCTIONS
    )
    assert evaluation.verdict == "PASS"
    assert evaluation.total >= 80
