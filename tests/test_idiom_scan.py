"""Tests for the Python 2 idiom scanner."""

from migration.idiom_scan import scan_file


def _rules(path):
    return {finding.rule for finding in scan_file(path)}


def test_legacy_ledger_flagged():
    rules = _rules("legacy/ledger.py")
    assert "MD5_HASH" in rules
    assert "STRING_SQL" in rules
    assert "BARE_EXCEPT" in rules
    assert "FLOAT_MONEY" in rules


def test_modern_ledger_clean():
    assert scan_file("modern/ledger.py") == []


def test_py2_sample_flagged():
    rules = _rules("migration/samples/legacy_snippet_py2.py")
    for rule in [
        "PY2_PRINT",
        "PY2_XRANGE",
        "PY2_ITERITEMS",
        "PY2_RAW_INPUT",
        "PY2_HAS_KEY",
        "PY2_UNICODE",
        "PY2_LONG",
    ]:
        assert rule in rules
