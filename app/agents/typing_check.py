"""
Typing agent: runs mypy against the PR's changed Python files to catch
genuinely incorrect type usage — not just missing hints (the quality agent
already nudges toward those via the coding-standards doc), but type errors a
real type checker can prove are wrong.
"""
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.agents._workdir import write_files
from app.agents.state import Finding

logger = logging.getLogger("codeguardian.typing_check")

_MYPY_LINE_RE = re.compile(
    r"^(?P<file>.+):(?P<line>\d+):(?P<col>\d+): (?P<level>error|warning): (?P<message>.+?)(?:\s+\[(?P<code>[\w-]+)\])?$"
)


def typing_agent(state: dict) -> dict:
    files = [
        f for f in state["files"]
        if f.get("content") and f["status"] != "removed" and f["filename"].endswith(".py")
    ]
    if not files or not shutil.which("mypy"):
        return {"typing_findings": []}

    with tempfile.TemporaryDirectory(prefix="codeguardian_typing_") as tmp:
        tmp_path = Path(tmp)
        written = write_files(tmp_path, files)

        try:
            proc = subprocess.run(
                [
                    "mypy",
                    "--no-error-summary",
                    "--no-incremental",
                    "--ignore-missing-imports",
                    "--follow-imports", "silent",
                    "--show-column-numbers",
                    "--show-error-codes",
                    str(tmp_path),
                ],
                capture_output=True, text=True, timeout=120,
            )
        except Exception:
            logger.exception("mypy run failed")
            return {"typing_findings": []}

        findings = []
        for line in proc.stdout.splitlines():
            match = _MYPY_LINE_RE.match(line.strip())
            if not match or match.group("level") != "error":
                continue

            rel = str(Path(match.group("file")).relative_to(tmp_path)).replace("\\", "/")
            findings.append(Finding(
                file=written.get(rel, rel),
                line=int(match.group("line")),
                severity="medium",
                message=match.group("message"),
                source_agent="typing",
            ))

    return {"typing_findings": findings}
