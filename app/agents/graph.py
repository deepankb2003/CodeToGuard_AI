"""
The review graph: one entry point fans out to 7 specialist nodes in parallel,
then a final aggregator node collects everything into one report.
"""
from langgraph.graph import StateGraph, END

from app.agents.state import ReviewState, all_findings
from app.agents.security import security_agent
from app.agents.quality import quality_agent
from app.agents.test_gap import test_gap_agent
from app.agents.documentation import documentation_agent
from app.agents.lint import lint_agent
from app.agents.typing_check import typing_agent
from app.agents.api_diff import api_diff_agent


def aggregate(state: ReviewState) -> dict:
    findings = all_findings(state)

    if not findings:
        report = f"## Code To Guard AI Review — PR #{state['pr_number']}\n\nNo findings."
        return {"aggregated_report": report}

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    findings.sort(key=lambda f: severity_order.get(f["severity"], 5))

    lines = [f"## Code To Guard AI Review — PR #{state['pr_number']}: {state['pr_title']}", ""]
    for f in findings:
        loc = f"{f['file']}:{f['line']}" if f.get("line") else f["file"]
        lines.append(f"- **[{f['severity'].upper()}]** ({f['source_agent']}) {loc} — {f['message']}")

    return {"aggregated_report": "\n".join(lines)}


# ---- graph wiring ----

def build_graph():
    graph = StateGraph(ReviewState)

    graph.add_node("security", security_agent)
    graph.add_node("quality", quality_agent)
    graph.add_node("test_gap", test_gap_agent)
    graph.add_node("documentation", documentation_agent)
    graph.add_node("lint", lint_agent)
    graph.add_node("typing", typing_agent)
    graph.add_node("api_diff", api_diff_agent)
    graph.add_node("aggregate", aggregate)

    specialists = ["security", "quality", "test_gap", "documentation", "lint", "typing", "api_diff"]

    # fan-out: a no-op entry node runs, then every specialist executes in
    # parallel (LangGraph fans them in automatically since they all point
    # to the same downstream "aggregate" node).
    graph.add_node("start", lambda state: state)
    graph.set_entry_point("start")
    for name in specialists:
        graph.add_edge("start", name)
        graph.add_edge(name, "aggregate")

    graph.add_edge("aggregate", END)

    return graph.compile()


review_graph = build_graph()
