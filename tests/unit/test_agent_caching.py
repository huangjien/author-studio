from src.services.agent_service import compute_output
from src.services.cache import cache_clear


def setup_function(function):
    # Reset cache and call counter before each test
    cache_clear()
    # Reset call count
    import src.services.agent_service as agent_service

    agent_service.compute_output_call_count = 0


def test_compute_output_memoization_same_params():
    # First call should compute and increment counter
    out1 = compute_output(
        agent_id="example-agent",
        input_text="Hello",
        selected_lang="en",
        prompt_text="You are a helpful assistant.",
    )
    # Second call with identical parameters should hit cache (no extra increments)
    out2 = compute_output(
        agent_id="example-agent",
        input_text="Hello",
        selected_lang="en",
        prompt_text="You are a helpful assistant.",
    )
    # Outputs should match
    assert out1 == out2

    # Verify call count is 1 due to memoization
    import src.services.agent_service as agent_service

    assert agent_service.compute_output_call_count == 1


def test_compute_output_memoization_different_lang():
    # First call with English
    _ = compute_output(
        agent_id="example-agent",
        input_text="Hello",
        selected_lang="en",
        prompt_text="You are a helpful assistant.",
    )
    # Second call with Spanish (different cache key)
    _ = compute_output(
        agent_id="example-agent",
        input_text="Hello",
        selected_lang="es",
        prompt_text="Eres un asistente útil.",
    )

    import src.services.agent_service as agent_service

    # Should have computed both calls
    assert agent_service.compute_output_call_count == 2