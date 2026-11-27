# ADR 0001: Money is Decimal, not float and not integer cents

## Status

Accepted.

## Context

The legacy ledger stores balances as SQLite `REAL` and does arithmetic in
`float`. `0.10 + 0.20` is `0.30000000000000004`, so balances drift from what
a statement shows. The migration had three options: keep floats and round
at display time, store integer minor units (cents), or use `Decimal`.

## Decision

Store money as `Decimal` with two places, serialised as text in SQLite.

## Consequences

- Arithmetic is exact for two-decimal money. The equivalence harness
  proves it: the `0.10 + 0.20` case that the legacy code gets wrong now
  reads exactly `0.30`.
- `Decimal` carries its own validation. `_check_amount` rejects negative
  amounts and amounts with more than two decimals at the boundary, instead
  of letting bad values reach storage.
- Integer cents would also have been exact, and is the right choice for a
  high-throughput ledger. It was rejected here because it pushes the
  decimal-point concern into every caller and every display path, and the
  migration's goal was to keep the public API identical. For a ledger
  doing millions of operations a second, revisit this decision.
- Rounding at display time was rejected: it hides drift instead of
  removing it, and two systems rounding differently is exactly how
  migration mismatches appear.
