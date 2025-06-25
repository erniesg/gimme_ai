"""Tests for time format validation in configuration."""

import pytest
from pydantic import ValidationError

from gimme_ai.config.workflow import StepConfig, RetryConfig


class TestTimeFormatValidation:
    """Test time format validation for configuration fields."""
    
    def test_poll_interval_valid_formats(self):
        """Test valid poll interval formats."""
        valid_intervals = ["1s", "30s", "5m", "2h", "10s", "60m"]
        
        for interval in valid_intervals:
            step = StepConfig(
                name="test_step",
                endpoint="/api/test",
                poll_interval=interval
            )
            assert step.poll_interval == interval
    
    def test_poll_interval_invalid_formats(self):
        """Test invalid poll interval formats raise validation errors."""
        invalid_intervals = [
            "1",          # No unit
            "30ms",       # Wrong unit
            "5min",       # Wrong unit  
            "2hours",     # Wrong unit
            "abc",        # Not a number
            "1.5s",       # Float not allowed
            "-5s",        # Negative not allowed
            "",           # Empty string
        ]
        
        for interval in invalid_intervals:
            with pytest.raises(ValidationError, match="Poll interval must be in format"):
                StepConfig(
                    name="test_step", 
                    endpoint="/api/test",
                    poll_interval=interval
                )
    
    def test_poll_timeout_valid_formats(self):
        """Test valid poll timeout formats."""
        valid_timeouts = ["30s", "5m", "1h", "120s", "45m"]
        
        for timeout in valid_timeouts:
            step = StepConfig(
                name="test_step",
                endpoint="/api/test", 
                poll_timeout=timeout
            )
            assert step.poll_timeout == timeout
    
    def test_poll_timeout_invalid_formats(self):
        """Test invalid poll timeout formats raise validation errors."""
        invalid_timeouts = [
            "1",          # No unit
            "30ms",       # Wrong unit
            "5min",       # Wrong unit
            "2hours",     # Wrong unit
            "xyz",        # Not a number
            "2.5m",       # Float not allowed
            "-10m",       # Negative not allowed
        ]
        
        for timeout in invalid_timeouts:
            with pytest.raises(ValidationError, match="Poll timeout must be in format"):
                StepConfig(
                    name="test_step",
                    endpoint="/api/test",
                    poll_timeout=timeout
                )
    
    def test_step_timeout_valid_formats(self):
        """Test valid step timeout formats."""
        valid_timeouts = ["10s", "2m", "1h", "45s", "30m"]
        
        for timeout in valid_timeouts:
            step = StepConfig(
                name="test_step",
                endpoint="/api/test",
                timeout=timeout
            )
            assert step.timeout == timeout
    
    def test_step_timeout_none_allowed(self):
        """Test that step timeout can be None."""
        step = StepConfig(
            name="test_step",
            endpoint="/api/test",
            timeout=None
        )
        assert step.timeout is None
    
    def test_step_timeout_invalid_formats(self):
        """Test invalid step timeout formats raise validation errors."""
        invalid_timeouts = [
            "1",          # No unit
            "30ms",       # Wrong unit
            "5min",       # Wrong unit
            "invalid",    # Not a number
            "1.5h",       # Float not allowed
            "-5m",        # Negative not allowed
        ]
        
        for timeout in invalid_timeouts:
            with pytest.raises(ValidationError, match="Timeout must be in format"):
                StepConfig(
                    name="test_step",
                    endpoint="/api/test", 
                    timeout=timeout
                )
    
    def test_retry_delay_valid_formats(self):
        """Test valid retry delay formats."""
        valid_delays = ["1s", "10s", "2m", "1h", "30s"]
        
        for delay in valid_delays:
            retry = RetryConfig(limit=3, delay=delay)
            assert retry.delay == delay
    
    def test_retry_delay_invalid_formats(self):
        """Test invalid retry delay formats raise validation errors."""
        invalid_delays = [
            "1",          # No unit
            "30ms",       # Wrong unit
            "5min",       # Wrong unit
            "invalid",    # Not a number
            "2.5s",       # Float not allowed
            "-1s",        # Negative not allowed
        ]
        
        for delay in invalid_delays:
            with pytest.raises(ValidationError, match="Duration must be in format"):
                RetryConfig(limit=3, delay=delay)
    
    def test_comprehensive_step_with_all_time_fields(self):
        """Test step configuration with all time-related fields."""
        step = StepConfig(
            name="comprehensive_step",
            endpoint="/api/test",
            poll_interval="15s",
            poll_timeout="5m", 
            timeout="2m",
            retry=RetryConfig(limit=3, delay="10s")
        )
        
        assert step.poll_interval == "15s"
        assert step.poll_timeout == "5m"
        assert step.timeout == "2m"
        assert step.retry.delay == "10s"
    
    def test_edge_case_time_values(self):
        """Test edge case time values."""
        # Very small values
        step = StepConfig(
            name="edge_case",
            endpoint="/api/test",
            poll_interval="1s",
            poll_timeout="1s",
            timeout="1s"
        )
        
        assert step.poll_interval == "1s"
        assert step.poll_timeout == "1s" 
        assert step.timeout == "1s"
        
        # Large values
        step = StepConfig(
            name="large_timeouts",
            endpoint="/api/test",
            poll_interval="999s",
            poll_timeout="999m", 
            timeout="999h"
        )
        
        assert step.poll_interval == "999s"
        assert step.poll_timeout == "999m"
        assert step.timeout == "999h"