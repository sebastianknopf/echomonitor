"""Typed models for EchoGTFS monitoring responses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class StaticStatistics:
    """GTFS Static statistics used by the dashboard."""

    last_import_timestamp: datetime | None
    last_import_status: str | None
    num_agencies: int
    num_routes: int
    num_stops: int
    num_trips: int
    operation_day_dates: tuple[date, ...]

    @property
    def total_objects(self) -> int:
        """Return the total number of imported GTFS Static objects."""
        return self.num_agencies + self.num_routes + self.num_stops + self.num_trips


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    """Monitoring values displayed on the dashboard."""

    static: StaticStatistics
    active_datasource_count: int


def parse_instance(payload: dict[str, Any]) -> str:
    """Parse the EchoGTFS instance name from the monitoring system response."""
    instance = payload.get("instance")

    if not isinstance(instance, str) or not instance.strip():
        raise ValueError("The API response is missing a valid 'instance' value.")

    return instance.strip()


def parse_static_statistics(payload: dict[str, Any]) -> StaticStatistics:
    """Parse the static statistics section of the monitoring response."""
    statistics = _require_dict(payload, "statistics")
    static = _require_dict(statistics, "static")

    return StaticStatistics(
        last_import_timestamp=_parse_datetime(static.get("last_import_timestamp")),
        last_import_status=_optional_string(static.get("last_import_status")),
        num_agencies=_require_int(static, "num_agencies"),
        num_routes=_require_int(static, "num_routes"),
        num_stops=_require_int(static, "num_stops"),
        num_trips=_require_int(static, "num_trips"),
        operation_day_dates=_parse_dates(static.get("operation_day_dates")),
    )


def parse_datasource_count(payload: dict[str, Any]) -> int:
    """Return the number of data sources exposed by the monitoring system."""
    filters = _require_dict(payload, "filters")
    datasources = filters.get("datasources")

    if not isinstance(datasources, list):
        raise ValueError("The API returned an invalid datasource list.")

    return len(datasources)


def _require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"The API response is missing a valid '{key}' object.")
    return value


def _require_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"The API response is missing a valid '{key}' value.")
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("The API returned an invalid status value.")
    return value


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("The API returned an invalid import timestamp.")

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("The API returned an invalid import timestamp.") from exc


def _parse_dates(value: Any) -> tuple[date, ...]:
    if not isinstance(value, list):
        raise ValueError("The API returned an invalid operation day list.")

    parsed_dates: list[date] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("The API returned an invalid operation day value.")
        try:
            parsed_dates.append(date.fromisoformat(item))
        except ValueError as exc:
            raise ValueError("The API returned an invalid operation day value.") from exc

    return tuple(parsed_dates)
