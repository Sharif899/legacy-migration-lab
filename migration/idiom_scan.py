"""Scanner for Python 2 idioms and legacy defects.

Detects, in any file, the patterns a migration has to remove: Python 2
only syntax and calls, MD5 hashing, string-concatenated SQL, bare except
clauses, mutable default arguments, and float handling of money.

Text rules run on every file (Python 2 code does not parse under Python 3,
so it can only be scanned as text). AST rules run when the file parses.

Usage:
    python -m migration.idiom_scan legacy/ledger.py migration/samples/legacy_snippet_py2.py
"""

from __future__ import annotations

import argparse
import ast
import io
import re
import tokenize
from dataclasses import dataclass


@dataclass
class Finding:
    rule: str
    line: int
    message: str
    severity: str = "high"


# Text rules: (rule, pattern, message). These catch Python 2 only code
# that cannot be parsed by a Python 3 AST.
TEXT_RULES = [
    ("PY2_PRINT", re.compile(r"^\s*print\s+[^(]"), "print statement, not a function call"),
    ("PY2_XRANGE", re.compile(r"\bxrange\s*\("), "xrange, removed in Python 3"),
    ("PY2_ITERITEMS", re.compile(r"\.iteritems\s*\("), "dict.iteritems, removed in Python 3"),
    ("PY2_RAW_INPUT", re.compile(r"\braw_input\s*\("), "raw_input, renamed to input in Python 3"),
    ("PY2_HAS_KEY", re.compile(r"\.has_key\s*\("), "dict.has_key, removed in Python 3"),
    ("PY2_UNICODE", re.compile(r"\bunicode\s*\("), "unicode type, removed in Python 3"),
    ("PY2_LONG", re.compile(r"\blong\s*\("), "long type, removed in Python 3"),
]


def _scan_text(source: str) -> list[Finding]:
    findings = []
    for lineno, line in enumerate(source.splitlines(), 1):
        if line.strip().startswith("#"):
            continue
        for rule, pattern, message in TEXT_RULES:
            if pattern.search(line):
                findings.append(Finding(rule, lineno, message))
    return findings


class _AstVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.findings: list[Finding] = []

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "md5":
            self.findings.append(
                Finding("MD5_HASH", node.lineno, "hashlib.md5 used for passwords")
            )
        if isinstance(func, ast.Name) and func.id == "float":
            self.findings.append(
                Finding("FLOAT_MONEY", node.lineno, "float() used, unsafe for money")
            )
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.findings.append(
                Finding("BARE_EXCEPT", node.lineno, "bare except: hides failures")
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        for default in node.args.defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.findings.append(
                    Finding(
                        "MUTABLE_DEFAULT",
                        node.lineno,
                        "mutable default argument on %s" % node.name,
                    )
                )
        self.generic_visit(node)


def _scan_ast(source: str) -> list[Finding]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    visitor = _AstVisitor()
    visitor.visit(tree)
    return visitor.findings


def _scan_sql_concat(source: str) -> list[Finding]:
    """Flag SQL built by string concatenation or % formatting.

    A line is flagged when it formats a string with % (a quote followed
    by %, or a continuation line starting with %), or when a + appears
    inside a string literal on that line, and a SQL keyword appears on
    that line or the two lines above it. A + in code, such as inside a
    parameter tuple, does not count.
    """
    lines = source.splitlines()
    plus_in_string: set[int] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.STRING and "+" in tok.string:
                plus_in_string.add(tok.start[0])
    except (tokenize.TokenError, SyntaxError, IndentationError):
        pass
    findings = []
    sql_words = ("SELECT", "INSERT", "UPDATE", "DELETE", "VALUES")
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        percent_format = bool(re.search(r"""["']\s*%""", line)) or stripped.startswith(
            "%"
        )
        if not (percent_format or lineno in plus_in_string):
            continue
        window = "\n".join(lines[max(0, lineno - 3) : lineno])
        if any(w in window.upper() for w in sql_words):
            findings.append(
                Finding(
                    "STRING_SQL",
                    lineno,
                    "SQL built by string concatenation or % formatting",
                )
            )
    return findings


def scan_file(path: str) -> list[Finding]:
    """Scan one file and return its findings, in line order."""
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    findings = _scan_text(source) + _scan_ast(source) + _scan_sql_concat(source)
    findings.sort(key=lambda f: (f.line, f.rule))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    total = 0
    for path in args.paths:
        findings = scan_file(path)
        total += len(findings)
        print("%s: %d finding(s)" % (path, len(findings)))
        for finding in findings:
            print("  line %d [%s] %s" % (finding.line, finding.rule, finding.message))
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
