from src.config.validator import validate_config


def test_validate_config_reports_missing_required_keys():
    ok, errors = validate_config({})
    assert not ok
    # Expect all required keys missing
    assert any("Missing required key: name" in e for e in errors)
    assert any("Missing required key: llm" in e for e in errors)
    assert any("Missing required key: workflow" in e for e in errors)
    assert any("Missing required key: prompts" in e for e in errors)


def test_validate_config_type_checks():
    data = {
        "name": 123,
        "llm": [],
        "workflow": [],
        "prompts": [],
    }
    ok, errors = validate_config(data)
    assert not ok
    assert "'name' must be a string" in errors
    assert "'llm' must be an object" in errors
    assert "'workflow' must be an object" in errors
    assert "'prompts' must be an object of language keys" in errors
