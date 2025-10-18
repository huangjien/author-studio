import importlib


def test_compute_output_no_prefix_uses_echo():
    # Reload to ensure a fresh module state
    from src.services import agent_service as svc

    importlib.reload(svc)

    # No prompt_text provided should hit the no-prefix branch
    out = svc.compute_output("delta-bot", "Ping", "en", None)
    assert out == "[delta-bot] Echo: Ping"
