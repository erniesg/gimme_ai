"""Singapore Timezone Cron Scheduling Support for gimme_ai workflows.

This module provides comprehensive timezone-aware cron scheduling with focus on
Singapore Time (SGT, UTC+8) conversion for Cloudflare Workers deployment.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional, Union

import pytz


class TimeZone(Enum):
    """Supported timezone enum."""
    UTC = "UTC"
    GMT = "GMT"
    SGT = "Asia/Singapore"
    HKT = "Asia/Hong_Kong"
    JST = "Asia/Tokyo"
    KST = "Asia/Seoul"
    EST = "America/New_York"
    PST = "America/Los_Angeles"
    CST = "America/Chicago"
    MST = "America/Denver"
    GMT_LONDON = "Europe/London"
    CET = "Europe/Berlin"
    IST = "Asia/Kolkata"
    AEST = "Australia/Sydney"


@dataclass
class CronSchedule:
    """Parsed cron schedule with timezone information."""
    minute: str
    hour: str
    day: str
    month: str
    weekday: str
    timezone: str = "UTC"
    original_schedule: str = ""
    converted_utc_schedule: str = ""
    description: str = ""

    def to_cron_string(self, use_utc: bool = False) -> str:
        """Convert to standard cron string format."""
        if use_utc and self.converted_utc_schedule:
            return self.converted_utc_schedule
        return f"{self.minute} {self.hour} {self.day} {self.month} {self.weekday}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "minute": self.minute,
            "hour": self.hour,
            "day": self.day,
            "month": self.month,
            "weekday": self.weekday,
            "timezone": self.timezone,
            "original_schedule": self.original_schedule,
            "converted_utc_schedule": self.converted_utc_schedule,
            "description": self.description
        }


@dataclass
class ScheduleConversionResult:
    """Result of timezone conversion with metadata."""
    original_schedule: CronSchedule
    converted_schedule: CronSchedule
    timezone_offset_hours: int
    conversion_notes: list[str]
    next_execution_local: Optional[datetime] = None
    next_execution_utc: Optional[datetime] = None


class SingaporeTimezoneScheduler:
    """Singapore timezone-aware cron scheduler with UTC conversion support."""

    def __init__(self):
        self.timezone_offsets = {
            TimeZone.UTC.value: 0,
            TimeZone.GMT.value: 0,
            TimeZone.SGT.value: 8,   # UTC+8
            TimeZone.HKT.value: 8,   # UTC+8
            TimeZone.JST.value: 9,   # UTC+9
            TimeZone.KST.value: 9,   # UTC+9
            TimeZone.EST.value: -5,  # UTC-5 (standard time)
            TimeZone.PST.value: -8,  # UTC-8 (standard time)
            TimeZone.CST.value: -6,  # UTC-6 (standard time)
            TimeZone.MST.value: -7,  # UTC-7 (standard time)
            TimeZone.GMT_LONDON.value: 0,  # GMT (ignoring DST for simplicity)
            TimeZone.CET.value: 1,   # UTC+1 (ignoring DST for simplicity)
            TimeZone.IST.value: 5.5, # UTC+5:30
            TimeZone.AEST.value: 10  # UTC+10 (ignoring DST for simplicity)
        }

        self.common_singapore_schedules = {
            "daily_2am": "0 2 * * *",      # 2 AM daily (common for batch jobs)
            "daily_6am": "0 6 * * *",      # 6 AM daily (morning reports)
            "daily_9am": "0 9 * * *",      # 9 AM daily (business hours start)
            "daily_6pm": "0 18 * * *",     # 6 PM daily (end of business)
            "weekdays_2am": "0 2 * * 1-5", # 2 AM weekdays only
            "weekdays_9am": "0 9 * * 1-5", # 9 AM weekdays only
            "weekend_10am": "0 10 * * 0,6", # 10 AM weekends only
            "hourly": "0 * * * *",         # Every hour
            "every_15min": "*/15 * * * *", # Every 15 minutes
            "monthly_1st_2am": "0 2 1 * *" # 1st of month at 2 AM
        }

    def parse_cron_schedule(
        self,
        cron_string: str,
        timezone: str = "UTC",
        description: str = ""
    ) -> CronSchedule:
        """Parse cron string into structured format with timezone."""

        if not self._validate_cron_format(cron_string):
            raise ValueError(f"Invalid cron format: {cron_string}")

        parts = cron_string.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Cron string must have exactly 5 fields: {cron_string}")

        minute, hour, day, month, weekday = parts

        return CronSchedule(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            weekday=weekday,
            timezone=timezone,
            original_schedule=cron_string,
            description=description
        )

    def convert_to_utc(
        self,
        schedule: Union[str, CronSchedule],
        source_timezone: str = "Asia/Singapore"
    ) -> ScheduleConversionResult:
        """Convert timezone-specific cron schedule to UTC equivalent."""

        # Parse input if it's a string
        if isinstance(schedule, str):
            schedule = self.parse_cron_schedule(schedule, source_timezone)

        # Get timezone offset
        if source_timezone not in self.timezone_offsets:
            raise ValueError(f"Unsupported timezone: {source_timezone}")

        offset_hours = self.timezone_offsets[source_timezone]
        conversion_notes = []

        # Convert hour field
        converted_hour, day_adjustment = self._convert_hour_field(
            schedule.hour, offset_hours, conversion_notes
        )

        # Convert day field if needed
        converted_day = self._convert_day_field(
            schedule.day, day_adjustment, conversion_notes
        )

        # Convert weekday field if needed
        converted_weekday = self._convert_weekday_field(
            schedule.weekday, day_adjustment, conversion_notes
        )

        # Create converted schedule
        converted_schedule = CronSchedule(
            minute=schedule.minute,
            hour=converted_hour,
            day=converted_day,
            month=schedule.month,
            weekday=converted_weekday,
            timezone="UTC",
            original_schedule=schedule.original_schedule,
            converted_utc_schedule=f"{schedule.minute} {converted_hour} {converted_day} {schedule.month} {converted_weekday}",
            description=f"UTC conversion of {schedule.description or 'schedule'}"
        )

        # Calculate next execution times
        next_local, next_utc = self._calculate_next_execution(schedule, converted_schedule)

        return ScheduleConversionResult(
            original_schedule=schedule,
            converted_schedule=converted_schedule,
            timezone_offset_hours=int(offset_hours),
            conversion_notes=conversion_notes,
            next_execution_local=next_local,
            next_execution_utc=next_utc
        )

    def get_singapore_schedule(self, schedule_name: str) -> CronSchedule:
        """Get predefined Singapore timezone schedule by name."""

        if schedule_name not in self.common_singapore_schedules:
            available = ", ".join(self.common_singapore_schedules.keys())
            raise ValueError(f"Unknown schedule '{schedule_name}'. Available: {available}")

        cron_string = self.common_singapore_schedules[schedule_name]
        description = self._get_schedule_description(schedule_name)

        return self.parse_cron_schedule(cron_string, TimeZone.SGT.value, description)

    def convert_singapore_to_utc(self, schedule_name_or_cron: str) -> ScheduleConversionResult:
        """Convert Singapore timezone schedule to UTC for Cloudflare Workers."""

        # Check if it's a predefined schedule name
        if schedule_name_or_cron in self.common_singapore_schedules:
            schedule = self.get_singapore_schedule(schedule_name_or_cron)
        else:
            # Treat as cron string
            schedule = self.parse_cron_schedule(schedule_name_or_cron, TimeZone.SGT.value)

        return self.convert_to_utc(schedule, TimeZone.SGT.value)

    def generate_cloudflare_wrangler_config(
        self,
        schedules: list[Union[str, CronSchedule]],
        source_timezone: str = "Asia/Singapore"
    ) -> dict[str, Any]:
        """Generate Cloudflare Workers wrangler.toml cron configuration."""

        cron_entries = []
        conversion_comments = []

        for schedule in schedules:
            # Handle predefined schedule names
            if isinstance(schedule, str) and schedule in self.common_singapore_schedules:
                result = self.convert_singapore_to_utc(schedule)
            else:
                result = self.convert_to_utc(schedule, source_timezone)

            cron_entries.append(result.converted_schedule.to_cron_string(use_utc=True))

            # Add comments for clarity
            original_desc = result.original_schedule.description or "schedule"
            conversion_comments.append(
                f"# {original_desc} ({source_timezone}) -> UTC"
            )

        return {
            "triggers": {
                "crons": cron_entries
            },
            "conversion_info": {
                "source_timezone": source_timezone,
                "target_timezone": "UTC",
                "comments": conversion_comments,
                "generated_at": datetime.utcnow().isoformat()
            }
        }

    def _validate_cron_format(self, cron_string: str) -> bool:
        """Validate basic cron format."""
        if not isinstance(cron_string, str):
            return False

        parts = cron_string.strip().split()
        if len(parts) != 5:
            return False

        # Basic validation for each field
        field_patterns = [
            r'^(\*|(\d+|\d+-\d+)(,(\d+|\d+-\d+))*|\*/\d+)$',  # minute (0-59)
            r'^(\*|(\d+|\d+-\d+)(,(\d+|\d+-\d+))*|\*/\d+)$',  # hour (0-23)
            r'^(\*|(\d+|\d+-\d+)(,(\d+|\d+-\d+))*|\*/\d+)$',  # day (1-31)
            r'^(\*|(\d+|\d+-\d+)(,(\d+|\d+-\d+))*|\*/\d+)$',  # month (1-12)
            r'^(\*|(\d+|\d+-\d+)(,(\d+|\d+-\d+))*|\*/\d+)$'   # weekday (0-7)
        ]

        for part, pattern in zip(parts, field_patterns):
            if not re.match(pattern, part):
                return False

        return True

    def _convert_hour_field(
        self,
        hour_field: str,
        offset_hours: float,
        notes: list[str]
    ) -> tuple[str, int]:
        """Convert hour field accounting for timezone offset."""

        offset_int = int(offset_hours)
        day_adjustment = 0

        # Handle wildcard
        if hour_field == "*":
            notes.append("Hour field '*' remains unchanged")
            return hour_field, day_adjustment

        # Handle step values (e.g., */6)
        if hour_field.startswith("*/"):
            notes.append(f"Step value '{hour_field}' remains unchanged")
            return hour_field, day_adjustment

        # Handle single hour or comma-separated hours
        if "," in hour_field:
            hours = hour_field.split(",")
            converted_hours = []

            for hour in hours:
                if "-" in hour:
                    # Handle range (e.g., 9-17)
                    start, end = hour.split("-")
                    start_conv = (int(start) - offset_int) % 24
                    end_conv = (int(end) - offset_int) % 24

                    if start_conv > end_conv:
                        # Range crosses midnight
                        converted_hours.append(f"{start_conv}-23")
                        converted_hours.append(f"0-{end_conv}")
                        notes.append(f"Range {hour} crosses midnight after conversion")
                    else:
                        converted_hours.append(f"{start_conv}-{end_conv}")
                else:
                    # Single hour
                    hour_int = int(hour)
                    converted_hour = (hour_int - offset_int) % 24
                    converted_hours.append(str(converted_hour))

                    # Check for day boundary crossing
                    if hour_int - offset_int < 0:
                        day_adjustment = -1
                        notes.append(f"Hour {hour} crosses to previous day")
                    elif hour_int - offset_int >= 24:
                        day_adjustment = 1
                        notes.append(f"Hour {hour} crosses to next day")

            return ",".join(converted_hours), day_adjustment

        elif "-" in hour_field:
            # Handle range
            start, end = hour_field.split("-")
            start_conv = (int(start) - offset_int) % 24
            end_conv = (int(end) - offset_int) % 24

            if start_conv > end_conv:
                # Range crosses midnight
                notes.append(f"Range {hour_field} crosses midnight after conversion")
                return f"{start_conv}-23,0-{end_conv}", day_adjustment
            else:
                return f"{start_conv}-{end_conv}", day_adjustment

        else:
            # Single hour
            hour_int = int(hour_field)
            converted_hour = (hour_int - offset_int) % 24

            # Check for day boundary crossing
            if hour_int - offset_int < 0:
                day_adjustment = -1
                notes.append(f"Hour {hour_field} ({hour_int}:00) moves to previous day")
            elif hour_int - offset_int >= 24:
                day_adjustment = 1
                notes.append(f"Hour {hour_field} ({hour_int}:00) moves to next day")

            return str(converted_hour), day_adjustment

    def _convert_day_field(self, day_field: str, day_adjustment: int, notes: list[str]) -> str:
        """Convert day field accounting for day boundary crossings."""

        if day_adjustment == 0 or day_field == "*":
            return day_field

        # For day adjustments with specific days, it becomes complex
        # For simplicity, we'll warn and keep the original
        if day_adjustment != 0 and day_field != "*":
            notes.append(f"Day field '{day_field}' may need manual adjustment due to timezone conversion")

        return day_field

    def _convert_weekday_field(self, weekday_field: str, day_adjustment: int, notes: list[str]) -> str:
        """Convert weekday field accounting for day boundary crossings."""

        if day_adjustment == 0 or weekday_field == "*":
            return weekday_field

        # Handle weekday adjustment
        if day_adjustment == -1:
            # Move to previous day
            if "," in weekday_field:
                # Complex case - warn user
                notes.append(f"Weekday field '{weekday_field}' may need manual adjustment (moved to previous day)")
                return weekday_field
            elif "-" in weekday_field:
                # Range case - warn user
                notes.append(f"Weekday range '{weekday_field}' may need manual adjustment (moved to previous day)")
                return weekday_field
            else:
                # Single weekday
                try:
                    weekday = int(weekday_field)
                    adjusted_weekday = (weekday - 1) % 7
                    notes.append(f"Weekday {weekday_field} adjusted to {adjusted_weekday} (previous day)")
                    return str(adjusted_weekday)
                except ValueError:
                    notes.append(f"Weekday field '{weekday_field}' could not be adjusted automatically")
                    return weekday_field

        elif day_adjustment == 1:
            # Move to next day
            if "," in weekday_field:
                notes.append(f"Weekday field '{weekday_field}' may need manual adjustment (moved to next day)")
                return weekday_field
            elif "-" in weekday_field:
                notes.append(f"Weekday range '{weekday_field}' may need manual adjustment (moved to next day)")
                return weekday_field
            else:
                try:
                    weekday = int(weekday_field)
                    adjusted_weekday = (weekday + 1) % 7
                    notes.append(f"Weekday {weekday_field} adjusted to {adjusted_weekday} (next day)")
                    return str(adjusted_weekday)
                except ValueError:
                    notes.append(f"Weekday field '{weekday_field}' could not be adjusted automatically")
                    return weekday_field

        return weekday_field

    def _calculate_next_execution(
        self,
        local_schedule: CronSchedule,
        utc_schedule: CronSchedule
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """Calculate next execution times for both local and UTC schedules."""

        # For simplicity, we'll calculate for a basic case
        # In production, would use a proper cron parsing library like croniter

        try:
            # Try to parse simple hour-based schedules
            if (local_schedule.minute.isdigit() and
                local_schedule.hour.isdigit() and
                local_schedule.day == "*" and
                local_schedule.month == "*" and
                local_schedule.weekday == "*"):

                now_local = datetime.now(pytz.timezone(local_schedule.timezone))
                now_utc = datetime.utcnow()

                # Calculate next local execution (daily)
                next_local = now_local.replace(
                    hour=int(local_schedule.hour),
                    minute=int(local_schedule.minute),
                    second=0,
                    microsecond=0
                )

                # If time has passed today, move to tomorrow
                if next_local <= now_local:
                    next_local += timedelta(days=1)

                # Calculate next UTC execution
                next_utc = now_utc.replace(
                    hour=int(utc_schedule.hour),
                    minute=int(utc_schedule.minute),
                    second=0,
                    microsecond=0
                )

                if next_utc <= now_utc:
                    next_utc += timedelta(days=1)

                return next_local, next_utc

        except Exception:
            pass  # Fall back to None values

        return None, None

    def _get_schedule_description(self, schedule_name: str) -> str:
        """Get human-readable description for predefined schedules."""
        descriptions = {
            "daily_2am": "Daily at 2:00 AM Singapore Time (ideal for batch processing)",
            "daily_6am": "Daily at 6:00 AM Singapore Time (morning reports)",
            "daily_9am": "Daily at 9:00 AM Singapore Time (business hours start)",
            "daily_6pm": "Daily at 6:00 PM Singapore Time (end of business day)",
            "weekdays_2am": "Weekdays at 2:00 AM Singapore Time (Monday-Friday)",
            "weekdays_9am": "Weekdays at 9:00 AM Singapore Time (Monday-Friday)",
            "weekend_10am": "Weekends at 10:00 AM Singapore Time (Saturday-Sunday)",
            "hourly": "Every hour",
            "every_15min": "Every 15 minutes",
            "monthly_1st_2am": "First day of month at 2:00 AM Singapore Time"
        }

        return descriptions.get(schedule_name, f"Custom schedule: {schedule_name}")


class DerivativScheduleTemplates:
    """Predefined schedule templates for Derivativ workflows."""

    @staticmethod
    def get_daily_question_generation_schedule() -> dict[str, Any]:
        """Get schedule configuration for daily question generation at 2 AM SGT."""
        scheduler = SingaporeTimezoneScheduler()

        # Convert Singapore 2 AM to UTC (6 PM previous day)
        result = scheduler.convert_singapore_to_utc("daily_2am")

        return {
            "schedule": result.converted_schedule.to_cron_string(use_utc=True),
            "timezone": "UTC",
            "description": "Daily question generation at 2:00 AM Singapore Time",
            "singapore_time": "2:00 AM SGT (daily)",
            "utc_time": f"{result.converted_schedule.hour}:00 UTC (daily)",
            "conversion_notes": result.conversion_notes,
            "next_execution_sgt": result.next_execution_local.isoformat() if result.next_execution_local else None,
            "next_execution_utc": result.next_execution_utc.isoformat() if result.next_execution_utc else None
        }

    @staticmethod
    def get_business_hours_schedules() -> dict[str, Any]:
        """Get multiple business hour schedules for different operations."""
        scheduler = SingaporeTimezoneScheduler()

        schedules = {
            "morning_reports": scheduler.convert_singapore_to_utc("daily_6am"),
            "business_start": scheduler.convert_singapore_to_utc("daily_9am"),
            "end_of_day": scheduler.convert_singapore_to_utc("daily_6pm"),
            "weekday_batch": scheduler.convert_singapore_to_utc("weekdays_2am")
        }

        result = {}
        for name, conversion_result in schedules.items():
            result[name] = {
                "schedule": conversion_result.converted_schedule.to_cron_string(use_utc=True),
                "description": conversion_result.original_schedule.description,
                "singapore_time": f"{conversion_result.original_schedule.hour}:00 SGT",
                "utc_time": f"{conversion_result.converted_schedule.hour}:00 UTC",
                "conversion_notes": conversion_result.conversion_notes
            }

        return result

    @staticmethod
    def generate_wrangler_config_for_derivativ() -> str:
        """Generate complete wrangler.toml configuration for Derivativ workflows."""
        scheduler = SingaporeTimezoneScheduler()

        # Define Derivativ schedules
        schedules = [
            ("daily_2am", "Daily question generation"),
            ("weekdays_9am", "Business day content review"),
            ("daily_6pm", "End of day processing")
        ]

        cron_configs = []
        for schedule_name, description in schedules:
            result = scheduler.convert_singapore_to_utc(schedule_name)
            utc_cron = result.converted_schedule.to_cron_string(use_utc=True)
            cron_configs.append(f'  "{utc_cron}"  # {description} (SGT -> UTC)')

        wrangler_config = f"""# Derivativ AI Workflow Schedules
# Generated on {datetime.utcnow().isoformat()}Z
# All times converted from Singapore Time (UTC+8) to UTC for Cloudflare Workers

[triggers]
crons = [
{chr(10).join(cron_configs)}
]

# Deployment configuration
name = "derivativ-workflows"
main = "src/worker.js"
compatibility_date = "2024-01-01"

# Environment variables
[vars]
ENVIRONMENT = "production"
TIMEZONE = "Asia/Singapore"

# Bindings for workflow data
[[kv_namespaces]]
binding = "WORKFLOW_STATE"
id = "your-kv-namespace-id"

[[workflows]]
binding = "DERIVATIV_WORKFLOW"
class_name = "DerivativWorkflow"
"""

        return wrangler_config


if __name__ == "__main__":
    # Test Singapore timezone scheduling
    print("Testing Singapore Timezone Scheduler...")

    scheduler = SingaporeTimezoneScheduler()

    # Test 1: Convert daily 2 AM SGT to UTC
    try:
        result = scheduler.convert_singapore_to_utc("daily_2am")
        print("✅ Daily 2 AM SGT conversion:")
        print(f"   Original: {result.original_schedule.to_cron_string()} (SGT)")
        print(f"   UTC: {result.converted_schedule.to_cron_string(use_utc=True)} (UTC)")
        print(f"   Notes: {', '.join(result.conversion_notes)}")
    except Exception as e:
        print(f"❌ Daily 2 AM SGT conversion failed: {e}")

    # Test 2: Custom cron conversion
    try:
        custom_schedule = "0 14 * * 1-5"  # 2 PM weekdays SGT
        result = scheduler.convert_to_utc(custom_schedule, "Asia/Singapore")
        print("✅ Custom schedule conversion:")
        print(f"   Original: {custom_schedule} (SGT)")
        print(f"   UTC: {result.converted_schedule.to_cron_string(use_utc=True)} (UTC)")
    except Exception as e:
        print(f"❌ Custom schedule conversion failed: {e}")

    # Test 3: Generate Cloudflare config
    try:
        schedules = ["daily_2am", "weekdays_9am"]
        config = scheduler.generate_cloudflare_wrangler_config(schedules)
        print("✅ Cloudflare config generation:")
        print(f"   Cron entries: {len(config['triggers']['crons'])}")
        print(f"   UTC schedules: {config['triggers']['crons']}")
    except Exception as e:
        print(f"❌ Cloudflare config generation failed: {e}")

    # Test 4: Derivativ templates
    try:
        derivativ_schedule = DerivativScheduleTemplates.get_daily_question_generation_schedule()
        print("✅ Derivativ daily schedule:")
        print(f"   SGT: {derivativ_schedule['singapore_time']}")
        print(f"   UTC: {derivativ_schedule['utc_time']}")
        print(f"   Cron: {derivativ_schedule['schedule']}")
    except Exception as e:
        print(f"❌ Derivativ schedule generation failed: {e}")

    # Test 5: Generate wrangler.toml
    try:
        wrangler_config = DerivativScheduleTemplates.generate_wrangler_config_for_derivativ()
        print(f"✅ Wrangler config generated ({len(wrangler_config)} characters)")
        print("   Sample lines:")
        for line in wrangler_config.split('\n')[:10]:
            if line.strip():
                print(f"   {line}")
    except Exception as e:
        print(f"❌ Wrangler config generation failed: {e}")

    print("Singapore timezone scheduler testing completed.")
