"""
Documentation agent: flags Python functions/classes that were added or
modified in the diff but have no docstring in the resulting file. Uses `ast`
against the full post-change file content (which the diff patch alone
doesn't give us) to check for a docstring, and the patch text to figure out
which definitions actually changed in this PR.
"""
import ast
import re

from app.agents.state import Finding

_ADDED_DEF_RE = re.compile(r"^\+\s*(?:async\s+)?(?:def|class)\s+(\w+)")


def documentation_agent(state: dict) -> dict:
    findings = []
    for f in state["files"]:
        if not f["filename"].endswith(".py") or not f.get("content") or f["status"] == "removed":
            continue

        changed_names = _changed_def_names(f.get("patch", ""))
        if not changed_names:
            continue

        try:
            tree = ast.parse(f["content"])
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if node.name not in changed_names:
                continue
            if ast.get_docstring(node):
                continue
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            findings.append(Finding(
                file=f["filename"],
                line=node.lineno,
                severity="low",
                message=f"{kind.capitalize()} '{node.name}' was added/modified without a docstring.",
                source_agent="documentation",
            ))

    return {"documentation_findings": findings}


def _changed_def_names(patch: str) -> set[str]:
    return {m.group(1) for line in patch.splitlines() if (m := _ADDED_DEF_RE.match(line))}
