# ADR 0002: Passwords are PBKDF2 with a per-account salt

## Status

Accepted.

## Context

The legacy ledger hashes passwords with unsalted MD5. MD5 is fast, which
is the opposite of what password hashing needs: an attacker with the
database can brute-force common passwords in minutes, and one rainbow
table cracks every account at once because there is no salt.

## Decision

PBKDF2-HMAC-SHA256, 200,000 iterations, with a random 16-byte salt per
account, compared with `hmac.compare_digest`.

## Consequences

- Verification is deliberately slow (hundreds of milliseconds at this
  iteration count), which is the point: it costs the attacker the same
  time per guess.
- A per-account salt means identical passwords produce different hashes,
  so a breach cannot be attacked in bulk.
- `compare_digest` removes the timing side channel that a plain `==`
  comparison leaks.
- Argon2id would be the stronger choice for a new system and is the
  recommendation if this ledger ever leaves the lab. PBKDF2 was chosen
  because it is in the standard library, so the migration has no new
  dependency, and because the threat being fixed is MD5 with no salt,
  which PBKDF2 already closes by orders of magnitude.
- Existing MD5 hashes cannot be upgraded in place. On cutover, accounts
  re-hash on next successful login: verify against MD5 once, then store
  PBKDF2 and drop the MD5 hash. Accounts that never log in again keep
  their MD5 hash until a forced reset, which is recorded as a known
  residual risk in the migration report.
