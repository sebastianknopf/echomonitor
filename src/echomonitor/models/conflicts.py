"""Typed models for conflict monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any

CONFLICT_TYPE_NAMES: dict[int, str] = {
    1001: "Datasource Failure",
    1005: "No Agency Found",
    1003: "No Stop Found",
    1002: "No Route Found",
    1004: "No Trip Found",
    2001: "Implied Additional Stop",
    2002: "Implied Canceled Stop",
    2003: "Wrong Quay",
    2008: "Agency No Global Id",
    2005: "Stop No Global Id",
    2004: "Route No Global Id",
    2006: "Trip No Global Id",
    2007: "Premature Departure",
}

CONFLICT_TYPE_CODES: tuple[int, ...] = tuple(CONFLICT_TYPE_NAMES)


@dataclass(frozen=True, slots=True)
class DataSource:
    """Monitoring data source."""

    id: int
    name: str


@dataclass(frozen=True, slots=True)
class Conflict:
    """One active monitoring conflict."""

    id: str
    timestamp: datetime
    code: int
    message: str
    datasource_id: int
    datasource_name: str
    properties: dict[str, str]


def parse_data_sources(payload: dict[str, Any]) -> tuple[DataSource, ...]:
    """Parse all data sources exposed by the monitoring system endpoint."""
    filters = _require_dict(payload, "filters")
    raw_data_sources = filters.get("datasources")
    if not isinstance(raw_data_sources, list):
        raise ValueError("The API returned an invalid datasource list.")

    data_sources: list[DataSource] = []
    for raw_data_source in raw_data_sources:
        if not isinstance(raw_data_source, dict):
            raise ValueError("The API returned an invalid datasource entry.")

        datasource_id = raw_data_source.get("id")
        name = raw_data_source.get("name")

        if not isinstance(datasource_id, int) or isinstance(datasource_id, bool):
            raise ValueError("The API returned a datasource without a valid ID.")

        if not isinstance(name, str) or not name.strip():
            raise ValueError("The API returned a datasource without a valid name.")

        data_sources.append(
            DataSource(
                id=datasource_id,
                name=name.strip(),
            )
        )

    return tuple(data_sources)


def parse_conflicts(payload: dict[str, Any]) -> tuple[Conflict, ...]:
    """Parse active monitoring conflicts."""
    raw_conflicts = payload.get("conflicts")
    if not isinstance(raw_conflicts, list):
        raise ValueError("The API returned an invalid conflict list.")

    conflicts: list[Conflict] = []
    for raw_conflict in raw_conflicts:
        if not isinstance(raw_conflict, dict):
            raise ValueError("The API returned an invalid conflict entry.")

        conflict_id = raw_conflict.get("id")
        timestamp = raw_conflict.get("timestamp")
        code = raw_conflict.get("code")
        message = raw_conflict.get("message")
        datasource = raw_conflict.get("datasource")
        properties = raw_conflict.get("properties")

        if not isinstance(conflict_id, str) or not conflict_id:
            raise ValueError("The API returned a conflict without a valid ID.")

        if not isinstance(timestamp, str) or not timestamp:
            raise ValueError("The API returned a conflict without a valid timestamp.")

        try:
            parsed_timestamp = datetime.fromisoformat(
                timestamp.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise ValueError(
                "The API returned a conflict with an invalid timestamp."
            ) from exc

        if not isinstance(code, int) or isinstance(code, bool):
            raise ValueError("The API returned a conflict without a valid code.")

        if not isinstance(message, str) or not message.strip():
            raise ValueError("The API returned a conflict without a valid message.")

        if not isinstance(datasource, dict):
            raise ValueError("The API returned a conflict without a valid datasource.")

        datasource_id = datasource.get("id")
        datasource_name = datasource.get("name")

        if not isinstance(datasource_id, int) or isinstance(datasource_id, bool):
            raise ValueError("The API returned a conflict with an invalid datasource ID.")

        if not isinstance(datasource_name, str) or not datasource_name.strip():
            raise ValueError("The API returned a conflict with an invalid datasource name.")

        if properties is None:
            properties = {}

        if not isinstance(properties, dict):
            raise ValueError("The API returned invalid conflict properties.")

        parsed_properties: dict[str, str] = {}
        for key, value in properties.items():
            if not isinstance(key, str):
                raise ValueError("The API returned invalid conflict properties.")

            parsed_properties[key] = _format_property_value(value)

        conflicts.append(
            Conflict(
                id=conflict_id,
                timestamp=parsed_timestamp,
                code=code,
                message=message.strip(),
                datasource_id=datasource_id,
                datasource_name=datasource_name.strip(),
                properties=parsed_properties,
            )
        )

    return tuple(conflicts)


def conflict_severity(code: int) -> str:
    """Return the severity encoded by the conflict code range."""
    if 1000 <= code <= 1999:
        return "Error"

    if 2000 <= code <= 2999:
        return "Warning"

    raise ValueError(f"Unsupported conflict code: {code}")


def conflict_type_name(code: int) -> str:
    """Return the configured display name for a conflict type."""
    try:
        return CONFLICT_TYPE_NAMES[code]
    except KeyError as exc:
        raise ValueError(f"Unsupported conflict code: {code}") from exc


def _format_property_value(value: Any) -> str:
    """Convert API property values into safe display text."""
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, (int, float)):
        return str(value)

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
        )
    except (TypeError, ValueError):
        return str(value)


def _require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"The API response is missing a valid '{key}' object.")
    return value
