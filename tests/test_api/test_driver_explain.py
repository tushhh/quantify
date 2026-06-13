"""
Tests for api.driver_explain — plain-English translation of model drivers.
"""

from __future__ import annotations

import pytest

from api.driver_explain import build_plain_summary, humanize_driver


class TestHumanizeDriver:
    def test_known_feature_higher(self) -> None:
        label, meaning = humanize_driver("rsi_14", "higher")
        assert label == "Momentum"
        assert "stronger" in meaning
        assert "▲" in meaning

    def test_known_feature_lower(self) -> None:
        label, meaning = humanize_driver("sma_crossover", "lower")
        assert label == "Trend"
        assert "downtrend" in meaning
        assert "▼" in meaning

    def test_new_volume_feature_translated(self) -> None:
        label, meaning = humanize_driver("volume_price_corr_20d", "higher")
        assert label == "Volume confirmation"
        assert "confirming" in meaning

    def test_sector_rs_feature_translated(self) -> None:
        label, meaning = humanize_driver("sector_rs_21d", "higher")
        assert "sector" in label.lower()
        assert "outperforming" in meaning

    def test_unknown_feature_fallback(self) -> None:
        label, meaning = humanize_driver("some_brand_new_feat", "higher")
        # Tidied label, generic direction-aware meaning — never raises
        assert label == "Some brand new feat"
        assert "above average" in meaning

    @pytest.mark.parametrize("direction", ["higher", "HIGHER", "h", "High"])
    def test_direction_case_insensitive_high(self, direction: str) -> None:
        _, meaning = humanize_driver("rsi_14", direction)
        assert "stronger" in meaning

    def test_every_glossary_entry_has_both_directions(self) -> None:
        from api.driver_explain import _GLOSSARY

        for feat, entry in _GLOSSARY.items():
            assert "label" in entry, f"{feat} missing label"
            assert "high" in entry, f"{feat} missing high"
            assert "low" in entry, f"{feat} missing low"


class _Exp:
    """Minimal stand-in for PredictionExplanation."""

    def __init__(self, feature: str, direction: str = "higher") -> None:
        self.feature = feature
        self.direction = direction


class TestBuildPlainSummary:
    def test_two_drivers_joined_with_and(self) -> None:
        exps = [_Exp("rsi_14", "higher"), _Exp("volume_price_corr_20d", "higher")]
        summary = build_plain_summary("long", exps)
        assert summary is not None
        assert " and " in summary
        assert "▲" not in summary and "▼" not in summary  # arrows stripped

    def test_single_driver_no_and(self) -> None:
        summary = build_plain_summary("short", [_Exp("sma_crossover", "lower")])
        assert summary is not None
        assert " and " not in summary

    def test_empty_returns_none(self) -> None:
        assert build_plain_summary("long", []) is None

    def test_works_with_dicts(self) -> None:
        exps = [
            {"feature": "rsi_14", "direction": "higher"},
            {"feature": "mfi_14", "direction": "higher"},
        ]
        summary = build_plain_summary("long", exps)
        assert summary is not None
        assert "money" in summary.lower()

    def test_max_drivers_respected(self) -> None:
        exps = [
            _Exp("rsi_14", "higher"),
            _Exp("mfi_14", "higher"),
            _Exp("sma_crossover", "higher"),
        ]
        summary = build_plain_summary("long", exps, max_drivers=1)
        assert summary is not None
        assert " and " not in summary

    def test_duplicate_clauses_deduplicated(self) -> None:
        # obv_slope and volume_trend both map to "rising"/"accumulating" style;
        # use two features with identical meaning to confirm dedup keeps it clean.
        exps = [_Exp("volume_ratio_20d", "higher"), _Exp("volume_ratio_20d", "higher")]
        summary = build_plain_summary("long", exps)
        assert summary is not None
        assert " and " not in summary  # the duplicate is collapsed

    def test_skips_explanation_without_feature(self) -> None:
        exps = [{"direction": "higher"}, {"feature": "rsi_14", "direction": "higher"}]
        summary = build_plain_summary("long", exps)
        assert summary is not None
        assert "stronger" in summary
