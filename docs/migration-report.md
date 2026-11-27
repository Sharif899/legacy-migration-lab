# Migration report: payments ledger, Python 2 style to Python 3.12

## 1. Inventory

| Item | Detail |
| --- | --- |
| System | Tiny payments ledger, one module, `legacy/ledger.py` |
| Language | Python 2 style code, running on Python 3 for the lab |
| Storage | SQLite, two tables (`accounts`, `entries`) |
| Public surface | `create_account`, `deposit`, `transfer`, `balance`, `statement` |
| Dependencies | Standard library only |
| Tests | None |
| Callers | None in this lab; the harness is the only caller |

## 2. Risk register

| Risk | Severity | Evidence |
| --- | --- | --- |
| MD5 password hashing, no salt | High | `hashlib.md5` in `create_account` and `_check` |
| SQL injection via string concatenation | High | Every query built with `%` formatting |
| Float money, rounding error | High | `0.10 + 0.20` is `0.30000000000000004` |
| Bare `except:` hides failures | Medium | Duplicate accounts fail silently |
| No transaction, partial updates | Medium | `transfer` can debit without crediting |
| No tests, no types | Medium | No way to prove a change is safe |
| Global mutable connection | Low | One connection shared by all methods |

## 3. Migration decisions

| Decision | Choice | Reason |
| --- | --- | --- |
| Money type | `Decimal`, two places | Exact decimal arithmetic; floats cannot represent money |
| Password hashing | PBKDF2-HMAC-SHA256, 200,000 rounds, per-account salt | Current standard for password storage; MD5 is broken |
| SQL | Parameterised queries everywhere | Removes the injection class entirely |
| Errors | Typed exceptions, not `False` | Callers can tell *why* an operation failed |
| Transactions | `with self._conn:` around every write | A failed transfer rolls back instead of half-applying |
| Public API | Unchanged method names and signatures | Existing callers keep working; only error signalling changes |
| Auth tokens | HMAC-signed tokens, 1 hour expiry | Stops raw passwords travelling with every call |

## 4. Phased plan

1. **Assess.** Inventory, risk register, scenario capture. No code changes.
2. **Isolate.** Freeze the legacy module. Write the shared scenarios and
   the equivalence harness against the legacy code first, so the baseline
   is recorded before anything moves.
3. **Migrate.** Rewrite module by module behind the same public API,
   keeping the legacy module in place for comparison.
4. **Validate.** Run the equivalence harness. Every scenario must match,
   and the modern test suite must pass. Any mismatch stops the cutover.
5. **Cutover.** Dual-run both ledgers on the same inputs, compare outputs
   daily, then switch reads to the modern ledger, then writes.
6. **Retire.** Delete the legacy module only after a full dual-run period
   with zero mismatches.

## 5. Validation evidence

- `pytest -q`: full suite green (modern ledger, equivalence, scanner, evaluator).
- `python -m migration.equivalence`: all 9 scenarios match, final state
  matches (balances and statements identical to two decimal places).
- `python -m migration.idiom_scan`: legacy module flags MD5, string SQL,
  bare excepts; modern module flags nothing.
- `python -m migration.differential --ops 200 --seed 7`: zero mismatches
  across 200 random operations, final state matches. The differential
  run caught one real divergence during development: the legacy code
  silently succeeds on a duplicate account while the modern code raises
  `AccountExists`. That is now a documented known divergence in the
  harness (state identical on both sides), not a hidden difference.
- `python -m migration.ai_eval`: bad sample diff scores below the pass
  mark with findings; good sample diff passes.

## 6. Rollback

The legacy module is kept in the repo until retirement. Rollback is a
configuration change: point callers back at `legacy.Ledger`. Balances are
stored as text in the modern schema and as floats in the legacy schema, so
a rollback script converts `TEXT` balances back to `REAL` with two-decimal
rounding, and re-hashes are not needed because the legacy module stores
MD5 hashes separately. The one irreversible step is the password
re-hash: accounts created after cutover have PBKDF2 hashes the legacy
code cannot verify, so those accounts must reset their passwords on
rollback. That is recorded here rather than discovered during an incident.

## 7. Threat model

| Threat | Before | After |
| --- | --- | --- |
| Stolen database, offline password cracking | MD5, no salt, one rainbow table cracks all accounts | PBKDF2, 200,000 rounds, per-account salt |
| SQL injection through account names | String-concatenated queries | Parameterised queries everywhere |
| Timing attack on password comparison | `==` on hashes | `hmac.compare_digest` |
| Token theft | Raw passwords passed with every call | HMAC-signed tokens, 1 hour expiry |
| Partial update on failure | Debit without credit, no rollback | One transaction per operation |

Residual risks: accounts that never log in after cutover keep MD5 hashes
until a forced reset; the token secret must be stored outside the
codebase, never committed; the 1 hour token expiry is a trade-off between
usability and exposure, revisit if sessions need to last longer.

## 8. Observability during dual-run

The comparison is the monitoring. During the dual-run period, track:

- mismatch count and mismatch rate per operation type
- the first mismatching operation (seed + index, reproducible)
- balance drift per account (modern minus legacy, should be zero)
- error-type divergence (legacy `False` vs modern typed error is
  expected; anything else is a mismatch)

Cutover proceeds only at zero mismatches across the whole period. Any
non-zero rate blocks it and the differential tester reproduces the
failing stream from its seed.
