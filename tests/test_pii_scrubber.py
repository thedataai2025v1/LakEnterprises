"""Unit tests for PII and Secret Scrubber (PIIScrubber)."""

from lakenterprises.guardrails.pii_scrubber import PIIScrubber, _luhn_checksum


class TestLuhnAlgorithm:
    def test_valid_visa_and_mastercard(self):
        # Standard test card numbers (Luhn valid)
        assert _luhn_checksum("4532015112830366") is True
        assert _luhn_checksum("5425233430109903") is True

    def test_invalid_card(self):
        assert _luhn_checksum("4532015112830367") is False
        assert _luhn_checksum("12345") is False


class TestPIIScrubber:
    def test_scrub_empty_and_safe_text(self):
        scrubber = PIIScrubber()
        assert scrubber.scrub_text("").scrubbed_text == ""
        res = scrubber.scrub_text("Hello enterprise world!")
        assert res.scrubbed_text == "Hello enterprise world!"
        assert not res.has_findings

    def test_scrub_aws_and_openai_api_keys(self):
        scrubber = PIIScrubber()
        text = "Deploying with AKIAIOSFODNN7EXAMPLE and key sk-abcdef1234567890abcdef123456"
        res = scrubber.scrub_text(text)
        assert res.contains_secrets is True
        assert "AKIAIOSFODNN7EXAMPLE" not in res.scrubbed_text
        assert "[REDACTED_AWS_KEY]" in res.scrubbed_text
        assert "[REDACTED_API_KEY]" in res.scrubbed_text
        assert len(res.detections) == 2

    def test_scrub_jwt_token(self):
        scrubber = PIIScrubber()
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotShareThisSignature12345"
        res = scrubber.scrub_text(f"Bearer {jwt}")
        assert res.contains_secrets is True
        assert jwt not in res.scrubbed_text
        assert "[REDACTED_JWT]" in res.scrubbed_text

    def test_scrub_private_key(self):
        scrubber = PIIScrubber()
        pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0Y...\n-----END RSA PRIVATE KEY-----"
        res = scrubber.scrub_text(f"Server key:\n{pem}")
        assert res.contains_secrets is True
        assert "[REDACTED_PRIVATE_KEY]" in res.scrubbed_text
        assert "-----BEGIN RSA PRIVATE KEY-----" not in res.scrubbed_text

    def test_scrub_database_connection_string_password(self):
        scrubber = PIIScrubber()
        uri = "postgres://app_user:superSecretPass123@db.internal:5432/enterprise"
        res = scrubber.scrub_text(f"Connecting to {uri}")
        assert res.contains_secrets is True
        assert "superSecretPass123" not in res.scrubbed_text
        assert "[REDACTED_PASSWORD]" in res.scrubbed_text

    def test_scrub_ssn_and_phone(self):
        scrubber = PIIScrubber()
        text = "SSN is 987-65-4321 and contact phone is (555) 234-5678."
        res = scrubber.scrub_text(text)
        assert res.contains_pii is True
        assert "987-65-4321" not in res.scrubbed_text
        assert "[REDACTED_SSN]" in res.scrubbed_text
        assert "[REDACTED_PHONE]" in res.scrubbed_text

    def test_scrub_email_address(self):
        scrubber = PIIScrubber()
        text = "Email alice.henderson@acmeglobal.com for IT queries."
        res = scrubber.scrub_text(text)
        assert res.contains_pii is True
        assert "alice.henderson@acmeglobal.com" not in res.scrubbed_text
        assert "[REDACTED_EMAIL]" in res.scrubbed_text

    def test_scrub_credit_card(self):
        scrubber = PIIScrubber()
        text = "Charged to card 4532 0151 1283 0366."
        res = scrubber.scrub_text(text)
        assert res.contains_pii is True
        assert "4532 0151 1283 0366" not in res.scrubbed_text
        assert "[REDACTED_CREDIT_CARD]" in res.scrubbed_text

    def test_scrub_nested_dict(self):
        scrubber = PIIScrubber()
        data = {
            "customer": {
                "name": "Alice",
                "email": "alice@acmeglobal.com",
                "orders": [{"id": 1, "card": "4532015112830366"}],
            },
            "status": "ok",
        }
        scrubbed = scrubber.scrub_dict(data)
        assert scrubbed["customer"]["email"] == "[REDACTED_EMAIL]"
        assert scrubbed["customer"]["orders"][0]["card"] == "[REDACTED_CREDIT_CARD]"
        assert scrubbed["status"] == "ok"
