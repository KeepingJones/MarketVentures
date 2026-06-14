"""
Unit tests for data-onboard core logic.

Tests cover:
- Intake form validation (pure validation, no DB or network)
- Gap analysis (pure logic against EXISTING_COVERAGE set)
- QA threshold constants (regression guard on pass/fail criteria)
- Pipeline stage ordering
- Alt data schema shape

No network calls, no external APIs.
"""
# ── Intake validation ─────────────────────────────────────────────────────────

from pipeline.intake import validate_intake, REQUIRED_FIELDS


class TestValidateIntake:
    def _valid_form(self) -> dict:
        return {
            "vendor_name": "Acme Data Ltd",
            "vendor_id": "acme",
            "contact_email": "data@acme.com",
            "api_endpoint": "https://api.acme.com",
            "asset_classes": ["equity", "fx"],
        }

    def test_valid_form_returns_no_errors(self):
        assert validate_intake(self._valid_form()) == []

    def test_missing_vendor_name_is_error(self):
        form = self._valid_form()
        del form["vendor_name"]
        errors = validate_intake(form)
        assert any("vendor_name" in e for e in errors)

    def test_missing_vendor_id_is_error(self):
        form = self._valid_form()
        del form["vendor_id"]
        errors = validate_intake(form)
        assert any("vendor_id" in e for e in errors)

    def test_missing_asset_classes_is_error(self):
        form = self._valid_form()
        del form["asset_classes"]
        errors = validate_intake(form)
        assert any("asset_classes" in e for e in errors)

    def test_string_asset_classes_is_error(self):
        form = self._valid_form()
        form["asset_classes"] = "equity"  # should be a list
        errors = validate_intake(form)
        assert any("asset_classes" in e for e in errors)

    def test_all_required_fields_are_covered(self):
        required = {"vendor_name", "vendor_id", "contact_email", "api_endpoint", "asset_classes"}
        assert required == set(REQUIRED_FIELDS)

    def test_multiple_missing_fields_all_reported(self):
        form = {}
        errors = validate_intake(form)
        assert len(errors) == len(REQUIRED_FIELDS)


# ── Gap analysis ──────────────────────────────────────────────────────────────

from pipeline.intake import run_gap_analysis
from unittest.mock import patch


class TestRunGapAnalysis:
    def _mock_db(self):
        return patch("pipeline.intake.save_coverage_gap")

    def test_new_asset_class_goes_to_new_coverage(self):
        with self._mock_db():
            result = run_gap_analysis("test_vendor", ["crypto"])
        assert "crypto" in result["new_coverage"]

    def test_existing_asset_class_goes_to_duplicates(self):
        with self._mock_db():
            result = run_gap_analysis("test_vendor", ["equity"])
        assert "equity" in result["duplicates"]

    def test_recommendation_proceed_when_new_coverage(self):
        with self._mock_db():
            result = run_gap_analysis("test_vendor", ["crypto", "nft"])
        assert result["recommendation"] == "proceed"

    def test_recommendation_low_value_add_when_all_duplicate(self):
        with self._mock_db():
            result = run_gap_analysis("test_vendor", ["equity", "fx"])
        assert result["recommendation"] == "low_value_add"

    def test_mixed_coverage_recommends_proceed(self):
        with self._mock_db():
            result = run_gap_analysis("test_vendor", ["equity", "crypto"])
        assert result["recommendation"] == "proceed"
        assert "crypto" in result["new_coverage"]
        assert "equity" in result["duplicates"]

    def test_empty_asset_classes_is_low_value(self):
        with self._mock_db():
            result = run_gap_analysis("test_vendor", [])
        assert result["recommendation"] == "low_value_add"


# ── QA thresholds ─────────────────────────────────────────────────────────────

from config import QA_MIN_COMPLETENESS_PCT, QA_MAX_LATENCY_MINUTES, QA_MIN_ACCURACY_PCT


class TestQaThresholds:
    def test_completeness_threshold_is_95_pct(self):
        assert QA_MIN_COMPLETENESS_PCT == 95.0

    def test_latency_threshold_is_30_minutes(self):
        assert QA_MAX_LATENCY_MINUTES == 30

    def test_accuracy_threshold_is_99_pct(self):
        assert QA_MIN_ACCURACY_PCT == 99.0

    def test_threshold_logic_pass(self):
        completeness, latency, accuracy = 97.0, 10.0, 99.5
        passed = (
            completeness >= QA_MIN_COMPLETENESS_PCT
            and latency <= QA_MAX_LATENCY_MINUTES
            and accuracy >= QA_MIN_ACCURACY_PCT
        )
        assert passed is True

    def test_threshold_logic_fail_on_completeness(self):
        completeness, latency, accuracy = 90.0, 10.0, 99.5
        passed = (
            completeness >= QA_MIN_COMPLETENESS_PCT
            and latency <= QA_MAX_LATENCY_MINUTES
            and accuracy >= QA_MIN_ACCURACY_PCT
        )
        assert passed is False

    def test_threshold_logic_fail_on_latency(self):
        completeness, latency, accuracy = 97.0, 45.0, 99.5
        passed = (
            completeness >= QA_MIN_COMPLETENESS_PCT
            and latency <= QA_MAX_LATENCY_MINUTES
            and accuracy >= QA_MIN_ACCURACY_PCT
        )
        assert passed is False

    def test_threshold_logic_fail_on_accuracy(self):
        completeness, latency, accuracy = 97.0, 10.0, 95.0
        passed = (
            completeness >= QA_MIN_COMPLETENESS_PCT
            and latency <= QA_MAX_LATENCY_MINUTES
            and accuracy >= QA_MIN_ACCURACY_PCT
        )
        assert passed is False


# ── Pipeline stages ───────────────────────────────────────────────────────────

from config import PIPELINE_STAGES


class TestPipelineStages:
    def test_six_stages_defined(self):
        assert len(PIPELINE_STAGES) == 6

    def test_intake_is_first_stage(self):
        assert PIPELINE_STAGES[0] == "intake"

    def test_go_live_is_last_stage(self):
        assert PIPELINE_STAGES[-1] == "go_live"

    def test_qa_period_before_go_live(self):
        qa_idx = PIPELINE_STAGES.index("qa_period")
        go_live_idx = PIPELINE_STAGES.index("go_live")
        assert qa_idx < go_live_idx

    def test_gap_analysis_before_legal_check(self):
        gap_idx = PIPELINE_STAGES.index("gap_analysis")
        legal_idx = PIPELINE_STAGES.index("legal_check")
        assert gap_idx < legal_idx


# ── Alt data schema ───────────────────────────────────────────────────────────

from config import ALT_DATA_SIGNAL_SCHEMA


class TestAltDataSchema:
    def test_schema_has_required_keys(self):
        required = {"ticker", "sentiment", "revenue_guidance",
                    "earnings_surprise", "key_risks", "source_type", "confidence"}
        assert required <= set(ALT_DATA_SIGNAL_SCHEMA.keys())

    def test_confidence_is_float_type(self):
        assert ALT_DATA_SIGNAL_SCHEMA["confidence"] is float

    def test_key_risks_is_list_type(self):
        assert ALT_DATA_SIGNAL_SCHEMA["key_risks"] is list
