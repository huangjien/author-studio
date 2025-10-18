from typing import Dict, Iterable, List, Optional, Tuple


def _normalize(tag: str) -> str:
    return tag.strip().lower().replace("_", "-")


def parse_accept_language(header_value: Optional[str]) -> List[str]:
    """Parse Accept-Language into a prioritized list of tags.
    Honors q-values for weighting; higher q first. Falls back to base language.
    Example: "es-ES,es;q=0.9,en;q=0.8" -> ["es-es", "es", "en"]
    """
    if not header_value:
        return []
    tokens: List[Tuple[str, float]] = []
    parts = [p.strip() for p in header_value.split(",") if p.strip()]
    for p in parts:
        lang = _normalize(p.split(";", 1)[0])
        q = 1.0
        if ";q=" in p:
            try:
                q = float(p.split(";q=", 1)[1])
            except Exception:
                q = 1.0
        if lang:
            tokens.append((lang, q))
    # Sort by q descending while preserving original order for equal q
    tokens_sorted = sorted(range(len(tokens)), key=lambda i: (-tokens[i][1], i))
    seen = set()
    ordered: List[str] = []
    for idx in tokens_sorted:
        lang, _ = tokens[idx]
        if lang not in seen:
            seen.add(lang)
            ordered.append(lang)
        base = lang.split("-", 1)[0]
        if base and base != lang and base not in seen:
            seen.add(base)
            ordered.append(base)
    return ordered


def choose_language(
    available: Iterable[str],
    accept_language: Optional[str],
    default: str = "en",
) -> str:
    """Choose best language from available keys based on Accept-Language.
    Case-insensitive matching for both exact and base language fallbacks.
    Returns the original available key if found, otherwise default if present,
    otherwise the first available key.
    """
    available_list = list(available)
    if not available_list:
        return default
    # map lower -> original
    lower_map: Dict[str, str] = {k.lower(): k for k in available_list}
    # Try Accept-Language candidates
    for cand in parse_accept_language(accept_language):
        if cand in lower_map:
            return lower_map[cand]
        base = cand.split("-", 1)[0]
        if base in lower_map:
            return lower_map[base]
    # Try default
    if default.lower() in lower_map:
        return lower_map[default.lower()]
    # Fallback to first available
    return available_list[0]


def get_localized_prompt(
    prompts: Dict[str, str],
    accept_language: Optional[str],
) -> Tuple[str, Optional[str]]:
    """Return (selected_language_key, prompt_text) based on language preference.
    If no prompt is found, returns (selected_key, None).
    """
    key = choose_language(prompts.keys(), accept_language, default="en")
    return key, prompts.get(key)
