"""
validation.py
--------------
Responsible for ONE thing only: a cheap, fast sanity check on whether a
topic string looks like real language (vs random keyboard mashing like
"sgndklsg") before we spend an LLM call generating questions about it.

Why this exists:
The LLM has no built-in way to say "this isn't a real topic" -- if you
ask it to write a quiz about "sgndklsg", it will confidently hallucinate
one instead of refusing. This module catches the obvious gibberish cases
*before* that happens, using retrieval (Wikipedia) as a free signal.

This is intentionally simple, not a full NLP pipeline -- it's a guardrail,
not a classifier. It only kicks in when Wikipedia retrieval has ALREADY
found nothing for the topic; it's the second layer of defense, not the
only one.
"""

import re


# A topic is treated as "looks like real language" if it contains at
# least one recognizable English-like word of 3+ letters using normal
# vowel/consonant patterns. This is deliberately lenient -- false
# positives (letting real topics through) are far less costly than
# false negatives (blocking a real topic the user actually wanted).
VOWELS = set("aeiouyAEIOUY")  # 'y' often acts as a vowel sound (e.g. "rhythm", "myth")


def is_topic_too_vague(topic: str) -> bool:
    """
    Returns True if the topic looks like gibberish rather than a real
    word or phrase, e.g. "sgndklsg" or "xkqzwpl".

    Heuristic: real English words almost always contain at least one
    vowel for every few consonants, and rarely repeat the same character
    3+ times in a row. We require at least half of the words in the topic
    to look real -- requiring just ONE real-looking word was too lenient,
    since a short fragment (e.g. "kjyu") can look word-like by chance even
    when the rest of the topic is clearly gibberish.
    """
    cleaned = re.sub(r"[^a-zA-Z\s]", "", topic).strip()

    if not cleaned:
        # Topic was purely numbers/symbols (e.g. "12345") -- also too vague.
        return True

    words = cleaned.split()
    real_count = sum(1 for word in words if _looks_like_real_word(word))

    return real_count < len(words) / 2


def _looks_like_real_word(word: str) -> bool:
    if len(word) < 3:
        # Too short to judge reliably (e.g. "AI", "ML" are real but short --
        # we let short words through by default rather than risk blocking them).
        return True

    if _has_long_repeated_character(word):
        # Real English words almost never repeat the same letter 3+ times
        # in a row (e.g. "aaaa", "dddddd"). This catches vowel-heavy
        # gibberish that would otherwise pass the vowel-ratio check below
        # (e.g. typing the same key repeatedly).
        return False

    vowel_count = sum(1 for ch in word if ch in VOWELS)

    # Real English words have a vowel roughly every 1-3 letters on average.
    # Pure keyboard-mashing strings (e.g. "sgndklsg", "xkqzwpl") tend to have
    # zero vowels, or a vowel ratio far below what real words show.
    # This is a simple ratio check rather than a consonant-run count,
    # since real words (e.g. "strengths", "rhythm") can have unusual
    # consonant clusters that a strict run-length check misclassifies.
    vowel_ratio = vowel_count / len(word)

    return vowel_ratio >= 0.1


def _has_long_repeated_character(word: str) -> bool:
    """True if any single character repeats 3+ times consecutively."""
    run_length = 1
    for i in range(1, len(word)):
        if word[i].lower() == word[i - 1].lower():
            run_length += 1
            if run_length >= 3:
                return True
        else:
            run_length = 1
    return False
