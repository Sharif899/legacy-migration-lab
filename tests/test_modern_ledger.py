"""Tests for the modern ledger."""

from decimal import Decimal

import pytest

from modern.ledger import (
    AccountExists,
    AccountNotFound,
    AuthenticationFailed,
    InsufficientFunds,
    InvalidAmount,
    Ledger,
)


def test_create_deposit_balance():
    ledger = Ledger()
    assert ledger.create_account("ada", "s3cret") is True
    ledger.deposit("ada", Decimal("100.00"))
    assert ledger.balance("ada") == Decimal("100.00")


def test_duplicate_account():
    ledger = Ledger()
    ledger.create_account("ada", "s3cret")
    with pytest.raises(AccountExists):
        ledger.create_account("ada", "other")


def test_transfer_and_statement():
    ledger = Ledger()
    ledger.create_account("ada", "s3cret")
    ledger.create_account("bob", "hunter2")
    ledger.deposit("ada", Decimal("100.00"))
    assert ledger.transfer("ada", "bob", Decimal("33.33"), "s3cret") is True
    assert ledger.balance("ada") == Decimal("66.67")
    assert ledger.balance("bob") == Decimal("33.33")
    statement = ledger.statement("ada")
    assert [entry.kind for entry in statement] == ["deposit", "transfer_out"]
    assert statement[1].amount == Decimal("33.33")
    assert statement[1].other == "bob"


def test_wrong_password():
    ledger = Ledger()
    ledger.create_account("ada", "s3cret")
    ledger.create_account("bob", "hunter2")
    with pytest.raises(AuthenticationFailed):
        ledger.transfer("ada", "bob", Decimal("1.00"), "wrong")


def test_insufficient_funds():
    ledger = Ledger()
    ledger.create_account("ada", "s3cret")
    ledger.create_account("bob", "hunter2")
    with pytest.raises(InsufficientFunds):
        ledger.transfer("ada", "bob", Decimal("1.00"), "s3cret")


def test_unknown_account():
    ledger = Ledger()
    assert ledger.balance("ghost") == Decimal("0.00")
    with pytest.raises(AccountNotFound):
        ledger.deposit("ghost", Decimal("1.00"))


def test_invalid_amounts():
    ledger = Ledger()
    ledger.create_account("ada", "s3cret")
    with pytest.raises(InvalidAmount):
        ledger.deposit("ada", Decimal("0"))
    with pytest.raises(InvalidAmount):
        ledger.deposit("ada", Decimal("-5.00"))
    with pytest.raises(InvalidAmount):
        ledger.deposit("ada", Decimal("1.234"))


def test_decimal_precision():
    # 0.10 + 0.20 is 0.30000000000000004 in float. Decimal gets it right.
    ledger = Ledger()
    ledger.create_account("bob", "hunter2")
    ledger.deposit("bob", Decimal("0.10"))
    ledger.deposit("bob", Decimal("0.20"))
    assert ledger.balance("bob") == Decimal("0.30")


def test_token_round_trip():
    ledger = Ledger()
    ledger.create_account("ada", "s3cret")
    token = ledger.make_token("ada", "s3cret", b"test-secret")
    assert ledger.verify_token(token, b"test-secret") == "ada"


def test_token_tampered():
    ledger = Ledger()
    ledger.create_account("ada", "s3cret")
    token = ledger.make_token("ada", "s3cret", b"test-secret")
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    with pytest.raises(AuthenticationFailed):
        ledger.verify_token(tampered, b"test-secret")


def test_token_expired():
    ledger = Ledger()
    ledger.create_account("ada", "s3cret")
    token = ledger.make_token("ada", "s3cret", b"test-secret")
    with pytest.raises(AuthenticationFailed):
        ledger.verify_token(token, b"test-secret", max_age=-1)
