"""Security utilities for secret masking and safe logging."""

import re
import logging
from typing import Any, Dict, Union, Optional

# Patterns for detecting secrets
SECRET_PATTERNS = [
    # OpenAI Keys (most specific first)
    (r'sk-[a-zA-Z0-9]{20,}', r'sk-***MASKED***'),
    
    # Replicate Keys  
    (r'r8_[a-zA-Z0-9]{20,}', r'r8_***MASKED***'),
    
    # AWS Keys
    (r'AKIA[0-9A-Z]{16}', r'AKIA***MASKED***'),
    
    # Bearer tokens
    (r'(bearer\s+)([a-zA-Z0-9_.-]{20,})', r'\1***MASKED***'),
    
    # API Keys (generic patterns)
    (r'(api[_-]?key[_-]?=?["\']?)([a-zA-Z0-9_-]{20,})', r'\1***MASKED***'),
    (r'(token[_-]?=?["\']?)([a-zA-Z0-9_.-]{20,})', r'\1***MASKED***'),
    
    # Generic secrets
    (r'(password[_-]?=?["\']?)([^\s"\']{8,})', r'\1***MASKED***'),
    (r'(secret[_-]?=?["\']?)([^\s"\']{8,})', r'\1***MASKED***'),
    (r'(key[_-]?=?["\']?)([a-zA-Z0-9_.-]{16,})', r'\1***MASKED***'),
]


class SecretMasker:
    """Utility class for masking secrets in logs and error messages."""
    
    def __init__(self, additional_patterns: Optional[list] = None):
        """
        Initialize secret masker.
        
        Args:
            additional_patterns: Additional regex patterns for masking
        """
        self.patterns = SECRET_PATTERNS.copy()
        if additional_patterns:
            self.patterns.extend(additional_patterns)
    
    def mask_string(self, text: str) -> str:
        """
        Mask secrets in a string.
        
        Args:
            text: Text that may contain secrets
            
        Returns:
            Text with secrets masked
        """
        if not isinstance(text, str):
            return str(text)
        
        masked_text = text
        for pattern, replacement in self.patterns:
            masked_text = re.sub(pattern, replacement, masked_text, flags=re.IGNORECASE)
        
        return masked_text
    
    def mask_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mask secrets in dictionary values.
        
        Args:
            data: Dictionary that may contain secrets
            
        Returns:
            Dictionary with secrets masked
        """
        if not isinstance(data, dict):
            return data
        
        masked_data = {}
        for key, value in data.items():
            if isinstance(value, str):
                masked_data[key] = self.mask_string(value)
            elif isinstance(value, dict):
                masked_data[key] = self.mask_dict(value)
            elif isinstance(value, list):
                masked_data[key] = [self.mask_string(item) if isinstance(item, str) else item for item in value]
            else:
                masked_data[key] = value
        
        return masked_data
    
    def mask_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        Mask sensitive headers for logging.
        
        Args:
            headers: HTTP headers dictionary
            
        Returns:
            Headers with sensitive values masked
        """
        sensitive_headers = {
            'authorization', 'x-api-key', 'x-auth-token', 
            'cookie', 'x-access-token', 'bearer'
        }
        
        masked_headers = {}
        for key, value in headers.items():
            if key.lower() in sensitive_headers:
                masked_headers[key] = '***MASKED***'
            else:
                masked_headers[key] = self.mask_string(value)
        
        return masked_headers


# Global instance for easy access
default_masker = SecretMasker()


def mask_secrets(data: Union[str, Dict[str, Any]]) -> Union[str, Dict[str, Any]]:
    """
    Convenience function to mask secrets in data.
    
    Args:
        data: String or dictionary that may contain secrets
        
    Returns:
        Data with secrets masked
    """
    if isinstance(data, str):
        return default_masker.mask_string(data)
    elif isinstance(data, dict):
        return default_masker.mask_dict(data)
    else:
        return data


class SecureLogger:
    """Logger wrapper that automatically masks secrets."""
    
    def __init__(self, logger: logging.Logger, masker: Optional[SecretMasker] = None):
        """
        Initialize secure logger.
        
        Args:
            logger: Underlying logger instance
            masker: Secret masker instance (uses default if None)
        """
        self.logger = logger
        self.masker = masker or default_masker
    
    def _safe_format(self, msg: str, *args) -> str:
        """Format message safely with secret masking."""
        try:
            if args:
                # Convert args to strings and mask each one
                safe_args = tuple(self.masker.mask_string(str(arg)) for arg in args)
                formatted_msg = msg % safe_args
            else:
                formatted_msg = msg
            return self.masker.mask_string(formatted_msg)
        except (TypeError, ValueError):
            # Fallback if formatting fails
            return self.masker.mask_string(str(msg))
    
    def debug(self, msg: str, *args, **kwargs):
        """Log debug message with secret masking."""
        safe_msg = self._safe_format(msg, *args)
        self.logger.debug(safe_msg, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        """Log info message with secret masking."""
        safe_msg = self._safe_format(msg, *args)
        self.logger.info(safe_msg, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        """Log warning message with secret masking."""
        safe_msg = self._safe_format(msg, *args)
        self.logger.warning(safe_msg, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        """Log error message with secret masking."""
        safe_msg = self._safe_format(msg, *args)
        self.logger.error(safe_msg, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        """Log critical message with secret masking."""
        safe_msg = self._safe_format(msg, *args)
        self.logger.critical(safe_msg, **kwargs)


def get_secure_logger(name: str) -> SecureLogger:
    """
    Get a secure logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        SecureLogger instance
    """
    return SecureLogger(logging.getLogger(name))