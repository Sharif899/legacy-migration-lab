"""Rubric evaluator for AI-generated migration diffs.

Scores a proposed migration (a unified diff) on the four things a
migration reviewer checks, 25 points each, 100 total:

- correctness: does it preserve behaviour and remove the defects?
- completeness: does it cover every module and every public function?
- maintainability: types, docstrings, no dead code or TODOs left behind?
- production readiness: tests, no secrets, backwards compatibility noted?

Verdict: PASS at 80+, NEEDS WORK at 60-79, FAIL below 60.

Usage:
    python -m migration.ai_eval migration/samples/ai_migration_bad.diff
    python -m migration.ai_eval migration/samples/ai_migration_good.diff
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field


@dataclass
class Evaluation:
    scores: dict
    findings: list = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(self.scores.values())

    @property
    def verdict(self) -> str:
        if self.total >= 80:
            return "PASS"
        if self.total >= 60:
            return "NEEDS WORK"
        return "FAIL"


def _added_lines(diff: str) -> list[str]:
    return [
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]


def _touched_files(diff: str) -> list[str]:
    return re.findall(r"^diff --git a/(\S+) b/", diff, re.M)


def evaluate_diff(
    diff: str,
    expected_modules: list[str],
    expected_functions: list[str],
) -> Evaluation:
    added = _added_lines(diff)
    added_text = "\n".join(added)
    touched = _touched_files(diff)
    scores = {"correctness": 25, "completeness": 25, "maintainability": 25, "production_readiness": 25}
    findings: list[str] = []

    # Correctness: defects must go, behaviour must be preserved.
    if re.search(r"\bmd5\b", added_text, re.I):
        scores["correctness"] -= 10
        findings.append("correctness: MD5 hashing still present in the migration")
    if re.search(r"float\s*\(", added_text):
        scores["correctness"] -= 5
        findings.append("correctness: float() still used for money")
    if re.search(r"except\s*:", added_text):
        scores["correctness"] -= 5
        findings.append("correctness: bare except: still present")
    if "Decimal" not in added_text and "decimal" not in added_text.lower():
        scores["correctness"] -= 5
        findings.append("correctness: no Decimal money handling in the migration")
    if re.search(r"execute\s*\([^)]*\+", added_text) or re.search(
        r"execute\s*\([^)]*%\s", added_text
    ):
        scores["correctness"] -= 5
        findings.append("correctness: SQL still built by concatenation")

    # Completeness: every module and every public function must be covered.
    missing_modules = [m for m in expected_modules if m not in touched]
    if missing_modules:
        scores["completeness"] -= 10
        findings.append(
            "completeness: modules not touched: %s" % ", ".join(missing_modules)
        )
    missing_functions = [f for f in expected_functions if f not in added_text]
    if missing_functions:
        scores["completeness"] -= 10
        findings.append(
            "completeness: functions not migrated: %s" % ", ".join(missing_functions)
        )

    # Maintainability: types, docstrings, no leftovers.
    defs = [line for line in added if line.strip().startswith("def ")]
    untyped = [d for d in defs if "->" not in d]
    if defs and untyped:
        scores["maintainability"] -= 10
        findings.append(
            "maintainability: %d of %d added functions lack return type hints"
            % (len(untyped), len(defs))
        )
    if '"""' not in added_text and "'''" not in added_text:
        scores["maintainability"] -= 5
        findings.append("maintainability: no docstrings in the migration")
    if "TODO" in added_text or "FIXME" in added_text:
        scores["maintainability"] -= 5
        findings.append("maintainability: TODO or FIXME left in the diff")

    # Production readiness: tests, no secrets, backwards compatibility.
    if not any("test" in f for f in touched):
        scores["production_readiness"] -= 10
        findings.append("production_readiness: no tests added with the migration")
    if re.search(r"password\s*=\s*[\"'][^\"']+[\"']", added_text, re.I) or re.search(
        r"SECRET\s*=\s*[\"']", added_text
    ):
        scores["production_readiness"] -= 10
        findings.append("production_readiness: hardcoded secret in the diff")
    if "backwards" not in diff.lower() and "compat" not in diff.lower():
        scores["production_readiness"] -= 5
        findings.append(
            "production_readiness: no backwards compatibility note in the diff"
        )

    scores = {k: max(0, v) for k, v in scores.items()}
    return Evaluation(scores=scores, findings=findings)


EXPECTED_MODULES = ["legacy/ledger.py"]
EXPECTED_FUNCTIONS = [
    "create_account",
    "deposit",
    "transfer",
    "balance",
    "statement",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("diff_path")
    args = parser.parse_args()
    with open(args.diff_path, encoding="utf-8") as fh:
        diff = fh.read()
    evaluation = evaluate_diff(diff, EXPECTED_MODULES, EXPECTED_FUNCTIONS)
    print("score: %d/100  verdict: %s" % (evaluation.total, evaluation.verdict))
    for name, score in evaluation.scores.items():
        print("  %-20s %d/25" % (name, score))
    for finding in evaluation.findings:
        print("  - " + finding)
    return 0 if evaluation.verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
