"""Modern payments ledger: same behaviour as legacy, current Python.

This is the "after" system. It keeps the legacy ledger's public method
names and business rules exactly, so the equivalence harness can run the
same scenarios against both, and changes only what the migration report
says must change:

- money is Decimal, never float
- passwords are PBKDF2 with a per-account salt, never MD5
- SQL is parameterised, never string-concatenated
- failures raise typed errors instead of returning False
- every operation runs in a transaction, so a failure rolls back
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import sqlite3
import time
from dataclasses import dataclass
from decimal import Decimal

log = logging.getLogger(__name__)

_PBKDF2_ITERATIONS = 200_000


class LedgerError(Exception):
    """Base class for ledger errors."""


class AccountNotFound(LedgerError):
    """The named account does not exist."""


class AccountExists(LedgerError):
    """An account with that name already exists."""


class AuthenticationFailed(LedgerError):
    """The password did not match."""


class InsufficientFunds(LedgerError):
    """The account balance is lower than the amount."""


class InvalidAmount(LedgerError):
    """The amount is not a positive number with at most two decimals."""


@dataclass(frozen=True)
class Entry:
    """One ledger entry."""

    kind: str
    amount: Decimal
    other: str = ""


def _check_amount(amount: Decimal) -> Decimal:
    """Validate an amount: positive, at most two decimal places."""
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    if amount <= 0:
        raise InvalidAmount("amount must be positive, got %s" % amount)
    if -amount.as_tuple().exponent > 2:
        raise InvalidAmount("amount must have at most two decimals")
    return amount


def _hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )


class Ledger:
    """A tiny payments ledger with explicit errors and Decimal money."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS accounts "
            "(id INTEGER PRIMARY KEY, name TEXT UNIQUE, "
            "password_hash BLOB, salt BLOB, balance TEXT)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS entries "
            "(id INTEGER PRIMARY KEY, account TEXT, kind TEXT, "
            "amount TEXT, other TEXT, ts REAL)"
        )

    def create_account(self, name: str, password: str) -> bool:
        salt = secrets.token_bytes(16)
        password_hash = _hash_password(password, salt)
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO accounts (name, password_hash, salt, balance) "
                    "VALUES (?, ?, ?, ?)",
                    (name, password_hash, salt, "0.00"),
                )
        except sqlite3.IntegrityError:
            raise AccountExists("account %r already exists" % name)
        log.info("created account %s", name)
        return True

    def _authenticate(self, name: str, password: str) -> None:
        row = self._conn.execute(
            "SELECT password_hash, salt FROM accounts WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            raise AccountNotFound("no account named %r" % name)
        stored_hash, salt = row
        if not hmac.compare_digest(_hash_password(password, salt), stored_hash):
            raise AuthenticationFailed("wrong password for %r" % name)

    def deposit(self, name: str, amount: Decimal) -> bool:
        amount = _check_amount(amount)
        with self._conn:
            row = self._conn.execute(
                "SELECT balance FROM accounts WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                raise AccountNotFound("no account named %r" % name)
            new_balance = Decimal(row[0]) + amount
            self._conn.execute(
                "UPDATE accounts SET balance = ? WHERE name = ?",
                (str(new_balance), name),
            )
            self._conn.execute(
                "INSERT INTO entries (account, kind, amount, other, ts) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, "deposit", str(amount), "", time.time()),
            )
        return True

    def transfer(
        self, frm: str, to: str, amount: Decimal, password: str
    ) -> bool:
        amount = _check_amount(amount)
        self._authenticate(frm, password)
        with self._conn:
            from_row = self._conn.execute(
                "SELECT balance FROM accounts WHERE name = ?", (frm,)
            ).fetchone()
            to_row = self._conn.execute(
                "SELECT balance FROM accounts WHERE name = ?", (to,)
            ).fetchone()
            if to_row is None:
                raise AccountNotFound("no account named %r" % to)
            if Decimal(from_row[0]) < amount:
                raise InsufficientFunds(
                    "%s has %s, cannot send %s" % (frm, from_row[0], amount)
                )
            self._conn.execute(
                "UPDATE accounts SET balance = ? WHERE name = ?",
                (str(Decimal(from_row[0]) - amount), frm),
            )
            self._conn.execute(
                "UPDATE accounts SET balance = ? WHERE name = ?",
                (str(Decimal(to_row[0]) + amount), to),
            )
            self._conn.execute(
                "INSERT INTO entries (account, kind, amount, other, ts) "
                "VALUES (?, ?, ?, ?, ?)",
                (frm, "transfer_out", str(amount), to, time.time()),
            )
            self._conn.execute(
                "INSERT INTO entries (account, kind, amount, other, ts) "
                "VALUES (?, ?, ?, ?, ?)",
                (to, "transfer_in", str(amount), frm, time.time()),
            )
        return True

    def balance(self, name: str) -> Decimal:
        row = self._conn.execute(
            "SELECT balance FROM accounts WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            return Decimal("0.00")
        return Decimal(row[0])

    def statement(self, name: str) -> list[Entry]:
        rows = self._conn.execute(
            "SELECT kind, amount, other FROM entries "
            "WHERE account = ? ORDER BY id",
            (name,),
        ).fetchall()
        return [Entry(kind=k, amount=Decimal(a), other=o) for (k, a, o) in rows]

    def make_token(self, name: str, password: str, secret: bytes) -> str:
        """Return an HMAC-signed token for an authenticated account.

        This replaces the legacy system's habit of passing raw passwords
        around. The token proves the holder authenticated, without
        carrying the password itself.
        """
        self._authenticate(name, password)
        stamp = str(int(time.time()))
        mac = hmac.new(secret, (name + ":" + stamp).encode(), "sha256")
        return "%s:%s:%s" % (name, stamp, mac.hexdigest())

    def verify_token(self, token: str, secret: bytes, max_age: int = 3600) -> str:
        """Verify a token from make_token and return the account name."""
        try:
            name, stamp, mac = token.split(":")
        except ValueError:
            raise AuthenticationFailed("malformed token")
        expected = hmac.new(
            secret, (name + ":" + stamp).encode(), "sha256"
        ).hexdigest()
        if not hmac.compare_digest(mac, expected):
            raise AuthenticationFailed("bad token signature")
        if int(time.time()) - int(stamp) > max_age:
            raise AuthenticationFailed("token expired")
        return name
