"""Dashboard view for EchoMonitor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st

from echomonitor.models.availability import (
    RouteAvailability,
    parse_active_alert_count,
    parse_route_availability,
    parse_routes,
)
from echomonitor.models.conflicts import parse_conflicts
from echomonitor.models.monitoring import (
    DashboardSnapshot,
    StaticStatistics,
    parse_datasource_count,
    parse_static_statistics,
)
from echomonitor.services.api_client import ApiClient, ApiError
from echomonitor.session.state import logout

REFRESH_INTERVAL = "30s"
CARD_HEIGHT = 150


@dataclass(frozen=True, slots=True)
class RealtimeAvailabilitySnapshot:
    """Aggregated GTFS-RT availability metrics for the dashboard."""

    active_alert_count: int
    realtime_percentage: float
    vehicle_percentage: float


@dataclass(frozen=True, slots=True)
class DashboardViewSnapshot:
    """Complete dashboard snapshot assembled from monitoring endpoints."""

    monitoring: DashboardSnapshot
    realtime: RealtimeAvailabilitySnapshot
    disturbed_datasource_count: int


def render_dashboard(client: ApiClient) -> None:
    """Render the dashboard and refresh its API-backed content every 30 seconds."""
    _render_dashboard_content(client)


@st.fragment(run_every=REFRESH_INTERVAL)
def _render_dashboard_content(client: ApiClient) -> None:
    """Load and render the current monitoring snapshot."""
    try:
        snapshot = _load_dashboard_snapshot(client)
    except ApiError as exc:
        if exc.status_code == 401:
            logout()
            st.rerun()

        st.error(str(exc))
        return
    except ValueError as exc:
        st.error(str(exc))
        return

    st.subheader("GTFS-RT Availability")
    _render_realtime_availability_cards(snapshot.realtime)

    st.write("")
    st.subheader("GTFS Static Import")
    _render_import_details(snapshot.monitoring.static)
    _render_static_object_cards(snapshot.monitoring.static)

    st.write("")
    st.subheader("Data Sources")
    _render_datasource_cards(
        snapshot.monitoring.active_datasource_count,
        snapshot.disturbed_datasource_count,
    )

    st.caption("Dashboard data refreshes automatically every 30 seconds.")


def _load_dashboard_snapshot(client: ApiClient) -> DashboardViewSnapshot:
    """Load all API data required by the dashboard."""
    statistics_payload = client.get_json("/api/monitoring/statistics")
    system_payload = client.get_json("/api/monitoring/system")
    conflicts_payload = client.get_json("/api/monitoring/conflicts")

    routes = parse_routes(system_payload)
    availability = parse_route_availability(
        statistics_payload,
        routes,
    )

    monitoring_snapshot = DashboardSnapshot(
        static=parse_static_statistics(statistics_payload),
        active_datasource_count=parse_datasource_count(system_payload),
    )
    realtime_snapshot = RealtimeAvailabilitySnapshot(
        active_alert_count=parse_active_alert_count(statistics_payload),
        realtime_percentage=_calculate_overall_percentage(
            availability,
            numerator="realtime",
        ),
        vehicle_percentage=_calculate_overall_percentage(
            availability,
            numerator="vehicle",
        ),
    )

    conflicts = parse_conflicts(conflicts_payload)
    disturbed_datasource_count = len(
        {
            conflict.datasource_id
            for conflict in conflicts
            if conflict.code == 1001
        }
    )

    return DashboardViewSnapshot(
        monitoring=monitoring_snapshot,
        realtime=realtime_snapshot,
        disturbed_datasource_count=disturbed_datasource_count,
    )


def _calculate_overall_percentage(
    availability: tuple[RouteAvailability, ...],
    *,
    numerator: str,
) -> float:
    """Calculate weighted GTFS-RT availability across all routes."""
    total_running_trips = sum(
        item.num_running_trips
        for item in availability
    )
    if total_running_trips <= 0:
        return 0.0

    if numerator == "realtime":
        available_trips = sum(
            item.num_realtime_trips
            for item in availability
        )
    elif numerator == "vehicle":
        available_trips = sum(
            item.num_vehicles
            for item in availability
        )
    else:
        raise ValueError(f"Unsupported availability numerator: {numerator}")

    return min(
        max((available_trips / total_running_trips) * 100.0, 0.0),
        100.0,
    )


def _render_realtime_availability_cards(
    snapshot: RealtimeAvailabilitySnapshot,
) -> None:
    """Render aggregated GTFS-RT availability KPIs."""
    columns = st.columns(3, gap="medium")

    with columns[0]:
        _render_metric_card(
            "Active Service Alerts",
            snapshot.active_alert_count,
        )

    with columns[1]:
        _render_metric_card(
            "Realtime Availability",
            f"{snapshot.realtime_percentage:.1f}%",
        )

    with columns[2]:
        _render_metric_card(
            "Vehicle Availability",
            f"{snapshot.vehicle_percentage:.1f}%",
        )


def _render_import_details(statistics: StaticStatistics) -> None:
    """Render non-KPI GTFS Static import information as simple styled rows."""
    _render_detail_row(
        "Last Import Timestamp",
        _format_import_timestamp(statistics.last_import_timestamp),
    )
    _render_detail_row(
        "Last Import Status",
        _format_import_status(
            statistics.last_import_status,
            statistics.last_import_timestamp,
        ),
    )
    _render_detail_row(
        "Imported Operation Days",
        _format_operation_days(statistics.operation_day_dates),
    )

    st.write("")


def _render_detail_row(label: str, value: str) -> None:
    """Render a compact GTFS Static label-value row."""
    st.html(
        f"""
        <div style="
            display: grid;
            grid-template-columns: 11.5rem max-content;
            column-gap: 0.75rem;
            align-items: baseline;
            margin: 0.2rem 0;
        ">
            <div style="font-weight: 600;">
                {label}
            </div>
            <div>
                {value}
            </div>
        </div>
        """
    )


def _render_static_object_cards(statistics: StaticStatistics) -> None:
    """Render GTFS Static object counts as equal-width KPI cards."""
    columns = st.columns(4, gap="medium")

    metrics = (
        ("Agencies", statistics.num_agencies),
        ("Routes", statistics.num_routes),
        ("Stops", statistics.num_stops),
        ("Trips", statistics.num_trips),
    )

    for column, (label, value) in zip(columns, metrics, strict=True):
        with column:
            _render_metric_card(label, value)


def _render_datasource_cards(
    active_datasource_count: int,
    disturbed_datasource_count: int,
) -> None:
    """Render datasource KPIs in their own section."""
    columns = st.columns(4, gap="medium")

    with columns[0]:
        _render_metric_card("Activated Data Sources", active_datasource_count)

    if disturbed_datasource_count > 0:
        with columns[1]:
            _render_disturbed_datasource_card(disturbed_datasource_count)


def _render_disturbed_datasource_card(disturbed_datasource_count: int) -> None:
    """Render a subtly highlighted card for datasource failures."""
    st.html(
        f"""
        <div style="
            min-height: {CARD_HEIGHT}px;
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
            justify-content: center;
            padding: 1rem 1.1rem;
            border: 1px solid #E7B1B1;
            border-left: 4px solid #C96B6B;
            border-radius: 0.75rem;
            background: #FDECEC;
        ">
            <div style="
                font-size: 0.875rem;
                color: rgba(49, 51, 63, 0.72);
                margin-bottom: 0.2rem;
            ">
                Erroneous Data Sources
            </div>
            <div style="
                font-size: 2.25rem;
                line-height: 1.1;
                font-weight: 600;
                color: #4A2F2F;
                margin-bottom: 0.55rem;
            ">
                {disturbed_datasource_count:,}
            </div>
            <div style="
                font-size: 0.8rem;
                line-height: 1.35;
                color: rgba(74, 47, 47, 0.72);
            ">
                These data sources currently have a Datasource Failure conflict.
            </div>
        </div>
        """
    )


def _render_metric_card(label: str, value: int | str) -> None:
    """Render a consistent KPI card."""
    formatted_value = f"{value:,}" if isinstance(value, int) else value

    with st.container(
        border=True,
        height=CARD_HEIGHT,
        vertical_alignment="center",
    ):
        st.metric(label, formatted_value)


def _format_import_timestamp(timestamp: datetime | None) -> str:
    if timestamp is None:
        return "Never"

    localized = _to_client_timezone(timestamp)
    return localized.strftime("%b %d, %Y %I:%M %p %Z")


def _to_client_timezone(timestamp: datetime) -> datetime:
    """Convert a timezone-aware timestamp to the browser timezone when available."""
    if timestamp.tzinfo is None:
        return timestamp

    timezone_name = _get_client_timezone_name()
    if timezone_name is None:
        return timestamp

    try:
        return timestamp.astimezone(ZoneInfo(timezone_name))
    except ZoneInfoNotFoundError:
        return timestamp


def _get_client_timezone_name() -> str | None:
    """Read the browser timezone from Streamlit context when available."""
    context = getattr(st, "context", None)
    if context is None:
        return None

    timezone_name = getattr(context, "timezone", None)
    if isinstance(timezone_name, str) and timezone_name:
        return timezone_name

    return None


def _format_import_status(status: str | None, timestamp: datetime | None) -> str:
    if timestamp is None:
        return "No Import Yet"
    if status is None:
        return "Not Available"

    return status.replace("_", " ").title()


def _format_operation_days(operation_days: tuple[date, ...]) -> str:
    """Format operation days for the dashboard detail row."""
    if not operation_days:
        return "No operation days imported."

    return " · ".join(day.strftime("%b %d, %Y") for day in operation_days)
