"""
Timestamp Utility Module

Provides timezone-aware datetime parsing and Unix timestamp conversion.
This standalone utility helps convert human-readable datetime strings into precise
Unix epoch timestamps (milliseconds) for use with Instana APIs.
"""

import logging
from datetime import datetime
from typing import Any, Dict
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Common timezone mappings
TIMEZONE_ALIASES = {
    "IST": "Asia/Kolkata",
    "ET": "America/New_York",      # Eastern Time (DST-aware)
    "PT": "America/Los_Angeles",   # Pacific Time (DST-aware)
    "CT": "America/Chicago",       # Central Time (DST-aware)
    "MT": "America/Denver",        # Mountain Time (DST-aware)
    "GMT": "GMT",
    "UTC": "UTC",
    "CET": "Europe/Paris",
    "JST": "Asia/Tokyo",
    "AEST": "Australia/Sydney",
    # Add fixed offset support if needed
    "EST5": "Etc/GMT+5",          # Fixed EST (no DST)
    "PST8": "Etc/GMT+8",          # Fixed PST (no DST)
}


def parse_timezone(tz_str: str) -> ZoneInfo:
    """
    Parse timezone string to ZoneInfo object.

    Args:
        tz_str: Timezone string (e.g., "IST", "UTC", "America/New_York")

    Returns:
        ZoneInfo object for the timezone
    """
    # Check if it's an alias
    if tz_str.upper() in TIMEZONE_ALIASES:
        tz_str = TIMEZONE_ALIASES[tz_str.upper()]

    try:
        return ZoneInfo(tz_str)
    except Exception as e:
        logger.warning(f"Failed to parse timezone '{tz_str}': {e}. Defaulting to UTC.")
        return ZoneInfo("UTC")


def parse_datetime_string(datetime_str: str, timezone: str = "UTC") -> datetime:
    """
    Parse various datetime string formats and return timezone-aware datetime.

    CRITICAL: The input datetime string is interpreted as being IN the specified timezone.
    For example, "12 March 2026, 1:47 AM" with timezone="IST" means 1:47 AM India time,
    which will be correctly converted to the equivalent UTC timestamp.

    Supported formats:
    - "10 March 2026, 2:00 PM"
    - "2026-03-10 14:00:00"
    - "2026-03-10T14:00:00"
    - "10/03/2026 14:00"
    - "March 10, 2026 2 PM"

    Args:
        datetime_str: Human-readable datetime string (interpreted as being in the specified timezone)
        timezone: Timezone string (default: UTC)

    Returns:
        Timezone-aware datetime object
    """
    # Check if datetime string contains a timezone abbreviation at the end
    # If so, extract it and use it instead of the provided timezone parameter
    datetime_str_clean = datetime_str.strip()
    detected_tz = None

    # Check for timezone abbreviations at the end of the string
    for tz_abbr in TIMEZONE_ALIASES:
        if datetime_str_clean.upper().endswith(f" {tz_abbr.upper()}"):
            detected_tz = tz_abbr
            # Remove the timezone from the string (case-insensitive removal)
            datetime_str_clean = datetime_str_clean[:-len(tz_abbr)-1].strip()
            logger.info(f"Detected timezone '{detected_tz}' in datetime string, using it instead of '{timezone}'")
            break

    # Use detected timezone if found, otherwise use provided timezone
    tz_to_use = detected_tz if detected_tz else timezone
    tz = parse_timezone(tz_to_use)

    # List of datetime formats to try
    formats = [
        "%d %B %Y, %I:%M %p",      # 10 March 2026, 2:00 PM
        "%d %B %Y, %I %p",          # 10 March 2026, 2 PM
        "%B %d, %Y %I:%M %p",       # March 10, 2026 2:00 PM
        "%B %d, %Y %I %p",          # March 10, 2026 2 PM
        "%Y-%m-%d %H:%M:%S",        # 2026-03-10 14:00:00
        "%Y-%m-%dT%H:%M:%S",        # 2026-03-10T14:00:00
        "%Y-%m-%d %H:%M",           # 2026-03-10 14:00
        "%d/%m/%Y %H:%M",           # 10/03/2026 14:00
        "%m/%d/%Y %H:%M",           # 03/10/2026 14:00
        "%d-%m-%Y %H:%M",           # 10-03-2026 14:00
        "%Y/%m/%d %H:%M",           # 2026/03/10 14:00
    ]

    # Try each format
    for fmt in formats:
        try:
            # Parse as naive datetime first
            dt_naive = datetime.strptime(datetime_str_clean, fmt)

            # Create timezone-aware datetime using constructor to handle DST correctly
            dt_aware = datetime(
                dt_naive.year, dt_naive.month, dt_naive.day,
                dt_naive.hour, dt_naive.minute, dt_naive.second,
                tzinfo=tz
            )

            return dt_aware
        except ValueError:
            continue

    # If no format matched, raise error
    raise ValueError(
        f"Unable to parse datetime string: '{datetime_str}'. "
        f"Supported formats include: '10 March 2026, 2:00 PM', '2026-03-10 14:00:00', etc."
    )


def convert_to_timestamp(
    datetime_str: str,
    timezone: str = "UTC",
    output_unit: str = "milliseconds"
) -> Dict[str, Any]:
    """
    Convert human-readable datetime string to Unix timestamp.

    This function provides accurate, timezone-aware timestamp conversion for use with
    Instana APIs. It eliminates the ambiguity of LLM-generated timestamps by
    performing deterministic local conversion.

    Args:
        datetime_str: Human-readable datetime string
            Examples:
            - "10 March 2026, 2:00 PM"
            - "2026-03-10 14:00:00"
            - "March 10, 2026 2 PM"
            - "2026-03-10T14:00:00"

        timezone: Timezone for the datetime (default: "UTC")
            Supports:
            - IANA timezone names: "Asia/Kolkata", "America/New_York", "Europe/London"
            - Common aliases: "IST", "ET", "PT", "CT", "UTC", "GMT"

        output_unit: Output unit for timestamp (default: "milliseconds")
            Options: "milliseconds", "seconds"

    Returns:
        Dictionary containing:
        - timestamp: Unix timestamp in specified unit
        - datetime_str: Original input string
        - parsed_datetime: ISO format of parsed datetime
        - timezone: Timezone used
        - unit: Output unit used

    Examples:
        # Convert IST datetime to milliseconds
        convert_to_timestamp("10 March 2026, 2:00 PM", "IST")

        # Convert UTC datetime to seconds
        convert_to_timestamp("2026-03-10 14:00:00", "UTC", "seconds")
    """
    # Validate inputs
    if not datetime_str or not datetime_str.strip():
        return {
            "error": "datetime_str cannot be empty or whitespace-only",
            "datetime_str": datetime_str,
            "timezone": timezone
        }

    if not timezone or not timezone.strip():
        logger.warning("Empty timezone provided, defaulting to UTC")
        timezone = "UTC"

    # Validate output_unit early
    if output_unit not in ("milliseconds", "seconds"):
        return {
            "error": f"Invalid output_unit: '{output_unit}'. Must be 'milliseconds' or 'seconds'."
        }

    try:
        logger.debug(f"Converting datetime: '{datetime_str}' in timezone: '{timezone}'")

        # Parse the datetime string
        dt = parse_datetime_string(datetime_str, timezone)

        # Convert to Unix timestamp
        timestamp_seconds = dt.timestamp()

        # Convert to requested unit
        if output_unit == "milliseconds":
            timestamp = int(timestamp_seconds * 1000)
        else:  # output_unit == "seconds" (already validated)
            timestamp = int(timestamp_seconds)

        result = {
            "success": True,
            "timestamp": timestamp,
            "datetime_str": datetime_str,
            "parsed_datetime": dt.isoformat(),
            "timezone": timezone,
            "timezone_offset": dt.strftime("%z"),
            "unit": output_unit
        }

        logger.info(f"Successfully converted '{datetime_str}' to timestamp: {timestamp}")
        return result

    except ValueError as e:
        logger.error(f"Failed to parse datetime: {e}")
        return {
            "error": str(e),
            "datetime_str": datetime_str,
            "timezone": timezone
        }
    except Exception as e:
        logger.error(f"Unexpected error in timestamp conversion: {e}", exc_info=True)
        return {
            "error": f"Unexpected error: {e!s}",
            "datetime_str": datetime_str,
            "timezone": timezone
        }


def get_current_timestamp(
    timezone: str = "UTC",
    output_unit: str = "milliseconds"
) -> Dict[str, Any]:
    """
    Get current timestamp in specified timezone and unit.

    Args:
        timezone: Timezone for current time (default: "UTC")
        output_unit: Output unit for timestamp (default: "milliseconds")
            Options: "milliseconds", "seconds"

    Returns:
        Dictionary containing current timestamp and datetime information
    """
    try:
        tz = parse_timezone(timezone)
        now = datetime.now(tz)

        timestamp_seconds = now.timestamp()

        if output_unit == "milliseconds":
            timestamp = int(timestamp_seconds * 1000)
        elif output_unit == "seconds":
            timestamp = int(timestamp_seconds)
        else:
            return {
                "error": f"Invalid output_unit: '{output_unit}'. Must be 'milliseconds' or 'seconds'."
            }

        return {
            "success": True,
            "timestamp": timestamp,
            "current_datetime": now.isoformat(),
            "timezone": timezone,
            "timezone_offset": now.strftime("%z"),
            "unit": output_unit
        }

    except Exception as e:
        logger.error(f"Error getting current timestamp: {e}", exc_info=True)
        return {"error": str(e)}
