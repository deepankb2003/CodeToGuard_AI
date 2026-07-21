"""
Thin wrapper around PyGithub. Every place that needs to talk to GitHub
goes through this module, so we have one spot to add retries/rate-limit
handling later, and one spot to swap PyGithub for raw MCP tool calls if
we move to that in a future phase.
"""
from github import Github, Auth
from app.config import settings


def get_client() -> Github:
    auth = Auth.Token(settings.github_token)
    return Github(auth=auth)


def get_pr_diff(repo_full_name: str, pr_number: int, client: Github | None = None) -> dict:
    """
    Fetch a pull request's changed files, their patches, and full post-change
    content (needed by the static-analysis agents, which can't act on a unified
    diff alone).

    Returns:
        {
            "pr_number": int,
            "title": str,
            "head_sha": str,
            "files": [
                {
                    "filename": str,
                    "status": str,          # "added" | "modified" | "removed"
                    "patch": str,            # unified diff text, may be "" for binary files
                    "additions": int,
                    "deletions": int,
                    "content": str | None,   # full file content at the PR head, if fetchable
                    "base_content": str | None,  # full content at the PR base, only for "modified" files
                },
                ...
            ]
        }
    """
    client = client or get_client()
    repo = client.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)
    head_sha = pr.head.sha
    base_sha = pr.base.sha

    files = []
    for f in pr.get_files():
        content = None
        base_content = None
        if f.status != "removed":
            content = _fetch_file_content(repo, f.filename, head_sha)
        if f.status == "modified":
            base_content = _fetch_file_content(repo, f.filename, base_sha)

        files.append({
            "filename": f.filename,
            "status": f.status,
            "patch": f.patch or "",
            "additions": f.additions,
            "deletions": f.deletions,
            "content": content,
            "base_content": base_content,
        })

    return {
        "pr_number": pr_number,
        "title": pr.title,
        "head_sha": head_sha,
        "files": files,
    }


def _fetch_file_content(repo, path: str, ref: str) -> str | None:
    try:
        content_file = repo.get_contents(path, ref=ref)
        return content_file.decoded_content.decode("utf-8", errors="replace")
    except Exception:
        # Binary file, submodule, or file too large for the contents API — skip it.
        return None


def post_pr_comment(repo_full_name: str, pr_number: int, body: str) -> None:
    """Post the aggregated review report as a single PR comment."""
    client = get_client()
    repo = client.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)
    pr.create_issue_comment(body)
