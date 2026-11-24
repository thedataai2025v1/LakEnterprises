"""Unit tests for Output Schema Validator and JSON repair."""

from pydantic import BaseModel

from lakenterprises.guardrails.output_validator import OutputSchemaValidator


class SampleReportModel(BaseModel):
    summary: str
    incident_count: int


class TestOutputSchemaValidator:
    def test_repair_json_fenced_markdown(self):
        validator = OutputSchemaValidator()
        raw = """Here is the response:
```json
{
  "summary": "Database pool starvation resolved.",
  "incident_count": 2,
}
```
"""
        repaired = validator.repair_json_string(raw)
        assert repaired is not None
        assert repaired["summary"] == "Database pool starvation resolved."
        assert repaired["incident_count"] == 2

    def test_validate_pydantic_schema(self):
        validator = OutputSchemaValidator()
        valid_json = '{"summary": "All systems operational", "incident_count": 0}'
        res = validator.validate(
            output_text=valid_json,
            expected_model=SampleReportModel,
        )
        assert res.is_valid is True
        assert res.repaired_output["incident_count"] == 0

    def test_validate_pydantic_schema_invalid(self):
        validator = OutputSchemaValidator()
        invalid_json = '{"summary": "Missing count field"}'
        res = validator.validate(
            output_text=invalid_json,
            expected_model=SampleReportModel,
        )
        assert res.is_valid is False
        assert any("incident_count" in err for err in res.errors)

    def test_validate_valid_citations(self):
        validator = OutputSchemaValidator()
        answer = "The payments outage was resolved at 14:00 [1] by restarting pool workers [2]."
        res = validator.validate(
            output_text=answer,
            valid_evidence_ids=["1", "2", "3"],
        )
        assert res.citations_valid is True
        assert res.found_citations == ["1", "2"]
        assert len(res.invalid_citations) == 0

    def test_detect_hallucinated_citations(self):
        validator = OutputSchemaValidator()
        answer = "Root cause identified in config [1] and customer alerted [99]."
        res = validator.validate(
            output_text=answer,
            valid_evidence_ids=["1", "2"],
        )
        assert res.citations_valid is False
        assert "99" in res.invalid_citations
        assert res.is_valid is False

    def test_detect_credential_leakage_in_output(self):
        validator = OutputSchemaValidator()
        leaking_output = "The database secret was AKIAIOSFODNN7EXAMPLE and sk-abcdef1234567890abcdef123456"
        res = validator.validate(output_text=leaking_output)
        assert res.contains_leakage is True
        assert res.is_valid is False
        assert any("raw credentials" in err.lower() for err in res.errors)

    def test_length_boundary_checks(self):
        validator = OutputSchemaValidator(min_length_chars=5, max_length_chars=20)
        res_short = validator.validate(output_text="hi")
        assert res_short.is_valid is False

        res_long = validator.validate(
            output_text="This is a very long string exceeding twenty chars"
        )
        assert res_long.is_valid is False
