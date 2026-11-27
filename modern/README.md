# Modern ledger

The "after" system. Same public method names and business rules as
`legacy/ledger.py`, so the equivalence harness can run the same scenarios
against both. What changed is exactly what the migration report said had
to change:

- money is `Decimal`, never `float`
- passwords are PBKDF2 with a per-account salt, never MD5
- SQL is parameterised, never string-concatenated
- failures raise typed errors (`AccountNotFound`, `AuthenticationFailed`,
  `InsufficientFunds`, `InvalidAmount`) instead of returning `False`
- every operation runs in a transaction, so a failure rolls back cleanly
- `make_token` / `verify_token` replace passing raw passwords around

See `docs/migration-report.md` for the decision log.
