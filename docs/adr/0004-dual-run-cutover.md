# ADR 0004: Cut over by dual-running, not by a flag flip

## Status

Accepted.

## Context

A migration that swaps implementations in one deploy can only be
validated after it is live. If the modern ledger has a behavioural
difference the fixed scenarios missed, the first sign is wrong balances
in production. The equivalence harness proves the fixed scenarios, but
fixed scenarios only cover what someone thought to write down.

## Decision

Dual-run both ledgers on the same inputs for a full period before
cutover, compare every outcome with the differential tester
(`migration/differential.py`), and cut over in stages: reads first, then
writes, then retire the legacy module.

## Consequences

- The differential tester generates random operation streams with a
  fixed seed, so any mismatch is reproducible. A mismatch stops the
  cutover, it does not get investigated live.
- Dual-running doubles write load during the period. For this ledger
  that is acceptable; for a high-volume system the period would be
  shortened or the comparison sampled.
- The legacy module stays in the repo until retirement, so rollback is
  a configuration change, not a redeploy. The one irreversible step is
  the password re-hash, recorded in the migration report.
- Observability during dual-run is the comparison itself: mismatch
  count, mismatch rate per operation type, and the first mismatching
  operation. If the mismatch rate is zero across the whole period, the
  cutover proceeds. Any non-zero rate blocks it.
