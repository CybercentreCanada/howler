from datetime import datetime, timedelta, timezone

import pytest
from howler.common.exceptions import HowlerInvalidParameterException

from sync.utils.parsers import parse_datetime

VALID_DATES = {
    "basic_datetime": ("2023-01-01T12:00:00", datetime(2023, 1, 1, 12, 0, 0)),
    "datetime_with_microseconds": ("2023-01-01T12:00:00.123456", datetime(2023, 1, 1, 12, 0, 0, 123456)),
    "datetime_with_timezone+0": ("2023-01-01T12:00:00+00:00", datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)),
    "datetime_with_timezone_z_format": ("2023-01-01T12:00:00Z", datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)),
    "datetime_with_microseconds_and_non_utc_timezone": (
        "2023-01-01T12:00:00.123456+05:30",
        datetime(2023, 1, 1, 12, 0, 0, 123456, tzinfo=timezone(timedelta(hours=5, minutes=30))),
    ),
}

INVALID_DATES = {
    "not_a_datetime": "not a datetime",
    "not_iso": "01-01-2023 12:00:00",
    "a_number": "1234567890",
}


@pytest.mark.parametrize("date_str, expected_date", VALID_DATES.values(), ids=VALID_DATES.keys())
def test_valid_datetime(date_str, expected_date):
    parsed_date = parse_datetime(date_str)
    assert isinstance(parsed_date, datetime)
    assert parsed_date == expected_date


@pytest.mark.parametrize("invalid_date", INVALID_DATES.values(), ids=INVALID_DATES.keys())
def test_invalid_datetime(invalid_date):
    with pytest.raises(HowlerInvalidParameterException) as exc_info:
        parse_datetime(invalid_date)

    assert str(exc_info.value) == f"Invalid datetime format: {invalid_date}"
