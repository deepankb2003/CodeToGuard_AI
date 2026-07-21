from app.agents.test_gap import test_gap_agent as run_test_gap_agent


def test_flags_file_without_matching_test():
    state = {"files": [{"filename": "app/utils/helper.py", "status": "added"}]}
    result = run_test_gap_agent(state)
    assert len(result["test_gap_findings"]) == 1
    assert result["test_gap_findings"][0]["file"] == "app/utils/helper.py"


def test_skips_file_with_matching_test():
    state = {
        "files": [
            {"filename": "app/utils/helper.py", "status": "added"},
            {"filename": "tests/test_helper.py", "status": "added"},
        ]
    }
    result = run_test_gap_agent(state)
    assert result["test_gap_findings"] == []
