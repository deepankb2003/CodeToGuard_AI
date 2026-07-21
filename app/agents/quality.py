"""
Quality agent: reviews each changed file's diff against excerpts retrieved
from the repo's coding-standards doc (RAG), rather than asking the LLM to
apply generic, ungrounded taste.
"""
from app.agents.llm import ask_json
from app.agents.state import Finding
from app.rag.store import query_standards

_SYSTEM_PROMPT = (
    "You are a code quality reviewer. You are given a unified diff for one "
    "file and excerpts from this repo's coding-standards doc. Flag ONLY "
    "violations of the given standards that are visible in the diff — do not "
    "invent generic advice unrelated to the excerpts. Respond with a JSON "
    "array of objects with keys: line (int or null), severity "
    "(low|medium|high), message. Return an empty array if there are no "
    "violations. No prose outside the JSON."
)


def quality_agent(state: dict) -> dict:
    findings = []
    for f in state["files"]:
        if f["status"] == "removed" or not f.get("patch"):
            continue

        standards = query_standards(f["patch"], n_results=3)
        if not standards:
            continue

        user = (
            f"File: {f['filename']}\n\n"
            f"Coding standards excerpts:\n" + "\n---\n".join(standards) + "\n\n"
            f"Diff:\n{f['patch']}"
        )
        result = ask_json(_SYSTEM_PROMPT, user, max_tokens=1024)
        if not isinstance(result, list):
            continue

        for item in result:
            findings.append(Finding(
                file=f["filename"],
                line=item.get("line"),
                severity=item.get("severity", "low"),
                message=item.get("message", ""),
                source_agent="quality",
            ))

    return {"quality_findings": findings}
