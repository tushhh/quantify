"""Security scan for the Quantify repo.

Checks: committed secrets and sensitive files, authentication on every FastAPI route,
secrets passed through workflow_dispatch inputs, and (with --deps) known-vulnerable
Python and npm dependencies.

Usage (from the repo root):
    python .claude/skills/deep-security-check/scan.py [--deps]

Exit code 1 if any HIGH finding. Matched secret values are never printed in full.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(
    subprocess.run(["git", "rev-parse", "--show-toplevel"], check=True,
                   capture_output=True, text=True).stdout.strip()
)

SECRET_PATTERNS = [
    ("Telegram bot token", re.compile(r"\b\d{8,10}:AA[0-9A-Za-z_-]{33}\b")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[0-9A-Za-z]{36,}|github_pat_[0-9A-Za-z_]{40,})\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("Slack token", re.compile(r"\bxox[abprs]-[0-9A-Za-z-]{10,}\b")),
    ("API key (sk-...)", re.compile(r"\bsk-(?:ant-|proj-)?[0-9A-Za-z_-]{24,}\b")),
    ("Database URL with password",
     re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s:/@'\"]+:[^\s@'\"]{3,}@")),
    ("Hardcoded credential",
     re.compile(r"(?i)\b(\w*(?:api[_-]?key|secret|token|passw(?:or)?d)\w*)\b[\"']?\s*[:=]\s*[\"']"
                r"([^\"'\s]{12,})[\"']")),
]
# Key names that hold locations or labels, not credentials (e.g. tokenUrl="/api/auth/login").
NOT_A_CREDENTIAL_KEY = re.compile(r"(?i)(url|uri|path|endpoint|name|type|header|prefix)$")
# Routes that must be reachable without auth.
PUBLIC_BY_DESIGN = {
    "POST /api/auth/register": "sign-up",
    "POST /api/auth/login": "sign-in",
}
RAW_ERROR_DETAIL = re.compile(r"detail\s*=\s*f[\"'][^\"']*\{(?:exc|e|err|error|res|ex)\b")
PLACEHOLDER = re.compile(
    r"(?i)(your|example|sample|changeme|placeholder|dummy|xxx|redacted|test|fake|<|\$\{|\{\{)"
)
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2",
                   ".ttf", ".pdf", ".joblib", ".pkl", ".parquet", ".zip", ".gz"}
SKIP_NAMES = {"package-lock.json"}
SENSITIVE_FILE = re.compile(
    r"(^|/)(\.env(\.(?!example$|sample$|template$)[^/]+)?|[^/]+\.(db|sqlite3?|pem|key|p12|pfx))$"
)
# Calls that change persistent or external state: DB writes, Telegram sends, workflow runs.
MUTATION_MARKERS = ("db.add(", "session.add(", "db.delete(", ".delete()", ".commit(",
                    "db.merge(", "send_message(", "/dispatches", "_dispatch", "broadcast")
PII_MARKERS = ("chat_id", "email", "phone")


@dataclass
class Finding:
    severity: str  # HIGH | MEDIUM | LOW | INFO
    where: str
    message: str


def _git_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", "-co", "--exclude-standard"], cwd=ROOT,
                         check=True, capture_output=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def _redact(value: str) -> str:
    return value[:4] + "..." + f"({len(value)} chars)"


def scan_secrets(files: list[str]) -> list[Finding]:
    findings = []
    for rel in files:
        if SENSITIVE_FILE.search(rel):
            findings.append(Finding("HIGH", rel, "sensitive file is tracked or unignored"))
        path = ROOT / rel
        if path.suffix.lower() in BINARY_SUFFIXES or path.name in SKIP_NAMES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.split("\n"), 1):  # editor line numbers
            for label, pattern in SECRET_PATTERNS:
                match = pattern.search(line)
                if not match:
                    continue
                value = match.group(match.lastindex or 0)
                if PLACEHOLDER.search(value):
                    continue
                if label == "Hardcoded credential" and (
                        NOT_A_CREDENTIAL_KEY.search(match.group(1))
                        or value.startswith(("/", "http"))
                        or "getenv" in line or "environ" in line or rel.startswith("tests/")):
                    continue
                findings.append(Finding("HIGH", f"{rel}:{lineno}",
                                        f"{label}: {_redact(value)}"))
    return findings


def _route(decorator: ast.expr) -> tuple[str, str] | None:
    if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr in {"get", "post", "put", "patch", "delete"}
            and decorator.args and isinstance(decorator.args[0], ast.Constant)):
        return decorator.func.attr.upper(), str(decorator.args[0].value)
    return None


def scan_routes() -> list[Finding]:
    findings = []
    for path in sorted((ROOT / "api" / "routers").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        rel = path.relative_to(ROOT).as_posix()
        router_wide_auth = bool(re.search(r"APIRouter\([^)]*dependencies=[^)]*get_current_user",
                                          text, re.S))
        prefix = re.search(r"APIRouter\([^)]*prefix=\"([^\"]*)\"", text)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                route = _route(decorator)
                if not route:
                    continue
                method, sub = route
                full = f"{method} /api{prefix.group(1) if prefix else ''}{sub}"
                src = ast.get_source_segment(text, node) or ""
                where = f"{rel}:{node.lineno}"
                if RAW_ERROR_DETAIL.search(src):
                    findings.append(Finding("LOW", where, f"{full} returns raw exception text to "
                                            "clients (CLAUDE.md: never expose backend errors)"))
                protected = router_wide_auth or "_verify_secret(" in src or "get_current_user" in src
                mutation = next((m for m in MUTATION_MARKERS if m in src), None)
                pii = any(marker in src for marker in PII_MARKERS)
                if full in PUBLIC_BY_DESIGN:
                    findings.append(Finding("INFO", where,
                                            f"{full} is public by design ({PUBLIC_BY_DESIGN[full]})"))
                    continue
                if protected:
                    if method == "GET" and mutation:
                        findings.append(Finding("LOW", where, f"{full} changes state on GET "
                                                "(link previews and crawlers can trigger it)"))
                    continue
                if path.name == "internal.py":
                    findings.append(Finding("HIGH", where,
                                            f"{full} is internal but never calls _verify_secret"))
                elif mutation:
                    findings.append(Finding("MEDIUM", where, f"{full} is unauthenticated and "
                                            f"changes state (matched {mutation!r}); confirm that's "
                                            "intended and rate-limited"))
                elif pii:
                    findings.append(Finding("MEDIUM", where,
                                            f"{full} is unauthenticated and handles user identifiers"))
                else:
                    findings.append(Finding("INFO", where, f"{full} is public (read-only)"))
    return findings


def scan_workflow_secrets(files: list[str]) -> list[Finding]:
    findings = []
    for rel in files:
        if not re.match(r"\.github/workflows/.+\.ya?ml$", rel):
            continue
        lines = (ROOT / rel).read_text(encoding="utf-8").split("\n")
        for i, line in enumerate(lines):
            if re.search(r"\becho\b.*\$\{\{\s*secrets\.", line):
                findings.append(Finding("MEDIUM", f"{rel}:{i + 1}", "secret echoed in a run step"))
            if not re.match(r"\s*inputs:\s*$", line):
                continue
            parent = len(line) - len(line.lstrip())
            child = None
            for j in range(i + 1, len(lines)):  # direct children of `inputs:` are the input names
                text = lines[j]
                if not text.strip() or text.lstrip().startswith("#"):
                    continue
                indent = len(text) - len(text.lstrip())
                if indent <= parent:
                    break
                child = indent if child is None else child
                name = re.match(r"\s*([A-Za-z0-9_-]+):", text)
                if (indent == child and name
                        and re.search(r"(?i)secret|token|password|api_?key", name.group(1))):
                    findings.append(Finding(
                        "MEDIUM", f"{rel}:{j + 1}",
                        f"workflow_dispatch input '{name.group(1)}' carries a secret; input "
                        "values aren't masked unless they equal a registered secret"))
    # Callers that put a live secret into a dispatch payload
    for rel in files:
        if not rel.endswith(".py") or rel.startswith(("tests/", ".claude/")):
            continue
        text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        if "/dispatches" not in text:
            continue
        for lineno, line in enumerate(text.split("\n"), 1):
            m = re.search(r"[\"'](\w*(?:secret|token|password)\w*)[\"']\s*:\s*(?![\"']{2}|None\b)(\S+)",
                          line, re.I)
            if m:
                findings.append(Finding("MEDIUM", f"{rel}:{lineno}",
                                        f"'{m.group(1)}' sent as a workflow_dispatch input; it can "
                                        "appear unmasked in Actions logs of this public repo"))
    return findings


def audit_dependencies() -> list[Finding]:
    findings = []
    uvx = shutil.which("uvx")
    if uvx:
        proc = subprocess.run([uvx, "pip-audit", "-r", "api/requirements.txt", "-f", "json",
                               "--progress-spinner", "off"], cwd=ROOT, capture_output=True,
                              text=True, timeout=900)
        try:
            report = json.loads(proc.stdout)
            for dep in report.get("dependencies", []):
                for vuln in dep.get("vulns", []):
                    fix = ", ".join(vuln.get("fix_versions", [])) or "no fix yet"
                    findings.append(Finding("MEDIUM", "api/requirements.txt",
                                            f"{dep['name']} {dep.get('version')}: {vuln['id']} "
                                            f"(fixed in {fix})"))
        except json.JSONDecodeError:
            findings.append(Finding("INFO", "pip-audit", "could not run: "
                                    + (proc.stderr.strip().splitlines() or ["no output"])[-1][:160]))
    else:
        findings.append(Finding("INFO", "pip-audit", "uvx not found; skipped Python audit"))

    npm = shutil.which("npm")
    if npm and (ROOT / "web" / "package-lock.json").exists():
        proc = subprocess.run([npm, "audit", "--omit=dev", "--json"], cwd=ROOT / "web",
                              capture_output=True, text=True, timeout=600)
        try:
            counts = json.loads(proc.stdout).get("metadata", {}).get("vulnerabilities", {})
            serious = {k: v for k, v in counts.items() if k in ("critical", "high") and v}
            if serious:
                findings.append(Finding("MEDIUM", "web/package-lock.json",
                                        f"npm audit (production deps): {serious}"))
            elif counts:
                findings.append(Finding("INFO", "web/package-lock.json",
                                        f"npm audit: {counts}"))
        except json.JSONDecodeError:
            findings.append(Finding("INFO", "npm audit", "could not run (network/proxy?)"))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--deps", action="store_true",
                        help="also audit dependencies (needs network: pip-audit via uvx, npm audit)")
    parser.add_argument("--all", action="store_true", help="also list INFO findings")
    args = parser.parse_args()

    files = _git_files()
    findings = scan_secrets(files) + scan_routes() + scan_workflow_secrets(files)
    if args.deps:
        findings += audit_dependencies()

    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}
    findings.sort(key=lambda f: (order[f.severity], f.where))
    counts = {s: sum(f.severity == s for f in findings) for s in order}
    shown = [f for f in findings if args.all or f.severity != "INFO"]

    print("deep-security-check: " + ", ".join(f"{n} {s}" for s, n in counts.items()))
    for f in shown:
        print(f"[{f.severity:<6}] {f.where}\n          {f.message}")
    if counts["INFO"] and not args.all:
        print(f"({counts['INFO']} INFO findings hidden; --all to list public read-only routes etc.)")
    return 1 if counts["HIGH"] else 0


if __name__ == "__main__":
    sys.exit(main())
