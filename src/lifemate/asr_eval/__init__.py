"""Offline ASR evaluation helpers and command-line entry point."""

from .metrics import (
    FUZZY_MATCH_THRESHOLD,
    cer,
    normalize_text,
    normalize_text_relaxed,
    transcript_metrics,
    wer,
)

__all__ = [
    "FUZZY_MATCH_THRESHOLD",
    "cer",
    "normalize_text",
    "normalize_text_relaxed",
    "transcript_metrics",
    "wer",
]
