"""Ledger invariants: properties that must hold whatever the history is.

These are the checks a senior reviewer looks for first, because they do
not depend on any particular scenario. They hold for every sequence of
valid operations.
"""

from decimal import Decimal

import pytest

from modern.ledger import (
    AuthenticationFailed,
    InsufficientFunds,
    Ledger,
)


def test_money_is_conserved_by_transfers():
    """Transfers move money, they never create or destroy it."""
    ledger = Ledger()
    ledger.create_account("ada", "s3cret")
    ledger.create_account("bob", "hunter2")
    ledger.create_account("carol", "p4ssw0rd")
    ledger.deposit("ada", Decimal("1000.00"))
    ledger.deposit("bob", Decimal("500.00"))
    ledger.deposit("carol", Decimal("250.00"))
    total_before = sum(
        (ledger.balance(name) for name in ("ada", "bob", "carol")),
        Decimal("0"),
    )
    ledger.transfer("ada", "bob", Decimal("123.45"), "s3cret")
    ledger.transfer("bob", "carol", Decimal("67.89"), "hunter2")
    ledger.transfer("carol", "ada", Decimal("10.01"), "p4ssw0rd")
    total_after = sum(
        (ledger.balance(name) for name in ("ada", "bob", "carol")),
        Decimal("0"),
    )
    assert total_after == total_before == Decimal("1750.00")


def test_statement_sums_match_balance():
    """Every balance equals the sum of that account's statement entries."""
    ledger = Ledger()
    ledger.create_account("ada", "s3cret")
    ledger.create_account("bob", "hunter2")
    ledger.deposit("ada", Decimal("200.00"))
    ledger.transfer("ada", "bob", Decimal("75.50"), "s3cret")
    ledger.deposit("bob", Decimal("0.10"))
    for name in ("ada", "bob"):
        entries = ledger.statement(name)
        signed = sum(
            (
                entry.amount
                if entry.kind in ("deposit", "transfer_in")
                else -entry.amount
            )
            for entry in entries
        )
        assert signed == ledger.balance(name)


def test_failed_transfer_leaves_state_unchanged():
    """A failed operation is atomic: no partial debit, no stray entry."""
    ledger = Ledger()
    ledger.create_account("ada", "s3cret")
    ledger.create_account("bob", "hunter2")
    ledger.deposit("ada", Decimal("50.00"))
    with pytest.raises(InsufficientFunds):
        ledger.transfer("ada", "bob", Decimal("500.00"), "s3cret")
    with pytest.raises(AuthenticationFailed):
        ledger.transfer("ada", "bob", Decimal("10.00"), "wrong")
    assert ledger.balance("ada") == Decimal("50.00")
    assert ledger.balance("bob") == Decimal("0.00")
    assert ledger.statement("ada") == [
        entry for entry in ledger.statement("ada") if entry.kind == "deposit"
    ]
    assert ledger.statement("bob") == []
