# ADR 0003: Failures raise typed errors instead of returning False

## Status

Accepted.

## Context

The legacy ledger returns `False` for every failure: wrong password,
missing account, insufficient funds, database error. Callers cannot tell
these apart, so they cannot respond correctly, and the bare `except:`
clauses hide the database errors entirely. This is also why duplicate
accounts fail silently.

## Decision

A typed error hierarchy under `LedgerError`: `AccountNotFound`,
`AccountExists`, `AuthenticationFailed`, `InsufficientFunds`,
`InvalidAmount`. Success returns `True` as before.

## Consequences

- Callers can branch on failure type: retry on a transient database
  error, ask the user to check their password on `AuthenticationFailed`,
  show a balance on `InsufficientFunds`.
- The change is deliberately the one breaking change in the public API.
  It is documented in the migration report and in the equivalence
  harness, which compares outcomes as success or failure rather than by
  error type, because the two systems signal failure differently.
- Bare `except:` is gone. The only place an exception is caught and
  translated is `create_account`, which converts an integrity error into
  `AccountExists`, and only that error.
- Logging was added at the boundary (`create_account`), not inside every
  method, so the ledger stays quiet on its hot path and the operator
  still gets an audit trail for account creation.
