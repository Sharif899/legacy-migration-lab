# Legacy ledger

The "before" system. A single module, `ledger.py`, written in the style of
a Python 2 era codebase: old-style classes, `%` formatting, bare `except:`,
MD5 passwords, string-concatenated SQL, float money, no tests.

It runs on Python 3 so the equivalence harness can execute it side by side
with the modern version. Every defect is marked with a `# LEGACY:` comment
in the source. The point of keeping it is not to run it, it is to have a
real baseline to migrate away from and to prove behaviour against.

See `docs/migration-report.md` for the inventory and risk register.
