"""
Security agent: runs Bandit and Semgrep against the PR's changed Python files,
then asks the LLM to rewrite each raw finding as a plain-English explanation a
reviewer can act on without knowing the underlying rule ID.
"""
import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.agents._workdir import write_files
from app.agents.llm import ask_json
from app.agents.state import Finding

logger = logging.getLogger("codeguardian.security")

_BANDIT_SEVERITY = {"LOW": "low", "MEDIUM": "medium", "HIGH": "high"}
_SEMGREP_SEVERITY = {"INFO": "info", "WARNING": "medium", "ERROR": "high"}

_TRIAGE_SYSTEM_PROMPT = (
    "You are a security reviewer explaining static-analysis findings to a "
    "developer. For each finding you're given, rewrite `message` into one "
    "plain-English sentence describing the risk and a concrete fix — no jargon, "
    "no rule IDs. Keep `file`, `line`, and `severity` unchanged. Respond with a "
    "JSON array of objects with keys: file, line, severity, message. No prose "
    "outside the JSON."
)


def security_agent(state: dict) -> dict:
    files = [f for f in state["files"] if f.get("content") and f["status"] != "removed"]
    py_files = [f for f in files if f["filename"].endswith(".py")]
    if not files:
        return {"security_findings": []}

    with tempfile.TemporaryDirectory(prefix="codeguardian_") as tmp:
        tmp_path = Path(tmp)
        written = write_files(tmp_path, files)

        findings: list[Finding] = []
        if py_files and shutil.which("bandit"):
            findings += _run_bandit(tmp_path, written)
        if shutil.which("semgrep"):
            findings += _run_semgrep(tmp_path, written)

    if not findings:
        return {"security_findings": []}

    return {"security_findings": _triage(findings)}


def _run_bandit(tmp_path: Path, written: dict[str, str]) -> list[Finding]:
    try:
        proc = subprocess.run(
            ["bandit", "-r", str(tmp_path), "-f", "json"],
            capture_output=True, text=True, timeout=120,
        )
        data = json.loads(proc.stdout or "{}")
    except Exception:
        logger.exception("bandit run failed")
        return []

    findings = []
    for result in data.get("results", []):
        rel = str(Path(result["filename"]).relative_to(tmp_path)).replace("\\", "/")
        findings.append(Finding(
            file=written.get(rel, rel),
            line=result.get("line_number"),
            severity=_BANDIT_SEVERITY.get(result.get("issue_severity", ""), "medium"),
            message=f"{result.get('test_name', 'bandit')}: {result.get('issue_text', '')}",
            source_agent="security",
        ))
    return findings


def _run_semgrep(tmp_path: Path, written: dict[str, str]) -> list[Finding]:
    try:
        proc = subprocess.run(
            ["semgrep", "--config", "auto", "--json", "--quiet", str(tmp_path)],
            capture_output=True, text=True, timeout=180,
        )
        data = json.loads(proc.stdout or "{}")
    except Exception:
        logger.exception("semgrep run failed")
        return []

    findings = []
    for result in data.get("results", []):
        rel = str(Path(result["path"]).relative_to(tmp_path)).replace("\\", "/")
        severity = result.get("extra", {}).get("severity", "WARNING")
        findings.append(Finding(
            file=written.get(rel, rel),
            line=result.get("start", {}).get("line"),
            severity=_SEMGREP_SEVERITY.get(severity, "medium"),
            message=result.get("extra", {}).get("message", result.get("check_id", "semgrep finding")),
            source_agent="security",
        ))
    return findings


def _triage(findings: list[Finding]) -> list[Finding]:
    payload = json.dumps([dict(f) for f in findings])
    triaged = ask_json(_TRIAGE_SYSTEM_PROMPT, payload, max_tokens=2048)
    if not isinstance(triaged, list) or len(triaged) != len(findings):
        return findings  # LLM unavailable or malformed — ship the raw findings instead.

    result = []
    for original, rewritten in zip(findings, triaged):
        result.append(Finding(
            file=original["file"],
            line=original["line"],
            severity=original["severity"],
            message=rewritten.get("message", original["message"]),
            source_agent="security",
        ))
    return result
