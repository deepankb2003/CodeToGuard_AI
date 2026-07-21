"""
FastAPI entrypoint. GitHub sends a POST to /webhook/github whenever a PR is
opened/updated. We verify the signature, pull the diff, run it through the
review graph, and post the aggregated report back as a PR comment.
"""
import hashlib
import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.integrations.github_client import get_pr_diff, post_pr_comment
from app.agents.graph import review_graph
from app.api.reviews import router as reviews_router
from app.db.repository import save_review
from app.db.session import init_db

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("codeguardian")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Code To Guard AI", lifespan=lifespan)
app.include_router(reviews_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
def dashboard():
    """Serves the review-history dashboard (app/static/index.html)."""
    return FileResponse("app/static/index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


def _verify_signature(payload_body: bytes, signature_header: str | None) -> bool:
    """Verify the X-Hub-Signature-256 header GitHub sends with every webhook."""
    if not settings.github_webhook_secret:
        # No secret configured (local dev) — skip verification.
        return True
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        settings.github_webhook_secret.encode(), payload_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@app.post("/webhook/github")
async def github_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if not _verify_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event = request.headers.get("X-GitHub-Event")
    payload = await request.json()

    if event != "pull_request":
        return {"status": "ignored", "reason": f"unhandled event type: {event}"}

    action = payload.get("action")
    if action not in ("opened", "synchronize", "reopened"):
        return {"status": "ignored", "reason": f"unhandled action: {action}"}

    repo_full_name = payload["repository"]["full_name"]
    pr_number = payload["pull_request"]["number"]

    logger.info(f"Reviewing PR #{pr_number} on {repo_full_name}")

    diff = get_pr_diff(repo_full_name, pr_number)

    initial_state = {
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

    result = review_graph.invoke(initial_state)

    post_pr_comment(repo_full_name, pr_number, result["aggregated_report"])
    review_id = save_review(result)

    return {"status": "reviewed", "pr_number": pr_number, "review_id": review_id}