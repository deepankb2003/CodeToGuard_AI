"""Endpoints for browsing past reviews, and for running a new one on demand."""
from fastapi import APIRouter, HTTPException
from github import GithubException
from pydantic import BaseModel
from sqlalchemy import select

from app.agents.graph import review_graph
from app.db.models import Review
from app.db.repository import save_review
from app.db.session import get_session
from app.integrations.github_client import get_client, get_pr_diff

router = APIRouter(prefix="/reviews", tags=["reviews"])


class RunReviewRequest(BaseModel):
    repo_full_name: str
    # If omitted, the repo's most recent open PR is used. If given, that
    # exact PR is reviewed regardless of state (open, closed, or merged).
    pr_number: int | None = None


@router.get("")
def list_reviews(repo: str | None = None, limit: int = 50):
    session = get_session()
    try:
        stmt = select(Review).order_by(Review.created_at.desc()).limit(limit)
        if repo:
            stmt = stmt.where(Review.repo_full_name == repo)
        reviews = session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id,
                "repo_full_name": r.repo_full_name,
                "pr_number": r.pr_number,
                "pr_title": r.pr_title,
                "created_at": r.created_at.isoformat(),
                "finding_count": len(r.findings),
            }
            for r in reviews
        ]
    finally:
        session.close()


@router.post("/run")
def run_review(payload: RunReviewRequest):
    """
    Fetches a PR from the given repo and runs the full review pipeline
    against it for real, saving the result. No GitHub comment is posted.

    If `pr_number` is given, that exact PR is reviewed regardless of its
    state (open, closed, or merged). If omitted, the repo's most recent
    open PR is used instead.
    """
    repo_full_name = payload.repo_full_name.strip()
    if "/" not in repo_full_name:
        raise HTTPException(status_code=400, detail="Repo must be in 'owner/name' format.")

    client = get_client()

    try:
        repo = client.get_repo(repo_full_name)
        if payload.pr_number is not None:
            pr_number = payload.pr_number
        else:
            open_prs = list(repo.get_pulls(state="open", sort="created", direction="desc"))
            if not open_prs:
                raise HTTPException(status_code=404, detail=f"No open pull requests found on '{repo_full_name}'.")
            pr_number = open_prs[0].number
    except GithubException as e:
        raise HTTPException(status_code=_map_status(e), detail=_github_error_message(e, repo_full_name))

    try:
        diff = get_pr_diff(repo_full_name, pr_number, client=client)
    except GithubException as e:
        detail = f"PR #{pr_number} not found on '{repo_full_name}'." if e.status == 404 else _github_error_message(e, repo_full_name)
        raise HTTPException(status_code=_map_status(e), detail=detail)

    state = {
        "repo_full_name": repo_full_name,
        "pr_number": pr_number,
        "pr_title": diff["title"],
        "head_sha": diff["head_sha"],
        "files": diff["files"],
        "security_findings": [],
        "quality_findings": [],
        "test_gap_findings": [],
        "documentation_findings": [],
        "lint_findings": [],
        "typing_findings": [],
        "api_change_findings": [],
        "aggregated_report": "",
    }

    result = review_graph.invoke(state)
    review_id = save_review(result)
    return get_review(review_id)


def _map_status(e: GithubException) -> int:
    return e.status if e.status in (401, 403, 404) else 502


def _github_error_message(e: GithubException, repo_full_name: str) -> str:
    if e.status == 404:
        return f"Repo '{repo_full_name}' not found, or your GitHub token doesn't have access to it."
    message = e.data.get("message", str(e)) if isinstance(e.data, dict) else str(e)
    return f"GitHub error: {message}"


@router.get("/{review_id}")
def get_review(review_id: int):
    session = get_session()
    try:
        review = session.get(Review, review_id)
        if review is None:
            raise HTTPException(status_code=404, detail="Review not found")
        return {
            "id": review.id,
            "repo_full_name": review.repo_full_name,
            "pr_number": review.pr_number,
            "pr_title": review.pr_title,
            "created_at": review.created_at.isoformat(),
            "report_markdown": review.report_markdown,
            "findings": [
                {
                    "file": f.file,
                    "line": f.line,
                    "severity": f.severity,
                    "message": f.message,
                    "source_agent": f.source_agent,
                }
                for f in review.findings
            ],
        }
    finally:
        session.close()
