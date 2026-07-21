"""
API-diff agent: compares each modified Python file's public function/class
signatures between the PR's base and head commits to catch breaking changes
— a removed public function/class, a removed required parameter, or a new
required parameter with no default. Pure ast diffing, no LLM involved.

Scope is deliberately limited to module-level functions/classes and their
direct methods (not nested functions or nested classes) — that covers a
file's actual public surface without getting lost in implementation detail.
"""
import ast

from app.agents.state import Finding


def api_diff_agent(state: dict) -> dict:
    findings = []
    for f in state["files"]:
        if f["status"] != "modified" or not f["filename"].endswith(".py"):
            continue
        if not f.get("content") or not f.get("base_content"):
            continue

        try:
            head_sigs = _public_signatures(f["content"])
            base_sigs = _public_signatures(f["base_content"])
        except SyntaxError:
            continue

        findings.extend(_diff_signatures(f["filename"], base_sigs, head_sigs))

    return {"api_change_findings": findings}


def _diff_signatures(filename: str, base_sigs: dict, head_sigs: dict) -> list[Finding]:
    findings = []
    for name, base_sig in base_sigs.items():
        if name not in head_sigs:
            findings.append(Finding(
                file=filename,
                line=base_sig["line"],
                severity="high",
                message=f"Public {base_sig['kind']} '{name}' was removed — this is a breaking API change.",
                source_agent="api_change",
            ))
            continue

        head_sig = head_sigs[name]
        if base_sig["kind"] != "function":
            continue

        removed_required = set(base_sig["required"]) - set(head_sig["required"]) - set(head_sig["optional"])
        added_required = set(head_sig["required"]) - set(base_sig["required"]) - set(base_sig["optional"])

        if removed_required:
            findings.append(Finding(
                file=filename,
                line=head_sig["line"],
                severity="high",
                message=(
                    f"Function '{name}' no longer accepts parameter(s) "
                    f"{sorted(removed_required)} — this is a breaking API change for existing callers."
                ),
                source_agent="api_change",
            ))
        if added_required:
            findings.append(Finding(
                file=filename,
                line=head_sig["line"],
                severity="high",
                message=(
                    f"Function '{name}' now requires new parameter(s) "
                    f"{sorted(added_required)} with no default — this is a breaking API change for existing callers."
                ),
                source_agent="api_change",
            ))

    return findings


def _public_signatures(source: str) -> dict:
    tree = ast.parse(source)
    sigs = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            required, optional = _split_params(node.args)
            sigs[node.name] = {"kind": "function", "line": node.lineno, "required": required, "optional": optional}
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                sigs[node.name] = {"kind": "class", "line": node.lineno, "required": [], "optional": []}
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and not item.name.startswith("_"):
                    required, optional = _split_params(item.args)
                    sigs[f"{node.name}.{item.name}"] = {
                        "kind": "function", "line": item.lineno, "required": required, "optional": optional,
                    }
    return sigs


def _split_params(args: ast.arguments) -> tuple[list[str], list[str]]:
    positional = [a.arg for a in args.posonlyargs + args.args if a.arg != "self"]
    num_defaults = len(args.defaults)
    required = positional[: len(positional) - num_defaults] if num_defaults else positional
    optional = positional[len(positional) - num_defaults:] if num_defaults else []

    kwonly_required = [a.arg for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is None]
    kwonly_optional = [a.arg for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None]

    return required + kwonly_required, optional + kwonly_optional
