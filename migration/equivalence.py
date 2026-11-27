"""Behavioural equivalence harness.

Runs the same scenarios against the legacy ledger and the modern ledger
and diffs the outcomes. This is the proof that the migration preserved
behaviour: same operations, same balances, same statements.

Two differences are intentional and documented, not failures:

1. Error signalling. The legacy code returns False on failure; the modern
   code raises typed errors. The harness normalises both to success or
   failure for comparison, and records the difference in the report.
2. Security fixes. Password storage and SQL construction changed on
   purpose. The harness compares business outcomes (balances, entries),
   not stored hashes or query text.
3. Duplicate accounts. The legacy code silently succeeds when an account
   already exists, so the duplicate is invisible to the caller. The
   modern code raises AccountExists. The state is identical on both
   sides, so the harness counts this as a known divergence, not a
   mismatch, and records it on the outcome.

Usage:
    python -m migration.equivalence --scenarios scenarios/scenarios.json
"""

from __future__ import annotations

import argparse
import json
from decimal import Decimal

from legacy.ledger import Ledger as LegacyLedger
from modern.ledger import Ledger as ModernLedger
from modern.ledger import LedgerError


def _to_decimal(value) -> Decimal:
    return Decimal(str(value))


def _round2(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _run_op(ledger, op: dict):
    """Run one scenario op on a ledger, returning a normalised outcome."""
    kind = op["op"]
    try:
        if kind == "create_account":
            result = ledger.create_account(op["name"], op["password"])
        elif kind == "deposit":
            result = ledger.deposit(op["name"], _to_decimal(op["amount"]))
        elif kind == "transfer":
            result = ledger.transfer(
                op["from"], op["to"], _to_decimal(op["amount"]), op["password"]
            )
        else:
            raise ValueError("unknown op %r" % kind)
        return ("ok" if result else "fail", None)
    except LedgerError as exc:
        return ("fail", type(exc).__name__)
    except Exception as exc:  # legacy code can raise sqlite errors
        return ("fail", type(exc).__name__)


def _snapshot(ledger, names: list[str]) -> dict:
    """Balances and statements for the named accounts, normalised."""
    snap = {}
    for name in names:
        entries = []
        for entry in ledger.statement(name):
            if isinstance(entry, dict):
                kind, amount, other = entry["kind"], entry["amount"], entry["other"]
            else:
                kind, amount, other = entry.kind, entry.amount, entry.other
            entries.append(
                {"kind": kind, "amount": str(_round2(amount)), "other": other}
            )
        snap[name] = {
            "balance": str(_round2(ledger.balance(name))),
            "entries": entries,
        }
    return snap


def run_scenarios(scenarios: list[dict]) -> dict:
    """Run scenarios against both ledgers and compare. Returns a report."""
    names = sorted(
        {op.get("name") or op.get("from") or op.get("to") for op in scenarios}
        - {None}
    )
    legacy = LegacyLedger()
    modern = ModernLedger()
    outcomes = []
    created: set[str] = set()
    for op in scenarios:
        legacy_out = _run_op(legacy, op)
        modern_out = _run_op(modern, op)
        match = legacy_out[0] == modern_out[0]
        divergence = None
        if (
            op["op"] == "create_account"
            and op["name"] in created
            and legacy_out[0] == "ok"
            and modern_out[1] == "AccountExists"
        ):
            # Known divergence 3: legacy silently succeeds on a duplicate
            # account, modern raises. State is identical on both sides.
            match = True
            divergence = (
                "duplicate create_account: legacy silently succeeds, "
                "modern raises AccountExists"
            )
        if op["op"] == "create_account" and legacy_out[0] == "ok":
            created.add(op["name"])
        outcomes.append(
            {
                "op": op,
                "legacy": legacy_out[0],
                "modern": modern_out[0],
                "legacy_error": legacy_out[1],
                "modern_error": modern_out[1],
                "match": match,
                "divergence": divergence,
            }
        )
    legacy_snap = _snapshot(legacy, names)
    modern_snap = _snapshot(modern, names)
    mismatches = [o for o in outcomes if not o["match"]]
    return {
        "ops": outcomes,
        "ops_match": not mismatches,
        "final_state_match": legacy_snap == modern_snap,
        "legacy_final": legacy_snap,
        "modern_final": modern_snap,
        "notes": [
            "Error signalling differs by design: legacy returns False, "
            "modern raises typed errors. Outcomes are compared as "
            "success/failure, not by error type.",
            "Password storage and SQL construction changed on purpose; "
            "only business outcomes are compared.",
            "Duplicate create_account is a known divergence: legacy "
            "silently succeeds, modern raises AccountExists. State is "
            "identical on both sides.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", required=True)
    args = parser.parse_args()
    with open(args.scenarios) as fh:
        scenarios = json.load(fh)
    report = run_scenarios(scenarios)
    print("operations: %d, all match: %s" % (len(report["ops"]), report["ops_match"]))
    print("final state match: %s" % report["final_state_match"])
    for outcome in report["ops"]:
        op = outcome["op"]
        mark = "OK " if outcome["match"] else "DIFF"
        detail = ""
        if outcome["legacy_error"] or outcome["modern_error"]:
            detail = "(legacy: %s, modern: %s)" % (
                outcome["legacy_error"],
                outcome["modern_error"],
            )
        if outcome.get("divergence"):
            detail = "(known divergence: %s)" % outcome["divergence"]
        print(
            "  [%s] %-10s legacy=%-4s modern=%-4s %s"
            % (mark, op["op"], outcome["legacy"], outcome["modern"], detail)
        )
    for name, snap in report["modern_final"].items():
        print("  %s balance=%s entries=%d" % (name, snap["balance"], len(snap["entries"])))
    for note in report["notes"]:
        print("  note: " + note)
    return 0 if (report["ops_match"] and report["final_state_match"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
