# Legacy Migration Lab

An end-to-end legacy codebase migration, built to be read by a recruiter.

A small payments ledger written in deliberately old-fashioned Python 2 style
is migrated to modern Python 3.12, and the migration itself is validated the
way a real one should be: behaviour is proven equivalent, the old idioms are
detected mechanically, and AI-generated migration proposals are scored
against a rubric.

This is a demonstration lab, not client work. The legacy code was written
for this project so the migration could be shown honestly, with the defects
labelled and the fixes verified by tests.

## Evidence first

- **24 tests, all passing**, including money-conservation and atomicity
  invariants that hold for any sequence of operations, not just the
  scenarios someone wrote down.
- **Randomised differential testing**: 200 random operations with a fixed
  seed run against both ledgers, every outcome and the final state
  compared. A mismatch is reproducible from the seed.
- **Four architecture decision records** (`docs/adr/`) showing the
  reasoning, the alternatives rejected, and the consequences: Decimal
  money, PBKDF2 hashing, the error taxonomy, and the dual-run cutover.
- **A written migration report** (`docs/migration-report.md`) with the
  inventory, risk register, phased plan, threat model, rollback, and the
  one irreversible step stated plainly instead of discovered later.

## The migration, in one paragraph

The legacy ledger is a single module with string-concatenated SQL, MD5
password hashing with no salt, float arithmetic for money, bare `except:`
clauses, global state and no tests. The modern ledger keeps the exact same
business behaviour and public method names, but stores money as `Decimal`,
hashes passwords with PBKDF2 and a per-account salt, uses parameterised
queries, raises typed errors instead of returning `False`, and is fully
tested. The equivalence harness runs the same scenarios against both
implementations and diffs the results.

## What is in here

| Path | What it shows |
| --- | --- |
| `legacy/` | The "before" system: Python 2 style payments ledger, defects labelled with `# LEGACY:` comments |
| `modern/` | The "after" system: same behaviour, Python 3.12, typed, tested |
| `migration/equivalence.py` | Behavioural equivalence harness: runs shared scenarios against both ledgers and diffs the outcomes |
| `migration/differential.py` | Randomised differential testing: seeded random operation streams run against both ledgers, every outcome compared |
| `migration/idiom_scan.py` | AST and text scanner that detects Python 2 idioms and legacy defects in a file |
| `migration/ai_eval.py` | Rubric evaluator for AI-generated migration diffs: correctness, completeness, maintainability, production readiness |
| `docs/adr/` | Architecture decision records: the reasoning behind each hard call, and the alternatives rejected |
| `migration/samples/` | A genuine Python 2 snippet (scanned as text only) and two sample AI migration diffs, one bad, one good |
| `scenarios/scenarios.json` | Shared scenarios both ledgers must satisfy |
| `docs/migration-report.md` | The written migration report: inventory, risks, phased plan, decisions, rollback |
| `tests/` | pytest suite covering the modern ledger, the equivalence harness, the scanner and the evaluator |

## How to run it

```bash
pip install pytest
pytest -q
python -m migration.equivalence --scenarios scenarios/scenarios.json
python -m migration.differential --ops 200 --seed 7
python -m migration.idiom_scan legacy/ledger.py migration/samples/legacy_snippet_py2.py
python -m migration.ai_eval migration/samples/ai_migration_bad.diff
python -m migration.ai_eval migration/samples/ai_migration_good.diff
```

Everything is standard library except pytest, which is only needed for the
test suite.

## Why this maps to legacy migration work

- **Analyse before touching anything.** `docs/migration-report.md` inventories
  the legacy system, its dependencies and its risks before any code changes.
- **Preserve behaviour.** The equivalence harness is the proof: same
  scenarios, same balances, same statements, with the only documented
  differences being the security fixes (hashing, SQL injection) and the
  error-signalling change (return codes to typed exceptions).
- **Validate with tests, not by reading.** The modern ledger has full test
  coverage of its business rules, including the float precision case
  (`0.10 + 0.20`) that the legacy code gets wrong. The invariants go
  further: money conservation and statement consistency hold for any
  operation sequence, and the differential tester checks random streams,
  not just the scenarios someone wrote down.
- **Evaluate AI-generated migrations.** `migration/ai_eval.py` scores a
  proposed migration diff on the four things that matter: correctness,
  completeness, maintainability and production readiness. The bad sample
  diff scores below the pass mark, with findings, because it keeps MD5,
  misses a function, adds no tests and hardcodes a password.
- **Plan the cutover.** The report covers phased rollout, dual running,
  and rollback, not just the code change.

## The legacy defects, labelled

Each defect in `legacy/ledger.py` carries a `# LEGACY:` comment:

- MD5 password hashing, no salt
- SQL built by string concatenation (injection)
- `float` for money (rounding error)
- bare `except:` that hides failures
- global mutable connection state
- `%` string formatting and old-style classes
- no tests, no types, no error taxonomy
