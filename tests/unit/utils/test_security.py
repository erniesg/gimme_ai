"""Tests for security utilities - secret masking and secure logging."""

import pytest
import logging
from gimme_ai.utils.security import SecretMasker, SecureLogger, mask_secrets, get_secure_logger


class TestSecretMasker:
    """Test cases for SecretMasker class."""
    
    def test_mask_openai_api_key(self):
        """Test masking of OpenAI API keys."""
        masker = SecretMasker()
        
        # Test various formats
        test_cases = [
            ("sk-1234567890abcdef1234567890abcdef", "sk-***MASKED***"),
            ("API_KEY=sk-1234567890abcdef1234567890abcdef", "API_KEY=sk-***MASKED***"),
            ("Authorization: Bearer sk-1234567890abcdef1234567890abcdef", "Authorization: Bearer sk-***MASKED***"),
        ]
        
        for input_text, expected in test_cases:
            result = masker.mask_string(input_text)
            assert "sk-***MASKED***" in result
            assert "1234567890abcdef" not in result
    
    def test_mask_replicate_token(self):
        """Test masking of Replicate tokens."""
        masker = SecretMasker()
        
        test_text = "REPLICATE_API_TOKEN=r8_1234567890abcdefghijklmnopqrstuvwxyz"
        result = masker.mask_string(test_text)
        
        assert "r8_***MASKED***" in result
        assert "1234567890abcdefghijklmnopqrstuvwxyz" not in result
    
    def test_mask_generic_api_key(self):
        """Test masking of generic API keys."""
        masker = SecretMasker()
        
        test_text = "api_key=abcd1234567890efgh"
        result = masker.mask_string(test_text)
        
        assert "***MASKED***" in result
        assert "abcd1234567890efgh" not in result
    
    def test_mask_headers(self):
        """Test masking of sensitive headers."""
        masker = SecretMasker()
        
        headers = {
            "Authorization": "Bearer sk-1234567890abcdef",
            "X-API-Key": "secret123456789",
            "Content-Type": "application/json",
            "User-Agent": "test-agent"
        }
        
        masked = masker.mask_headers(headers)
        
        assert masked["Authorization"] == "***MASKED***"
        assert masked["X-API-Key"] == "***MASKED***"
        assert masked["Content-Type"] == "application/json"  # Should not be masked
        assert masked["User-Agent"] == "test-agent"  # Should not be masked
    
    def test_mask_dict(self):
        """Test masking of dictionary values."""
        masker = SecretMasker()
        
        data = {
            "api_key": "sk-1234567890abcdef1234567890abcdef",  # Make it longer to trigger pattern
            "user": "test_user",
            "config": {
                "token": "secret123456789abcdefghij",  # Make it longer to trigger pattern
                "timeout": 30
            }
        }
        
        masked = masker.mask_dict(data)
        
        assert masked["api_key"] == "sk-***MASKED***"
        assert masked["user"] == "test_user"
        assert "***MASKED***" in str(masked["config"]["token"])
        assert masked["config"]["timeout"] == 30
    
    def test_mask_nested_secrets(self):
        """Test masking of nested secrets in complex data."""
        masker = SecretMasker()
        
        text = """
        {
            "auth": {
                "type": "bearer",
                "token": "sk-1234567890abcdef1234567890abcdef"
            },
            "replicate_token": "r8_abcdefghijklmnopqrstuvwxyz123456",
            "normal_data": "this should not be masked"
        }
        """
        
        result = masker.mask_string(text)
        
        assert "sk-***MASKED***" in result
        assert "r8_***MASKED***" in result
        assert "this should not be masked" in result
        assert "1234567890abcdef" not in result
        assert "abcdefghijklmnopqrstuvwxyz123456" not in result


class TestSecureLogger:
    """Test cases for SecureLogger class."""
    
    def test_secure_logger_masks_secrets(self, caplog):
        """Test that SecureLogger masks secrets in log messages."""
        logger = logging.getLogger("test_secure")
        secure_logger = SecureLogger(logger)
        
        with caplog.at_level(logging.INFO):
            secure_logger.info("API Key: sk-1234567890abcdef1234567890abcdef")
        
        # Check that the secret was masked in the log
        assert len(caplog.records) == 1
        assert "sk-***MASKED***" in caplog.records[0].message
        assert "1234567890abcdef" not in caplog.records[0].message
    
    def test_secure_logger_handles_formatting(self, caplog):
        """Test that SecureLogger handles string formatting correctly."""
        logger = logging.getLogger("test_secure_format")
        secure_logger = SecureLogger(logger)
        
        with caplog.at_level(logging.ERROR):
            secure_logger.error("Request failed with token %s", "sk-1234567890abcdef1234567890abcdef")
        
        assert len(caplog.records) == 1
        assert "sk-***MASKED***" in caplog.records[0].message
        assert "1234567890abcdef" not in caplog.records[0].message
    
    def test_get_secure_logger_function(self):
        """Test the get_secure_logger convenience function."""
        secure_logger = get_secure_logger("test_function")
        
        assert isinstance(secure_logger, SecureLogger)
        assert secure_logger.logger.name == "test_function"


class TestMaskSecretsFunction:
    """Test cases for the mask_secrets convenience function."""
    
    def test_mask_secrets_string(self):
        """Test mask_secrets function with string input."""
        result = mask_secrets("Token: sk-1234567890abcdef1234567890abcdef")
        
        assert "sk-***MASKED***" in result
        assert "1234567890abcdef" not in result
    
    def test_mask_secrets_dict(self):
        """Test mask_secrets function with dictionary input."""
        data = {
            "auth_token": "sk-1234567890abcdef1234567890abcdef",  # Make it longer
            "username": "test_user"
        }
        
        result = mask_secrets(data)
        
        assert result["auth_token"] == "sk-***MASKED***"
        assert result["username"] == "test_user"
    
    def test_mask_secrets_preserves_other_types(self):
        """Test that mask_secrets preserves non-string/dict types."""
        assert mask_secrets(123) == 123
        assert mask_secrets([1, 2, 3]) == [1, 2, 3]
        assert mask_secrets(None) is None


class TestSecurityPatterns:
    """Test specific security patterns and edge cases."""
    
    def test_aws_key_masking(self):
        """Test masking of AWS access keys."""
        masker = SecretMasker()
        
        text = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
        result = masker.mask_string(text)
        
        assert "AKIA***MASKED***" in result
        assert "IOSFODNN7EXAMPLE" not in result
    
    def test_password_masking(self):
        """Test masking of passwords."""
        masker = SecretMasker()
        
        text = "password=mysecretpassword123"
        result = masker.mask_string(text)
        
        assert "***MASKED***" in result
        assert "mysecretpassword123" not in result
    
    def test_case_insensitive_masking(self):
        """Test that masking works case-insensitively."""
        masker = SecretMasker()
        
        text = "API_KEY=sk-1234567890abcdef1234567890abcdef"
        result = masker.mask_string(text)
        
        assert "sk-***MASKED***" in result
        assert "1234567890abcdef" not in result
    
    def test_no_false_positives(self):
        """Test that normal text is not masked."""
        masker = SecretMasker()
        
        normal_texts = [
            "This is normal text",
            "user_id=12345",
            "filename=test.txt",
            "short=abc",  # Too short to be considered a secret
        ]
        
        for text in normal_texts:
            result = masker.mask_string(text)
            assert result == text  # Should be unchanged