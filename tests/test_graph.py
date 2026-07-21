from app.agents.graph import aggregate


def test_aggregate_reports_no_findings():
    state = {
        "pr_number": 1,
        "pr_title": "Test PR",
        "security_findings": [],
        "quality_findings": [],
        "test_gap_findings": [],
        "documentation_findings": [],
    }
    result = aggregate(state)
    assert "No findings" in result["aggregated_report"]


def test_aggregate_sorts_by_severity():
    state = {
        "pr_number": 2,
        "pr_title": "Test PR",
        "security_findings": [
            {"file": "a.py", "line": 1, "severity": "low", "message": "m1", "source_agent": "security"}
        ],
        "quality_findings": [
            {"file": "b.py", "line": 2, "severity": "critical", "message": "m2", "source_agent": "quality"}
        ],
        "test_gap_findings": [],
        "documentation_findings": [],
    }
    result = aggregate(state)
    lines = result["aggregated_report"].splitlines()
    critical_idx = next(i for i, l in enumerate(lines) if "CRITICAL" in l)
    low_idx = next(i for i, l in enumerate(lines) if "LOW" in l)
    assert critical_idx < low_idx
