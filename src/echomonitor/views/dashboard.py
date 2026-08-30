"""Dashboard view for EchoMonitor."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st

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

    st.subheader("GTFS Static Import")
    _render_import_details(snapshot.static)
    _render_static_object_cards(snapshot.static)

    st.write("")
    st.subheader("Data Sources")
    _render_datasource_cards(snapshot.active_datasource_count)

    st.caption("Dashboard data refreshes automatically every 30 seconds.")


def _load_dashboard_snapshot(client: ApiClient) -> DashboardSnapshot:
    """Load all API data required by the dashboard."""
    statistics_payload = client.get_json("/api/monitoring/statistics")
    system_payload = client.get_json("/api/monitoring/system")

    return DashboardSnapshot(
        static=parse_static_statistics(statistics_payload),
        active_datasource_count=parse_datasource_count(system_payload),
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
    """Render a compact label-value row without a card or icon."""
    label_column, value_column = st.columns([1, 4], gap="medium")

    with label_column:
        st.markdown(f"**{label}**")

    with value_column:
        st.markdown(value)


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


def _render_datasource_cards(active_datasource_count: int) -> None:
    """Render datasource KPIs in their own section."""
    columns = st.columns(4, gap="medium")

    with columns[0]:
        _render_metric_card("Activated Data Sources", active_datasource_count)


def _render_metric_card(label: str, value: int) -> None:
    """Render a consistent KPI card."""
    with st.container(
        border=True,
        height=CARD_HEIGHT,
        vertical_alignment="center",
    ):
        st.metric(label, f"{value:,}")


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
