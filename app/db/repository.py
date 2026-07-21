"""Persistence helpers for storing a completed review and its findings."""
from app.agents.state import all_findings
from app.db.models import Review, FindingRecord
from app.db.session import get_session


def save_review(state: dict) -> int:
    """Persist a completed ReviewState (post-aggregation) and return the new review id."""
    session = get_session()
    try:
        review = Review(
            repo_full_name=state["repo_full_name"],
            pr_number=state["pr_number"],
            pr_title=state["pr_title"],
            report_markdown=state["aggregated_report"],
        )
        review.findings = [
            FindingRecord(
                file=f["file"],
                line=f.get("line"),
                severity=f["severity"],
                message=f["message"],
                source_agent=f["source_agent"],
            )
            for f in all_findings(state)
        ]
        session.add(review)
        session.commit()
        return review.id
    finally:
        session.close()
