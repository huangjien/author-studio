from src.core.i18n import parse_accept_language


def test_parse_accept_language_base_equals_lang_no_duplicate():
    # When the language has no region, base == lang; base should not be appended twice
    assert parse_accept_language("en") == ["en"]


def test_parse_accept_language_base_already_seen_no_duplicate():
    # If base is already present, it should not be appended again when encountering a regional tag
    ordered = parse_accept_language("en, en-US;q=0.9")
    # Expect stable order: 'en' first (q=1.0), then 'en-us'
    assert ordered == ["en", "en-us"]