from app.agents.documentation import documentation_agent


def test_flags_missing_docstring():
    state = {
        "files": [{
            "filename": "app/utils/helper.py",
            "status": "added",
            "patch": "+def compute(x):\n+    return x * 2\n",
            "content": "def compute(x):\n    return x * 2\n",
        }]
    }
    result = documentation_agent(state)
    assert len(result["documentation_findings"]) == 1
    assert result["documentation_findings"][0]["file"] == "app/utils/helper.py"


def test_skips_function_with_docstring():
    state = {
        "files": [{
            "filename": "app/utils/helper.py",
            "status": "added",
            "patch": '+def compute(x):\n+    """Doubles x."""\n+    return x * 2\n',
            "content": 'def compute(x):\n    """Doubles x."""\n    return x * 2\n',
        }]
    }
    result = documentation_agent(state)
    assert result["documentation_findings"] == []
