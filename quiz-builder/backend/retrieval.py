"""
retrieval.py
------------
Responsible for ONE thing only: fetching real-world factual context
about a topic from Wikipedia before we ask the LLM to write questions.

Why this exists (interview talking point):
Without this step, the LLM generates quiz questions purely from its own
training memory. That risks hallucinated facts (wrong dates, wrong names,
made-up statistics). By grounding the LLM with a real Wikipedia summary
first, we reduce hallucination -- this is a lightweight form of RAG
(Retrieval-Augmented Generation).

This module also exposes `topic_has_any_match`, which uses Wikipedia's
"opensearch" (autocomplete-style) endpoint as a second, stronger signal
for whether a topic is real -- it catches near-misses (e.g. slightly
different capitalization or phrasing) AND clear gibberish (e.g. "qwerty",
"sgndklsg"), which a simple letter-pattern heuristic alone cannot reliably
distinguish.
"""

import requests


WIKI_API_URL = "https://en.wikipedia.org/w/api.php"


def fetch_topic_context(topic: str, sentences: int = 8) -> str:
    """
    Fetch a plain-text summary of `topic` from Wikipedia.

    Returns an empty string if no page is found, so the caller can
    decide to fall back to LLM-only generation instead of crashing.
    """
    params = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "exintro": True,       # only the intro section, not the whole article
        "explaintext": True,   # plain text, not wiki markup/HTML
        "titles": topic,
        "redirects": 1,        # follow redirects (e.g. "AI" -> "Artificial intelligence")
    }

    try:
        response = requests.get(WIKI_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        pages = data.get("query", {}).get("pages", {})
        for page_id, page_data in pages.items():
            if page_id == "-1":  # Wikipedia's code for "page not found"
                return ""
            extract = page_data.get("extract", "")
            if extract:
                # Trim to a reasonable number of sentences so we don't
                # blow up the LLM prompt with a huge wall of text.
                trimmed = _trim_to_sentences(extract, sentences)
                return trimmed
        return ""
    except requests.RequestException:
        # Network issue, timeout, etc. -- fail soft, not hard.
        return ""


def topic_has_any_match(topic: str) -> bool:
    """
    Uses Wikipedia's "opensearch" endpoint (the same kind of API that
    powers its search-bar autocomplete) to check whether ANYTHING
    resembling this topic exists -- even if `fetch_topic_context` found
    no exact page match.

    This is a much stronger signal than a letter-pattern heuristic for
    telling real (if obscure or misspelled) topics apart from pure
    gibberish like "qwerty" or "sgndklsg", which return zero suggestions.

    Fails soft (returns True) on network errors, so a connectivity issue
    never blocks a legitimate topic -- we'd rather risk one bad quiz than
    block real topics when our own network check is the thing failing.
    """
    params = {
        "action": "opensearch",
        "search": topic,
        "limit": 1,
        "namespace": 0,
        "format": "json",
    }

    try:
        response = requests.get(WIKI_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        # opensearch returns [query, [matching titles], [descriptions], [urls]]
        matching_titles = data[1] if len(data) > 1 else []
        return len(matching_titles) > 0
    except (requests.RequestException, IndexError, ValueError):
        return True


def _trim_to_sentences(text: str, max_sentences: int) -> str:
    sentences_list = text.replace("\n", " ").split(". ")
    trimmed = ". ".join(sentences_list[:max_sentences])
    if trimmed and not trimmed.endswith("."):
        trimmed += "."
    return trimmed
