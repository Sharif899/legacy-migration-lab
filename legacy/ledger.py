"""Legacy payments ledger, written in deliberately old-fashioned style.

This module is the "before" system of the migration lab. It runs on Python 3
so the equivalence harness can execute it, but it is written the way the same
code looked in the Python 2 era: old-style classes, % formatting, bare
excepts, MD5 passwords, string-concatenated SQL, float money, no tests.

Every defect carries a # LEGACY: comment. Do not copy these patterns.
"""

import hashlib
import sqlite3
import time


class Ledger(object):
    """A tiny payments ledger. One table for accounts, one for entries."""

    def __init__(self, db_path=":memory:"):
        # LEGACY: global mutable connection, created in the constructor,
        # shared by every method, never closed.
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS accounts "
            "(id INTEGER PRIMARY KEY, name TEXT, password TEXT, balance REAL)"
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS entries "
            "(id INTEGER PRIMARY KEY, account TEXT, kind TEXT, "
            "amount REAL, other TEXT, ts REAL)"
        )

    def create_account(self, name, password):
        # LEGACY: MD5 with no salt. Fast to brute force, no per-user salt.
        h = hashlib.md5(password.encode("utf-8")).hexdigest()
        try:
            # LEGACY: SQL built by string concatenation. Injectable.
            self.conn.execute(
                "INSERT INTO accounts (name, password, balance) "
                "VALUES ('%s', '%s', 0)" % (name, h)
            )
            self.conn.commit()
        except:
            # LEGACY: bare except swallows the error. A duplicate name
            # fails silently and the caller never finds out.
            pass
        return True

    def _check(self, name, password):
        h = hashlib.md5(password.encode("utf-8")).hexdigest()
        cur = self.conn.execute(
            "SELECT name FROM accounts WHERE name = '%s' "
            "AND password = '%s'" % (name, h)
        )
        return cur.fetchone() is not None

    def deposit(self, name, amount):
        try:
            # LEGACY: float money. 0.10 + 0.20 is 0.30000000000000004.
            self.conn.execute(
                "UPDATE accounts SET balance = balance + %s "
                "WHERE name = '%s'" % (amount, name)
            )
            self.conn.execute(
                "INSERT INTO entries (account, kind, amount, other, ts) "
                "VALUES ('%s', 'deposit', %s, '', %s)"
                % (name, amount, time.time())
            )
            self.conn.commit()
            return True
        except:
            return False

    def transfer(self, frm, to, amount, password):
        if not self._check(frm, password):
            return False
        bal = self.balance(frm)
        if bal < amount:
            return False
        try:
            self.conn.execute(
                "UPDATE accounts SET balance = balance - %s "
                "WHERE name = '%s'" % (amount, frm)
            )
            self.conn.execute(
                "UPDATE accounts SET balance = balance + %s "
                "WHERE name = '%s'" % (amount, to)
            )
            self.conn.execute(
                "INSERT INTO entries (account, kind, amount, other, ts) "
                "VALUES ('%s', 'transfer_out', %s, '%s', %s)"
                % (frm, amount, to, time.time())
            )
            self.conn.execute(
                "INSERT INTO entries (account, kind, amount, other, ts) "
                "VALUES ('%s', 'transfer_in', %s, '%s', %s)"
                % (to, amount, frm, time.time())
            )
            self.conn.commit()
            return True
        except:
            # LEGACY: a failure halfway through leaves the ledger
            # half-updated. No transaction, no rollback.
            return False

    def balance(self, name):
        cur = self.conn.execute(
            "SELECT balance FROM accounts WHERE name = '%s'" % name
        )
        row = cur.fetchone()
        # LEGACY: float money, coerced explicitly.
        return float(row[0]) if row else 0.0

    def statement(self, name):
        cur = self.conn.execute(
            "SELECT kind, amount, other FROM entries "
            "WHERE account = '%s' ORDER BY id" % name
        )
        return [
            {"kind": k, "amount": a, "other": o} for (k, a, o) in cur.fetchall()
        ]
