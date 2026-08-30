"""Typed models for route availability monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MonitoringRoute:
    """Route metadata exposed by the monitoring system endpoint."""

    id: str
    short_name: str
    long_name: str | None


@dataclass(frozen=True, slots=True)
class AssignmentCount:
    """Number of realtime trip assignments for one assignment type."""

    assignment_type: str
    count: int


@dataclass(frozen=True, slots=True)
class RouteAvailability:
    """Realtime availability metrics for one route."""

    route_id: str
    route_short_name: str
    num_running_trips: int
    num_realtime_trips: int
    num_monitored_trips: int
    num_vehicles: int
    trip_assignment_counts: tuple[AssignmentCount, ...]
    vehicle_assignment_counts: tuple[AssignmentCount, ...]

    @property
    def realtime_percentage(self) -> float:
        """Return the percentage of running trips with realtime data."""
        return _percentage(self.num_realtime_trips, self.num_running_trips)

    @property
    def monitored_percentage(self) -> float:
        """Return the percentage of running trips that are monitored."""
        return _percentage(self.num_monitored_trips, self.num_running_trips)

    @property
    def vehicle_percentage(self) -> float:
        """Return the percentage of running trips with a vehicle assignment."""
        return _percentage(self.num_vehicles, self.num_running_trips)


def parse_routes(payload: dict[str, Any]) -> tuple[MonitoringRoute, ...]:
    """Parse all routes exposed by the monitoring system endpoint."""
    filters = _require_dict(payload, "filters")
    raw_routes = filters.get("routes")

    if not isinstance(raw_routes, list):
        raise ValueError("The API returned an invalid route list.")

    routes: list[MonitoringRoute] = []
    for raw_route in raw_routes:
        if not isinstance(raw_route, dict):
            raise ValueError("The API returned an invalid route entry.")

        route_id = raw_route.get("id")
        short_name = raw_route.get("short_name")
        long_name = raw_route.get("long_name")

        if not isinstance(route_id, str) or not route_id:
            raise ValueError("The API returned a route without a valid ID.")

        if not isinstance(short_name, str) or not short_name.strip():
            short_name = route_id

        if long_name is not None and not isinstance(long_name, str):
            raise ValueError("The API returned an invalid route long name.")

        routes.append(
            MonitoringRoute(
                id=route_id,
                short_name=short_name.strip(),
                long_name=long_name,
            )
        )

    return tuple(routes)


def parse_active_alert_count(payload: dict[str, Any]) -> int:
    """Parse the number of active realtime service alerts."""
    statistics = _require_dict(payload, "statistics")
    realtime = _require_dict(statistics, "realtime")
    alerts = _require_dict(realtime, "alerts")

    value = alerts.get("num_alerts")
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("The API returned an invalid active alert count.")

    return value


def parse_route_availability(
    payload: dict[str, Any],
    routes: tuple[MonitoringRoute, ...],
) -> tuple[RouteAvailability, ...]:
    """Combine realtime trip and vehicle statistics for all known routes."""
    statistics = _require_dict(payload, "statistics")
    realtime = _require_dict(statistics, "realtime")

    trip_rows = _require_list(realtime, "trips")
    vehicle_rows = _require_list(realtime, "vehicles")

    trips_by_route = _index_statistics(trip_rows, "trip")
    vehicles_by_route = _index_statistics(vehicle_rows, "vehicle")

    availability: list[RouteAvailability] = []

    for route in routes:
        trip_statistics = trips_by_route.get(route.id)
        vehicle_statistics = vehicles_by_route.get(route.id)

        trip_running = (
            _require_statistic_int(trip_statistics, "num_running_trips")
            if trip_statistics is not None
            else None
        )
        vehicle_running = (
            _require_statistic_int(vehicle_statistics, "num_running_trips")
            if vehicle_statistics is not None
            else None
        )

        num_running_trips = trip_running if trip_running is not None else vehicle_running or 0

        availability.append(
            RouteAvailability(
                route_id=route.id,
                route_short_name=route.short_name,
                num_running_trips=num_running_trips,
                num_realtime_trips=(
                    _require_statistic_int(trip_statistics, "num_realtime_trips")
                    if trip_statistics is not None
                    else 0
                ),
                num_monitored_trips=(
                    _require_statistic_int(trip_statistics, "num_monitored_trips")
                    if trip_statistics is not None
                    else 0
                ),
                num_vehicles=(
                    _require_statistic_int(vehicle_statistics, "num_vehicles")
                    if vehicle_statistics is not None
                    else 0
                ),
                trip_assignment_counts=(
                    _parse_assignment_counts(trip_statistics)
                    if trip_statistics is not None
                    else ()
                ),
                vehicle_assignment_counts=(
                    _parse_assignment_counts(vehicle_statistics)
                    if vehicle_statistics is not None
                    else ()
                ),
            )
        )

    return tuple(availability)


def _parse_assignment_counts(
    statistics: dict[str, Any],
) -> tuple[AssignmentCount, ...]:
    """Parse assignment type counts from realtime trip statistics."""
    raw_assignments = statistics.get("assignment_types")
    if not isinstance(raw_assignments, list):
        raise ValueError("The API returned invalid assignment type statistics.")

    assignment_counts: list[AssignmentCount] = []
    for raw_assignment in raw_assignments:
        if not isinstance(raw_assignment, dict):
            raise ValueError("The API returned an invalid assignment type entry.")

        assignment_type = raw_assignment.get("assignment_type")
        count = raw_assignment.get("num_assignments")

        if not isinstance(assignment_type, str) or not assignment_type:
            raise ValueError("The API returned an invalid assignment type.")

        if not isinstance(count, int) or isinstance(count, bool):
            raise ValueError("The API returned an invalid assignment count.")

        assignment_counts.append(
            AssignmentCount(
                assignment_type=assignment_type,
                count=count,
            )
        )

    return tuple(assignment_counts)


def _index_statistics(
    rows: list[Any],
    statistic_type: str,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"The API returned invalid {statistic_type} statistics.")

        route = row.get("route")
        if not isinstance(route, dict):
            raise ValueError(
                f"The API returned {statistic_type} statistics without a valid route."
            )

        route_id = route.get("id")
        if not isinstance(route_id, str) or not route_id:
            raise ValueError(
                f"The API returned {statistic_type} statistics without a valid route ID."
            )

        result[route_id] = row

    return result


def _require_statistic_int(
    statistics: dict[str, Any] | None,
    key: str,
) -> int:
    if statistics is None:
        return 0

    value = statistics.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"The API returned an invalid '{key}' statistic.")

    return value


def _require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"The API response is missing a valid '{key}' object.")
    return value


def _require_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"The API response is missing a valid '{key}' list.")
    return value


def _percentage(value: int, total: int) -> float:
    if total <= 0:
        return 0.0

    return min(max((value / total) * 100.0, 0.0), 100.0)
