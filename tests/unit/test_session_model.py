import json
from datetime import datetime, timedelta, timezone

from src.core.models.session import Session


def test_session_serializes_created_at_with_timezone_aware_isoformat():
    created = datetime.now(timezone.utc)
    s = Session(session_id="sess-1", agent_id="alpha-bot", created_at=created)

    payload = json.loads(s.model_dump_json())
    ts = payload["created_at"]
    # Normalize potential 'Z' suffix to '+00:00' for fromisoformat
    ts_norm = ts.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(ts_norm)

    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)


def test_session_history_default_is_not_shared_between_instances():
    created1 = datetime.now(timezone.utc)
    created2 = datetime.now(timezone.utc)
    s1 = Session(session_id="sess-1", agent_id="alpha-bot", created_at=created1)
    s2 = Session(session_id="sess-2", agent_id="beta-bot", created_at=created2)

    assert s1.history == []
    assert s2.history == []

    data = {"role": "user", "content": "Hello"}
    s1.history.append(data)

    assert s1.history == [data]
    assert s2.history == []