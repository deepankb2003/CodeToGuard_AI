"""
Test-gap agent: flags changed source files that don't have a corresponding
test file touched in the same PR. Deliberately a heuristic, not a coverage
tool — it can't see whether an existing test already exercises the change, only
whether the PR bothered to touch anything that looks like a test for it.
"""
from pathlib import Path

from app.agents.state import Finding

_TEST_DIR_MARKERS = ("test", "tests")


def test_gap_agent(state: dict) -> dict:
    files = [f for f in state["files"] if f["status"] != "removed"]
    code_files = [f for f in files if _is_code_file(f["filename"]) and not _is_test_file(f["filename"])]
    if not code_files:
        return {"test_gap_findings": []}

    test_stems = {
        _strip_test_affixes(Path(f["filename"]).stem)
        for f in files
        if _is_test_file(f["filename"])
    }

    findings = []
    for f in code_files:
        stem = Path(f["filename"]).stem
        if stem in test_stems:
            continue
        findings.append(Finding(
            file=f["filename"],
            line=None,
            severity="medium",
            message=(
                f"No test file changes were found alongside {f['filename']}. "
                "Add or update a test covering this change."
            ),
            source_agent="test_gap",
        ))
    return {"test_gap_findings": findings}


def _is_code_file(filename: str) -> bool:
    return filename.endswith((".py", ".ts", ".tsx", ".js", ".jsx"))


def _is_test_file(filename: str) -> bool:
    parts = Path(filename).parts
    stem = Path(filename).stem.lower()
    return (
        any(marker in (p.lower() for p in parts) for marker in _TEST_DIR_MARKERS)
        or stem.startswith("test_")
        or stem.endswith("_test")
        or stem.endswith(".test")
        or stem.endswith(".spec")
    )


def _strip_test_affixes(stem: str) -> str:
    for prefix in ("test_",):
        if stem.startswith(prefix):
            return stem[len(prefix):]
    for suffix in ("_test", ".test", ".spec", "_spec"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem
