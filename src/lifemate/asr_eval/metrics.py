from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from collections import Counter


FUZZY_MATCH_THRESHOLD = 0.8


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace without changing Vietnamese diacritics."""

    normalized = unicodedata.normalize("NFC", str(text))
    return " ".join(normalized.split())


def normalize_text_relaxed(text: str) -> str:
    """Normalize case, punctuation, Unicode and whitespace for relaxed scoring."""

    normalized = unicodedata.normalize("NFC", str(text)).lower()
    without_punctuation = "".join(
        character for character in normalized if not unicodedata.category(character).startswith("P")
    )
    return " ".join(without_punctuation.split())


def edit_distance(reference: Sequence[str], hypothesis: Sequence[str]) -> int:
    """Return Levenshtein distance between two token sequences."""

    previous = list(range(len(hypothesis) + 1))
    for index, reference_token in enumerate(reference, start=1):
        current = [index]
        for hypothesis_index, hypothesis_token in enumerate(hypothesis, start=1):
            substitution = previous[hypothesis_index - 1] + (reference_token != hypothesis_token)
            insertion = current[hypothesis_index - 1] + 1
            deletion = previous[hypothesis_index] + 1
            current.append(min(substitution, insertion, deletion))
        previous = current
    return previous[-1]


def _error_rate(reference: Sequence[str], hypothesis: Sequence[str]) -> float:
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return edit_distance(reference, hypothesis) / len(reference)


def token_f1(reference: Sequence[str], hypothesis: Sequence[str]) -> float:
    """Return multiset token F1, preserving duplicate-token counts."""

    if not reference and not hypothesis:
        return 1.0
    if not reference or not hypothesis:
        return 0.0
    reference_counts = Counter(reference)
    hypothesis_counts = Counter(hypothesis)
    overlap = sum((reference_counts & hypothesis_counts).values())
    precision = overlap / len(hypothesis)
    recall = overlap / len(reference)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def wer(reference: str, hypothesis: str) -> float:
    reference_tokens = normalize_text(reference).split()
    hypothesis_tokens = normalize_text(hypothesis).split()
    return _error_rate(reference_tokens, hypothesis_tokens)


def cer(reference: str, hypothesis: str) -> float:
    reference_chars = list(normalize_text(reference))
    hypothesis_chars = list(normalize_text(hypothesis))
    return _error_rate(reference_chars, hypothesis_chars)


def transcript_metrics(reference: str, prediction: str) -> dict[str, object]:
    reference_normalized = normalize_text(reference)
    prediction_normalized = normalize_text(prediction)
    relaxed_reference = normalize_text_relaxed(reference)
    relaxed_prediction = normalize_text_relaxed(prediction)
    fuzzy_score = token_f1(relaxed_reference.split(), relaxed_prediction.split())
    return {
        "reference_normalized": reference_normalized,
        "prediction_normalized": prediction_normalized,
        "wer": _error_rate(reference_normalized.split(), prediction_normalized.split()),
        "cer": _error_rate(list(reference_normalized), list(prediction_normalized)),
        "exact_match": reference_normalized == prediction_normalized,
        "relaxed_reference_normalized": relaxed_reference,
        "relaxed_prediction_normalized": relaxed_prediction,
        "relaxed_wer": _error_rate(relaxed_reference.split(), relaxed_prediction.split()),
        "relaxed_cer": _error_rate(list(relaxed_reference), list(relaxed_prediction)),
        "relaxed_exact_match": relaxed_reference == relaxed_prediction,
        "fuzzy_token_f1": fuzzy_score,
        "fuzzy_match": fuzzy_score >= FUZZY_MATCH_THRESHOLD,
    }
