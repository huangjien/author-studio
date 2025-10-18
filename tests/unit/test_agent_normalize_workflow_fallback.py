from src.agents.loader import _normalize_workflow


def test_normalize_workflow_fallback_returns_empty_dict():
    # Provide a value that is neither WorkflowConfig nor dict
    result = _normalize_workflow(123)  # type: ignore[arg-type]
    assert result == {}
