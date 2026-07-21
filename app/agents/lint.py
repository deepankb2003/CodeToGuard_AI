"""
Lint agent: deterministic unused-import (ruff) and dead-code (vulture)
detection. No LLM involved, so these findings are exact and tool-verified,
not judgment calls.
"""
import json
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.agents._workdir import write_files
from app.agents.state import Finding

logger = logging.getLogger("codeguardian.lint")

_VULTURE_LINE_RE = re.compile(
    r"^(?P<file>.+):(?P<line>\d+): (?P<message>.+?) \((?P<confidence>\d+)% confidence\)$"
)
# ruff's F401 already reports unused imports — skip vulture's overlapping report of the same thing.
_VULTURE_SKIP_PREFIXES = ("unused import",)


def lint_agent(state: dict) -> dict:
    files = [
        f for f in state["files"]
        if f.get("content") and f["status"] != "removed" and f["filename"].endswith(".py")
    ]
    if not files:
        return {"lint_findings": []}

    with tempfile.TemporaryDirectory(prefix="codeguardian_lint_") as tmp:
        tmp_path = Path(tmp)
        written = write_files(tmp_path, files)

        findings: list[Finding] = []
        if shutil.which("ruff"):
            findings += _run_ruff(tmp_path, written)
        if shutil.which("vulture"):
            findings += _run_vulture(tmp_path, written)

    return {"lint_findings": findings}


def _run_ruff(tmp_path: Path, written: dict[str, str]) -> list[Finding]:
    try:
        proc = subprocess.run(
            ["ruff", "check", "--select", "F401", "--output-format", "json", str(tmp_path)],
            capture_output=True, text=True, timeout=60,
        )
        results = json.loads(proc.stdout or "[]")
    except Exception:
        logger.exception("ruff run failed")
        return []

    findings = []
    for result in results:
        rel = str(Path(result["filename"]).relative_to(tmp_path)).replace("\\", "/")
        findings.append(Finding(
            file=written.get(rel, rel),
            line=result.get("location", {}).get("row"),
            severity="low",
            message=result.get("message", "Unused import."),
            source_agent="unused_import",
        ))
    return findings


def _run_vulture(tmp_path: Path, written: dict[str, str]) -> list[Finding]:
    try:
        proc = subprocess.run(
            ["vulture", str(tmp_path)],
            capture_output=True, text=True, timeout=60,
        )
    except Exception:
        logger.exception("vulture run failed")
        return []

    findings = []
    for line in proc.stdout.splitlines():
        match = _VULTURE_LINE_RE.match(line.strip())
        if not match:
            continue
        message = match.group("message")
        if message.startswith(_VULTURE_SKIP_PREFIXES):
            continue

        rel = str(Path(match.group("file")).relative_to(tmp_path)).replace("\\", "/")
        findings.append(Finding(
            file=written.get(rel, rel),
            line=int(match.group("line")),
            severity="medium",
            message=f"{message} ({match.group('confidence')}% confidence).",
            source_agent="dead_code",
        ))
    return findings
