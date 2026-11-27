"""Randomised differential testing for the migration.

Fixed scenarios only cover what someone thought to write down. This
module generates random operation streams with a fixed seed, runs them
against the legacy ledger and the modern ledger, and compares every
outcome and the final state. A mismatch is reproducible from the seed.

Usage:
    python -m migration.differential --ops 200 --seed 7
"""

from __future__ import annotations

import argparse
import random
from decimal import Decimal

from migration.equivalence import run_scenarios

_NAMES = ["ada", "bob", "carol", "dan"]
_PASSWORDS = {"ada": "s3cret", "bob": "hunter2", "carol": "p4ssw0rd", "dan": "letmein"}


def generate_ops(count: int, seed: int) -> list[dict]:
    """Generate a deterministic random operation stream."""
    rng = random.Random(seed)
    ops: list[dict] = []
    created: set[str] = set()
    for _ in range(count):
        roll = rng.random()
        if roll < 0.15 or not created:
            name = rng.choice(_NAMES)
            ops.append(
                {"op": "create_account", "name": name, "password": _PASSWORDS[name]}
            )
            created.add(name)
        elif roll < 0.55:
            name = rng.choice(sorted(created))
            amount = str(Decimal(rng.randrange(1, 50000)) / 100)
            ops.append({"op": "deposit", "name": name, "amount": amount})
        else:
            frm, to = rng.sample(sorted(created), 2) if len(created) >= 2 else (None, None)
            if frm is None:
                name = rng.choice(sorted(created))
                ops.append({"op": "deposit", "name": name, "amount": "10.00"})
                continue
            amount = str(Decimal(rng.randrange(1, 20000)) / 100)
            password = _PASSWORDS[frm]
            if rng.random() < 0.1:
                password = "wrong-password"
            ops.append(
                {
                    "op": "transfer",
                    "from": frm,
                    "to": to,
                    "amount": amount,
                    "password": password,
                }
            )
    return ops


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ops", type=int, default=200)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    scenarios = generate_ops(args.ops, args.seed)
    report = run_scenarios(scenarios)
    mismatches = [op for op in report["ops"] if not op["match"]]
    print(
        "ops: %d, seed: %d, mismatches: %d, final state match: %s"
        % (len(scenarios), args.seed, len(mismatches), report["final_state_match"])
    )
    for mismatch in mismatches[:10]:
        print("  MISMATCH %s" % (mismatch,))
    return 0 if (report["ops_match"] and report["final_state_match"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
