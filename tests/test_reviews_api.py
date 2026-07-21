from fastapi.testclient import TestClient

from app.db.repository import save_review
from app.db.session import init_db
from main import app


def _seed_review() -> int:
    state = {
        "repo_full_name": "acme/widgets",
        "pr_number": 7,
        "pr_title": "Seeded PR",
        "aggregated_report": "## seeded",
        "security_findings": [
            {"file": "a.py", "line": 1, "severity": "high", "message": "m", "source_agent": "security"}
        ],
        "quality_findings": [],
        "test_gap_findings": [],
        "documentation_findings": [],
    }
    return save_review(state)


def test_list_and_get_review():
    init_db()
    review_id = _seed_review()
    client = TestClient(app)

    listed = client.get("/reviews")
    assert listed.status_code == 200
    assert any(r["id"] == review_id for r in listed.json())

    detail = client.get(f"/reviews/{review_id}")
    assert detail.status_code == 200
    assert detail.json()["pr_number"] == 7
    assert len(detail.json()["findings"]) == 1

    missing = client.get("/reviews/999999")
    assert missing.status_code == 404
