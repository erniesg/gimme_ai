"""
Singapore timezone scheduling utilities for gimme_ai workflows.
Handles SGT to UTC conversion, business hours detection, and cron generation.
"""

import re
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional, List, Union

# Singapore timezone (UTC+8, no DST)
SGT_TIMEZONE = timezone(timedelta(hours=8))


class SingaporeScheduler:
    """
    Singapore timezone scheduler for converting SGT times to UTC cron expressions.
    
    Handles Derivativ's requirement for daily question generation at 2 AM SGT,
    which converts to 6 PM UTC (previous day) for Cloudflare Workers.
    """
    
    def __init__(self, business_start: int = 9, business_end: int = 18):
        """
        Initialize scheduler with business hours.
        
        Args:
            business_start: Business hours start (24-hour format, default 9 AM)
            business_end: Business hours end (24-hour format, default 6 PM)
        """
        self.timezone = SGT_TIMEZONE
        self.business_start = business_start
        self.business_end = business_end
    
    def convert_time_to_utc_cron(
        self, 
        sgt_time: str, 
        frequency: str = "daily",
        weekday: Optional[str] = None,
        day_of_month: Optional[int] = None
    ) -> str:
        """
        Convert SGT time to UTC cron expression.
        
        Args:
            sgt_time: Time in SGT (e.g., "02:00", "14:30")
            frequency: Schedule frequency ("daily", "weekly", "monthly")
            weekday: Day of week for weekly schedules ("monday", "tuesday", etc.)
            day_of_month: Day of month for monthly schedules (1-31)
            
        Returns:
            UTC cron expression (e.g., "0 18 * * *")
        """
        # Convert SGT time to UTC cron
        base_cron = sgt_to_utc_cron(sgt_time)
        
        if frequency == "daily":
            return base_cron
        elif frequency == "weekly":
            if weekday is None:
                raise ValueError("weekday is required for weekly schedules")
            weekday_num = self._weekday_to_cron_num(weekday)
            parts = base_cron.split()
            parts[4] = str(weekday_num)
            return " ".join(parts)
        elif frequency == "monthly":
            if day_of_month is None:
                raise ValueError("day_of_month is required for monthly schedules")
            parts = base_cron.split()
            parts[2] = str(day_of_month)
            return " ".join(parts)
        else:
            raise ValueError(f"Unsupported frequency: {frequency}")
    
    def get_next_singapore_time(self, sgt_time: str, frequency: str = "daily") -> datetime:
        """
        Get next occurrence of Singapore time.
        
        Args:
            sgt_time: Time in SGT format
            frequency: Schedule frequency
            
        Returns:
            Next datetime in SGT timezone
        """
        hour, minute = parse_sgt_time(sgt_time)
        now = datetime.now(SGT_TIMEZONE)
        
        # Create target time for today
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # If target time has passed today, move to next occurrence
        if target <= now:
            if frequency == "daily":
                target += timedelta(days=1)
            elif frequency == "weekly":
                target += timedelta(days=7)
            elif frequency == "monthly":
                # Simple monthly increment (doesn't handle month-end edge cases)
                if target.month == 12:
                    target = target.replace(year=target.year + 1, month=1)
                else:
                    target = target.replace(month=target.month + 1)
        
        return target
    
    def generate_derivativ_schedule(self) -> str:
        """
        Generate Derivativ's specific schedule: 2 AM SGT daily.
        
        Returns:
            UTC cron expression for 2 AM SGT daily
        """
        return self.convert_time_to_utc_cron("02:00", "daily")
    
    def validate_singapore_time(self, sgt_time: str) -> bool:
        """
        Validate Singapore time format.
        
        Args:
            sgt_time: Time string to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            parse_sgt_time(sgt_time)
            return True
        except ValueError:
            return False
    
    def _weekday_to_cron_num(self, weekday: str) -> int:
        """Convert weekday name to cron number (0=Sunday, 1=Monday, etc.)"""
        weekdays = {
            "sunday": 0, "monday": 1, "tuesday": 2, "wednesday": 3,
            "thursday": 4, "friday": 5, "saturday": 6
        }
        return weekdays.get(weekday.lower(), 1)


def parse_sgt_time(time_str: str) -> Tuple[int, int]:
    """
    Parse SGT time string into hour and minute.
    
    Supports formats:
    - "HH:mm" (24-hour format)
    - "H:mm AM/PM" (12-hour format)
    
    Args:
        time_str: Time string to parse
        
    Returns:
        Tuple of (hour, minute) in 24-hour format
        
    Raises:
        ValueError: If time format is invalid
    """
    time_str = time_str.strip()
    
    # Try 12-hour format first (e.g., "2:00 AM", "2:00 PM")
    am_pm_pattern = r'^(\d{1,2}):(\d{2})\s*(AM|PM)$'
    match = re.match(am_pm_pattern, time_str, re.IGNORECASE)
    if match:
        hour, minute, am_pm = match.groups()
        hour, minute = int(hour), int(minute)
        
        # Validate ranges
        if hour < 1 or hour > 12:
            raise ValueError("Invalid time format: hour must be 1-12 for AM/PM format")
        if minute < 0 or minute > 59:
            raise ValueError("Invalid time format: minute must be 0-59")
        
        # Convert to 24-hour format
        if am_pm.upper() == 'AM':
            if hour == 12:
                hour = 0  # 12 AM = 00:00
        else:  # PM
            if hour != 12:
                hour += 12  # 1 PM = 13:00, but 12 PM = 12:00
        
        return hour, minute
    
    # Try 24-hour format (e.g., "02:00", "14:30")
    hour_minute_pattern = r'^(\d{1,2}):(\d{2})$'
    match = re.match(hour_minute_pattern, time_str)
    if match:
        hour, minute = map(int, match.groups())
        
        # Validate ranges
        if hour < 0 or hour > 23:
            raise ValueError("Invalid time format: hour must be 0-23")
        if minute < 0 or minute > 59:
            raise ValueError("Invalid time format: minute must be 0-59")
        
        return hour, minute
    
    raise ValueError(f"Invalid time format: {time_str}")


def sgt_to_utc_cron(sgt_time: str) -> str:
    """
    Convert Singapore time to UTC cron expression.
    
    SGT is UTC+8, so we subtract 8 hours to get UTC time.
    
    Args:
        sgt_time: Time in SGT (e.g., "02:00", "14:30")
        
    Returns:
        UTC cron expression (e.g., "0 18 * * *")
    """
    hour, minute = parse_sgt_time(sgt_time)
    
    # Convert SGT to UTC by subtracting 8 hours
    utc_hour = hour - 8
    
    # Handle day rollover (negative hours)
    if utc_hour < 0:
        utc_hour += 24
    
    return f"{minute} {utc_hour} * * *"


def is_singapore_business_hours(dt: datetime) -> bool:
    """
    Check if datetime falls within Singapore business hours.
    
    Business hours: 9 AM - 6 PM SGT, Monday-Friday
    
    Args:
        dt: Datetime to check (should be in SGT timezone)
        
    Returns:
        True if within business hours, False otherwise
    """
    # Convert to SGT if needed
    if dt.tzinfo != SGT_TIMEZONE:
        dt = dt.astimezone(SGT_TIMEZONE)
    
    # Check if weekday (Monday=0, Sunday=6)
    if dt.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    
    # Check if within business hours (9 AM - 6 PM)
    return 9 <= dt.hour < 18


def generate_wrangler_crons(schedules: List[Tuple[str, str]]) -> str:
    """
    Generate wrangler.toml cron configuration from schedules.
    
    Args:
        schedules: List of (name, cron_expression) tuples
        
    Returns:
        Wrangler.toml cron configuration string
    """
    if not schedules:
        return "[triggers]\ncrons = []"
    
    cron_lines = []
    for i, (name, cron) in enumerate(schedules):
        if len(schedules) == 1:
            # Single item - 2 spaces
            cron_lines.append(f'  "{cron}"  # {name}')
        elif i == len(schedules) - 1:
            # Last item in multiple - 3 spaces, no comma
            cron_lines.append(f'  "{cron}"   # {name}')
        else:
            # Not last item - 2 spaces with comma
            cron_lines.append(f'  "{cron}",  # {name}')
    
    return "[triggers]\ncrons = [\n" + "\n".join(cron_lines) + "\n]"