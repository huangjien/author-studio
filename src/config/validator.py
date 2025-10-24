from typing import Any, Dict, List, Tuple

REQUIRED_KEYS = ["name", "llm", "workflow", "prompts"]


def validate_config(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    for key in REQUIRED_KEYS:
        if key not in data:
            errors.append(f"Missing required key: {key}")
    # basic type checks
    if "name" in data and not isinstance(data["name"], str):
        errors.append("'name' must be a string")
    if "llm" in data and not isinstance(data["llm"], dict):
        errors.append("'llm' must be an object")
    if "workflow" in data and not isinstance(data["workflow"], dict):
        errors.append("'workflow' must be an object")
    if "prompts" in data and not isinstance(data["prompts"], dict):
        errors.append("'prompts' must be an object of language keys")
    return (len(errors) == 0, errors)