from lifemate.asr_eval.metrics import cer, normalize_text, transcript_metrics, wer


def test_normalize_text_applies_nfc_and_collapses_whitespace():
    assert normalize_text("A\u0301   B\n C") == "Á B C"


def test_wer_counts_word_edit_operations():
    assert wer("một hai ba", "một bốn ba") == 1 / 3


def test_cer_counts_character_edit_operations():
    assert cer("abc", "adc") == 1 / 3


def test_transcript_metrics_reports_exact_match_after_normalization():
    result = transcript_metrics("Xin   chào", "Xin chào")
    assert result["exact_match"] is True
    assert result["wer"] == 0.0
    assert result["cer"] == 0.0


def test_empty_reference_is_handled_without_division_by_zero():
    assert wer("", "") == 0.0
    assert wer("", "xin chào") == 1.0
    assert cer("", "xin") == 1.0


def test_transcript_metrics_includes_relaxed_case_and_punctuation_metrics():
    result = transcript_metrics("Xin chào, Việt Nam!", "xin chào việt nam")
    assert result["relaxed_reference_normalized"] == "xin chào việt nam"
    assert result["relaxed_prediction_normalized"] == "xin chào việt nam"
    assert result["relaxed_wer"] == 0.0
    assert result["relaxed_cer"] == 0.0
    assert result["relaxed_exact_match"] is True


def test_transcript_metrics_computes_fuzzy_token_f1_with_point_eight_threshold():
    result = transcript_metrics("xin chào bạn", "xin chào")
    assert result["fuzzy_token_f1"] == 0.8
    assert result["fuzzy_match"] is True

    below_threshold = transcript_metrics("xin chào bạn bốn", "xin chào")
    assert below_threshold["fuzzy_token_f1"] == 2 / 3
    assert below_threshold["fuzzy_match"] is False


def test_fuzzy_token_f1_handles_empty_transcripts():
    assert transcript_metrics("", "")["fuzzy_token_f1"] == 1.0
    assert transcript_metrics("", "xin")["fuzzy_token_f1"] == 0.0
