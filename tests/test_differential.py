"""Randomised differential tests: both ledgers, same random stream."""

from migration.differential import generate_ops
from migration.equivalence import run_scenarios


def test_random_stream_matches():
    scenarios = generate_ops(200, seed=7)
    report = run_scenarios(scenarios)
    assert report["ops_match"] is True
    assert report["final_state_match"] is True


def test_second_seed_matches():
    scenarios = generate_ops(150, seed=42)
    report = run_scenarios(scenarios)
    assert report["ops_match"] is True
    assert report["final_state_match"] is True
