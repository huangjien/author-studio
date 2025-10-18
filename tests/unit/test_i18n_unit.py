from src.core.i18n import (
    choose_language,
    get_localized_prompt,
    parse_accept_language,
)


def test_parse_accept_language_handles_invalid_q():
    # Invalid q-value should default to 1.0 and not crash
    ordered = parse_accept_language("es;q=bad,en;q=0.5")
    # Expect Spanish prioritized over English due to default q=1.0
    assert ordered[0] in ("es", "es-bad") or ordered[0].startswith("es")
    assert "en" in ordered


def test_choose_language_no_available_returns_default():
    lang = choose_language([], accept_language="es", default="en")
    assert lang == "en"


def test_choose_language_default_not_present_falls_back_to_first_available():
    lang = choose_language(["fr"], accept_language="de", default="zz")
    assert lang == "fr"


def test_get_localized_prompt_missing_key_returns_none():
    key, prompt = get_localized_prompt({}, accept_language="es")
    # Default key is 'en' when nothing available
    assert key == "en"
    assert prompt is None
