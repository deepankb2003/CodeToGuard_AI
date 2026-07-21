"""
Shared state that flows through every node in the LangGraph review graph.
Each specialist agent reads what it needs and writes its own findings key —
they never overwrite each other's sections. The Supervisor node reads all
four findings sections at the end to build the aggregated report.
"""
from typing import TypedDict, List, Dict, Any, Optional


class Finding(TypedDict):
    file: str
    line: Optional[int]
    severity: str          # "critical" | "high" | "medium" | "low" | "info"
    message: str
    source_agent: str      # "security" | "quality" | "test_gap" | "documentation"


class ReviewState(TypedDict):
    # --- input ---
    repo_full_name: str
    pr_number: int
    pr_title: str
    head_sha: str
    files: List[Dict[str, Any]]     # raw diff data from github_client.get_pr_diff

    # --- per-agent outputs (each agent only writes its own key) ---
    security_findings: List[Finding]
    quality_findings: List[Finding]
    test_gap_findings: List[Finding]
    documentation_findings: List[Finding]
    lint_findings: List[Finding]
    typing_findings: List[Finding]
    api_change_findings: List[Finding]

    # --- final output ---
    aggregated_report: str


# Every key an agent writes findings to. Kept as one list so aggregate() and
# save_review() can't drift out of sync when a new agent is added.
FINDING_KEYS = [
    "security_findings",
    "quality_findings",
    "test_gap_findings",
    "documentation_findings",
    "lint_findings",
    "typing_findings",
    "api_change_findings",
]


def all_findings(state: dict) -> List[Finding]:
    result: List[Finding] = []
    for key in FINDING_KEYS:
        result.extend(state.get(key, []))
    return result
