"""
TDD tests for Singapore timezone scheduling utilities.
Tests SGT to UTC conversion, business hours, and cron generation.
"""

import pytest
from datetime import datetime, timezone, timedelta
from gimme_ai.utils.singapore_scheduler import (
    SingaporeScheduler,
    sgt_to_utc_cron,
    parse_sgt_time,
    is_singapore_business_hours,
    generate_wrangler_crons,
    SGT_TIMEZONE
)


class TestSGTTimezoneFunctions:
    """Test basic SGT timezone utility functions."""
    
    def test_sgt_timezone_constant(self):
        """Test SGT timezone is correctly defined as UTC+8."""
        # SGT is UTC+8 with no DST
        assert SGT_TIMEZONE.utcoffset(datetime.now()) == timedelta(hours=8)
    
    def test_parse_sgt_time_valid_formats(self):
        """Test parsing various SGT time formats."""
        # Test standard formats
        assert parse_sgt_time("02:00") == (2, 0)
        assert parse_sgt_time("14:30") == (14, 30)
        assert parse_sgt_time("09:45") == (9, 45)
        
        # Test 12-hour formats
        assert parse_sgt_time("2:00 AM") == (2, 0)
        assert parse_sgt_time("2:00 PM") == (14, 0)
        assert parse_sgt_time("12:30 AM") == (0, 30)
        assert parse_sgt_time("12:30 PM") == (12, 30)
    
    def test_parse_sgt_time_invalid_formats(self):
        """Test parsing invalid time formats raises appropriate errors."""
        with pytest.raises(ValueError, match="Invalid time format"):
            parse_sgt_time("25:00")
        
        with pytest.raises(ValueError, match="Invalid time format"):
            parse_sgt_time("02:60")
        
        with pytest.raises(ValueError, match="Invalid time format"):
            parse_sgt_time("invalid")
    
    def test_sgt_to_utc_cron_basic_conversion(self):
        """Test basic SGT to UTC cron conversion."""
        # 2 AM SGT = 6 PM UTC previous day
        assert sgt_to_utc_cron("02:00") == "0 18 * * *"
        
        # 9 AM SGT = 1 AM UTC same day
        assert sgt_to_utc_cron("09:00") == "0 1 * * *"
        
        # 6 PM SGT = 10 AM UTC same day
        assert sgt_to_utc_cron("18:00") == "0 10 * * *"
        
        # 11 PM SGT = 3 PM UTC same day
        assert sgt_to_utc_cron("23:00") == "0 15 * * *"
    
    def test_sgt_to_utc_cron_with_minutes(self):
        """Test SGT to UTC conversion with minutes."""
        # 2:30 AM SGT = 6:30 PM UTC previous day
        assert sgt_to_utc_cron("02:30") == "30 18 * * *"
        
        # 9:15 AM SGT = 1:15 AM UTC same day
        assert sgt_to_utc_cron("09:15") == "15 1 * * *"
    
    def test_sgt_to_utc_cron_edge_cases(self):
        """Test edge cases for timezone conversion."""
        # Midnight SGT = 4 PM UTC previous day
        assert sgt_to_utc_cron("00:00") == "0 16 * * *"
        
        # 1 AM SGT = 5 PM UTC previous day  
        assert sgt_to_utc_cron("01:00") == "0 17 * * *"
        
        # 8 AM SGT = Midnight UTC same day
        assert sgt_to_utc_cron("08:00") == "0 0 * * *"
    
    def test_is_singapore_business_hours(self):
        """Test Singapore business hours detection."""
        # Create SGT datetime objects
        sgt_9am = datetime.now(SGT_TIMEZONE).replace(hour=9, minute=0, second=0, microsecond=0)
        sgt_12pm = datetime.now(SGT_TIMEZONE).replace(hour=12, minute=0, second=0, microsecond=0)
        sgt_6pm = datetime.now(SGT_TIMEZONE).replace(hour=18, minute=0, second=0, microsecond=0)
        sgt_7pm = datetime.now(SGT_TIMEZONE).replace(hour=19, minute=0, second=0, microsecond=0)
        sgt_2am = datetime.now(SGT_TIMEZONE).replace(hour=2, minute=0, second=0, microsecond=0)
        
        # Business hours (9 AM - 6 PM SGT, Monday-Friday)
        # Note: This test assumes we're testing on a weekday
        assert is_singapore_business_hours(sgt_9am) == True
        assert is_singapore_business_hours(sgt_12pm) == True
        assert is_singapore_business_hours(sgt_6pm) == False  # 6 PM is end of business hours
        assert is_singapore_business_hours(sgt_7pm) == False
        assert is_singapore_business_hours(sgt_2am) == False


class TestSingaporeScheduler:
    """Test the main SingaporeScheduler class."""
    
    def test_scheduler_initialization(self):
        """Test scheduler initializes with correct default values."""
        scheduler = SingaporeScheduler()
        assert scheduler.timezone == SGT_TIMEZONE
        assert scheduler.business_start == 9
        assert scheduler.business_end == 18
    
    def test_scheduler_custom_business_hours(self):
        """Test scheduler with custom business hours."""
        scheduler = SingaporeScheduler(business_start=8, business_end=17)
        assert scheduler.business_start == 8
        assert scheduler.business_end == 17
    
    def test_convert_time_to_utc_cron(self):
        """Test scheduler's main conversion method."""
        scheduler = SingaporeScheduler()
        
        # Test daily schedule
        cron = scheduler.convert_time_to_utc_cron("02:00", "daily")
        assert cron == "0 18 * * *"
        
        # Test weekly schedule (Mondays)
        cron = scheduler.convert_time_to_utc_cron("02:00", "weekly", weekday="monday")
        assert cron == "0 18 * * 1"
        
        # Test monthly schedule (1st of month)
        cron = scheduler.convert_time_to_utc_cron("02:00", "monthly", day_of_month=1)
        assert cron == "0 18 1 * *"
    
    def test_get_next_singapore_time(self):
        """Test getting next occurrence of Singapore time."""
        scheduler = SingaporeScheduler()
        
        # This is a more complex test that depends on current time
        # For now, just test that it returns a datetime with SGT timezone
        next_time = scheduler.get_next_singapore_time("02:00", "daily")
        assert next_time.tzinfo == SGT_TIMEZONE
        assert next_time.hour == 2
        assert next_time.minute == 0
    
    def test_generate_derivativ_schedule(self):
        """Test generating Derivativ's specific schedule."""
        scheduler = SingaporeScheduler()
        
        # Derivativ runs at 2 AM SGT daily
        cron = scheduler.generate_derivativ_schedule()
        assert cron == "0 18 * * *"  # 2 AM SGT = 6 PM UTC previous day
    
    def test_validate_singapore_time(self):
        """Test Singapore time validation."""
        scheduler = SingaporeScheduler()
        
        # Valid times
        assert scheduler.validate_singapore_time("02:00") == True
        assert scheduler.validate_singapore_time("14:30") == True
        
        # Invalid times
        assert scheduler.validate_singapore_time("25:00") == False
        assert scheduler.validate_singapore_time("02:60") == False
        assert scheduler.validate_singapore_time("invalid") == False


class TestWranglerIntegration:
    """Test Wrangler configuration generation."""
    
    def test_generate_wrangler_crons_single_schedule(self):
        """Test generating wrangler.toml cron configuration."""
        schedules = [("derivativ_daily", "0 18 * * *")]
        
        config = generate_wrangler_crons(schedules)
        
        expected = '''[triggers]
crons = [
  "0 18 * * *"  # derivativ_daily
]'''
        assert config.strip() == expected.strip()
    
    def test_generate_wrangler_crons_multiple_schedules(self):
        """Test generating multiple cron schedules."""
        schedules = [
            ("derivativ_daily", "0 18 * * *"),
            ("weekly_summary", "0 19 * * 1"),
            ("monthly_report", "0 20 1 * *")
        ]
        
        config = generate_wrangler_crons(schedules)
        
        expected = '''[triggers]
crons = [
  "0 18 * * *",  # derivativ_daily
  "0 19 * * 1",  # weekly_summary
  "0 20 1 * *"   # monthly_report
]'''
        assert config.strip() == expected.strip()
    
    def test_generate_wrangler_crons_empty_list(self):
        """Test generating config with no schedules."""
        config = generate_wrangler_crons([])
        
        expected = '''[triggers]
crons = []'''
        assert config.strip() == expected.strip()


class TestRealWorldScenarios:
    """Test real-world scheduling scenarios."""
    
    def test_derivativ_daily_2am_sgt(self):
        """Test Derivativ's specific requirement: 2 AM SGT daily."""
        scheduler = SingaporeScheduler()
        
        # Requirement: Generate 50 Cambridge IGCSE questions at 2 AM SGT
        cron = scheduler.convert_time_to_utc_cron("02:00", "daily")
        
        # Should convert to 6 PM UTC previous day
        assert cron == "0 18 * * *"
        
        # Verify this is correct by checking the math:
        # 2 AM SGT = 2 AM UTC+8 = (2-8) AM UTC = -6 AM UTC = 6 PM UTC previous day
    
    def test_business_hours_avoidance(self):
        """Test that 2 AM SGT avoids Singapore business hours."""
        # 2 AM SGT should be well outside business hours (9 AM - 6 PM SGT)
        sgt_2am = datetime.now(SGT_TIMEZONE).replace(hour=2, minute=0)
        assert is_singapore_business_hours(sgt_2am) == False
        
        # This confirms 2 AM is a good time for automated processing
    
    def test_multiple_question_generation_times(self):
        """Test scheduling multiple daily question generation sessions."""
        scheduler = SingaporeScheduler()
        
        # Morning prep: 1 AM SGT
        morning_cron = scheduler.convert_time_to_utc_cron("01:00", "daily")
        assert morning_cron == "0 17 * * *"
        
        # Main generation: 2 AM SGT  
        main_cron = scheduler.convert_time_to_utc_cron("02:00", "daily")
        assert main_cron == "0 18 * * *"
        
        # Backup generation: 3 AM SGT
        backup_cron = scheduler.convert_time_to_utc_cron("03:00", "daily")
        assert backup_cron == "0 19 * * *"
        
        # All should be different times
        assert len({morning_cron, main_cron, backup_cron}) == 3