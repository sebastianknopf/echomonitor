"""Availability view for EchoMonitor."""

from __future__ import annotations

import re
from typing import TypeAlias

import altair as alt
import pandas as pd
import streamlit as st

from echomonitor.components.charts import render_scrollable_x_chart
from echomonitor.models.availability import (
    MonitoringRoute,
    RouteAvailability,
    parse_active_alert_count,
    parse_route_availability,
    parse_routes,
)
from echomonitor.services.api_client import ApiClient, ApiError
from echomonitor.session.state import logout

REFRESH_INTERVAL = "30s"
ROUTE_CACHE_KEY = "availability_routes"
ROUTE_CACHE_BASE_URL_KEY = "availability_routes_base_url"

METRIC_ORDER = ["Realtime", "Monitored", "Vehicle"]
METRIC_COLORS = ["#17324D", "#2F7D8C", "#D28C45"]

ASSIGNMENT_TYPE_ORDER = [
    "DIRECT_BY_ID",
    "MATCH_BY_CACHED_ID",
    "MATCHED_BY_START_STOP",
    "MATCHED_BY_INTERMEDIATE_STOPS",
    "NO_MATCH_GENERAL",
    "NO_MATCH_AMBIGUOUS_TRIP",
]
ASSIGNMENT_TYPE_COLORS = [
    "#17324D",
    "#2F7D8C",
    "#4F9D69",
    "#D28C45",
    "#B85C5C",
    "#7B5EA7",
]

NaturalSortPart: TypeAlias = int | str


def render_availability(client: ApiClient) -> None:
    """Render realtime availability statistics by route."""
    routes = _get_or_load_routes(client)
    if routes is None:
        return

    _render_availability_content(client, routes)


def _get_or_load_routes(
    client: ApiClient,
) -> tuple[MonitoringRoute, ...] | None:
    """Load routes once per API base URL and retain them in session state."""
    cached_base_url = st.session_state.get(ROUTE_CACHE_BASE_URL_KEY)
    cached_routes = st.session_state.get(ROUTE_CACHE_KEY)

    if (
        cached_base_url == client.config.base_url
        and isinstance(cached_routes, tuple)
        and all(isinstance(route, MonitoringRoute) for route in cached_routes)
    ):
        return cached_routes

    try:
        payload = client.get_json("/api/monitoring/system")
        routes = parse_routes(payload)
    except ApiError as exc:
        if exc.status_code == 401:
            logout()
            st.rerun()

        st.error(str(exc))
        return None
    except ValueError as exc:
        st.error(str(exc))
        return None

    st.session_state[ROUTE_CACHE_KEY] = routes
    st.session_state[ROUTE_CACHE_BASE_URL_KEY] = client.config.base_url
    return routes


@st.fragment(run_every=REFRESH_INTERVAL)
def _render_availability_content(
    client: ApiClient,
    routes: tuple[MonitoringRoute, ...],
) -> None:
    """Refresh and render route availability statistics."""
    try:
        payload = client.get_json("/api/monitoring/statistics")
        active_alert_count = parse_active_alert_count(payload)
        availability = parse_route_availability(payload, routes)
    except ApiError as exc:
        if exc.status_code == 401:
            logout()
            st.rerun()

        st.error(str(exc))
        return
    except ValueError as exc:
        st.error(str(exc))
        return

    _render_alerts(active_alert_count)

    st.write("")
    st.subheader("Realtime Availability By Route")

    if not routes:
        st.info("No routes are available for monitoring.")
        return

    if not availability:
        st.info("No availability statistics are available.")
        return

    render_scrollable_x_chart(
        _build_availability_chart(availability),
        minimum_category_width=7,
    )

    st.write("")
    _render_details(routes, availability)

    st.caption("Availability data refreshes automatically every 30 seconds.")


def _render_alerts(active_alert_count: int) -> None:
    """Render active realtime service alerts."""
    st.subheader("Alerts")

    columns = st.columns(4, gap="medium")
    with columns[0]:
        with st.container(
            border=True,
            height=150,
            vertical_alignment="center",
        ):
            st.metric("Active Service Alerts", f"{active_alert_count:,}")


def _build_availability_chart(
    availability: tuple[RouteAvailability, ...],
) -> alt.Chart:
    """Build three grouped percentage bars for each route."""
    sorted_availability = sorted(
        availability,
        key=lambda item: _natural_sort_key(item.route_short_name),
    )

    rows: list[dict[str, str | float]] = []
    for item in sorted_availability:
        rows.extend(
            [
                {
                    "route": item.route_short_name,
                    "route_label": (
                        f"{item.route_short_name} ({item.num_running_trips})"
                    ),
                    "running_trips": item.num_running_trips,
                    "metric": "Realtime",
                    "percentage": item.realtime_percentage,
                },
                {
                    "route": item.route_short_name,
                    "route_label": (
                        f"{item.route_short_name} ({item.num_running_trips})"
                    ),
                    "running_trips": item.num_running_trips,
                    "metric": "Monitored",
                    "percentage": item.monitored_percentage,
                },
                {
                    "route": item.route_short_name,
                    "route_label": (
                        f"{item.route_short_name} ({item.num_running_trips})"
                    ),
                    "running_trips": item.num_running_trips,
                    "metric": "Vehicle",
                    "percentage": item.vehicle_percentage,
                },
            ]
        )

    frame = pd.DataFrame.from_records(rows)
    route_order = [
        f"{item.route_short_name} ({item.num_running_trips})"
        for item in sorted_availability
    ]

    return (
        alt.Chart(frame)
        .mark_bar()
        .encode(
            x=alt.X(
                "route_label:N",
                title="Route (Trips)",
                sort=route_order,
                axis=alt.Axis(
                    labelAngle=-45,
                    labelOverlap=False,
                    labelLimit=180,
                ),
            ),
            xOffset=alt.XOffset(
                "metric:N",
                sort=METRIC_ORDER,
            ),
            y=alt.Y(
                "percentage:Q",
                title="Share Of Trips",
                scale=alt.Scale(domain=[0, 100]),
                axis=alt.Axis(
                    format=".0f",
                    labelExpr="datum.label + '%'",
                ),
            ),
            color=alt.Color(
                "metric:N",
                title=None,
                sort=METRIC_ORDER,
                scale=alt.Scale(
                    domain=METRIC_ORDER,
                    range=METRIC_COLORS,
                ),
            ),
            tooltip=[
                alt.Tooltip("route:N", title="Route"),
                alt.Tooltip(
                    "running_trips:Q",
                    title="Trips",
                    format=".0f",
                ),
                alt.Tooltip("metric:N", title="Metric"),
                alt.Tooltip(
                    "percentage:Q",
                    title="Share",
                    format=".1f",
                ),
            ],
        )
        .properties(height=420)
        .configure_legend(
            orient="top",
            direction="horizontal",
        )
    )


def _render_details(
    routes: tuple[MonitoringRoute, ...],
    availability: tuple[RouteAvailability, ...],
) -> None:
    """Render filterable detail KPIs below the overall chart."""
    title_column, filter_column = st.columns([3, 1], gap="medium")

    with title_column:
        st.subheader("Details")

    sorted_routes = sorted(
        routes,
        key=lambda route: _natural_sort_key(route.short_name),
    )
    route_by_id = {route.id: route for route in sorted_routes}
    route_options: list[str | None] = [None, *[route.id for route in sorted_routes]]

    with filter_column:
        selected_route_id = st.selectbox(
            "Route",
            options=route_options,
            format_func=lambda route_id: _format_route_option(route_id, route_by_id),
            key="availability_route_filter",
            width="stretch",
        )

    selected_availability = _filter_availability(
        availability,
        selected_route_id,
    )
    running_trips = sum(item.num_running_trips for item in selected_availability)
    realtime_percentage = _calculate_percentage(
        selected_availability,
        numerator_attribute="num_realtime_trips",
    )
    monitored_percentage = _calculate_percentage(
        selected_availability,
        numerator_attribute="num_monitored_trips",
    )
    vehicle_percentage = _calculate_percentage(
        selected_availability,
        numerator_attribute="num_vehicles",
    )

    columns = st.columns(4, gap="medium")

    with columns[0]:
        _render_detail_metric_card(
            "Currently Running Trips",
            f"{running_trips:,}",
        )

    with columns[1]:
        _render_detail_metric_card(
            "Realtime Availability",
            f"{realtime_percentage:.1f}%",
        )

    with columns[2]:
        _render_detail_metric_card(
            "Monitored",
            f"{monitored_percentage:.1f}%",
        )

    with columns[3]:
        _render_detail_metric_card(
            "Vehicle Availability",
            f"{vehicle_percentage:.1f}%",
        )

    st.write("")
    _render_assignment_type_charts(selected_availability)


def _render_assignment_type_charts(
    availability: tuple[RouteAvailability, ...],
) -> None:
    """Render trip and vehicle assignment type distributions side by side."""
    trip_rows = _build_assignment_type_rows(
        availability,
        assignment_attribute="trip_assignment_counts",
    )
    vehicle_rows = _build_assignment_type_rows(
        availability,
        assignment_attribute="vehicle_assignment_counts",
    )

    left_column, right_column = st.columns(2, gap="medium")

    with left_column:
        _render_assignment_type_chart(
            title="Trip Assignment Types",
            assignment_rows=trip_rows,
        )

    with right_column:
        _render_assignment_type_chart(
            title="Vehicle Assignment Types",
            assignment_rows=vehicle_rows,
        )


def _render_assignment_type_chart(
    title: str,
    assignment_rows: list[dict[str, str | int | float]],
) -> None:
    """Render one assignment type pie chart."""
    st.markdown(f"#### {title}")

    if not assignment_rows:
        st.info("No assignment type statistics are available.")
        return

    frame = pd.DataFrame.from_records(assignment_rows)

    chart = (
        alt.Chart(frame)
        .mark_arc()
        .encode(
            theta=alt.Theta(
                "percentage:Q",
                stack=True,
            ),
            color=alt.Color(
                "assignment_type:N",
                title=None,
                sort=ASSIGNMENT_TYPE_ORDER,
                scale=alt.Scale(
                    domain=ASSIGNMENT_TYPE_ORDER,
                    range=ASSIGNMENT_TYPE_COLORS,
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "assignment_type:N",
                    title="Assignment Type",
                ),
                alt.Tooltip(
                    "count:Q",
                    title="Assignments",
                    format=".0f",
                ),
                alt.Tooltip(
                    "percentage:Q",
                    title="Share",
                    format=".1f",
                ),
            ],
        )
        .properties(height=360)
        .configure_legend(
            orient="bottom",
            direction="vertical",
        )
    )

    st.altair_chart(chart, width="stretch")


def _build_assignment_type_rows(
    availability: tuple[RouteAvailability, ...],
    assignment_attribute: str,
) -> list[dict[str, str | int | float]]:
    """Aggregate assignment type counts and convert them to percentages."""
    counts = {assignment_type: 0 for assignment_type in ASSIGNMENT_TYPE_ORDER}

    for item in availability:
        assignment_counts = getattr(item, assignment_attribute)
        for assignment in assignment_counts:
            counts.setdefault(assignment.assignment_type, 0)
            counts[assignment.assignment_type] += assignment.count

    total_assignments = sum(counts.values())
    if total_assignments <= 0:
        return []

    ordered_assignment_types = [
        *ASSIGNMENT_TYPE_ORDER,
        *sorted(
            assignment_type
            for assignment_type in counts
            if assignment_type not in ASSIGNMENT_TYPE_ORDER
        ),
    ]

    return [
        {
            "assignment_type": assignment_type,
            "count": counts[assignment_type],
            "percentage": (counts[assignment_type] / total_assignments) * 100.0,
        }
        for assignment_type in ordered_assignment_types
        if counts.get(assignment_type, 0) > 0
    ]


def _format_route_option(
    route_id: str | None,
    route_by_id: dict[str, MonitoringRoute],
) -> str:
    """Format selectbox route options with short and long names."""
    if route_id is None:
        return "All"

    route = route_by_id[route_id]
    if route.long_name and route.long_name.strip():
        return f"{route.short_name} - {route.long_name.strip()}"

    return route.short_name


def _filter_availability(
    availability: tuple[RouteAvailability, ...],
    route_id: str | None,
) -> tuple[RouteAvailability, ...]:
    """Filter availability statistics by route when requested."""
    if route_id is None:
        return availability

    return tuple(
        item
        for item in availability
        if item.route_id == route_id
    )


def _render_detail_metric_card(label: str, value: str) -> None:
    """Render one equal-width detail KPI card."""
    with st.container(
        border=True,
        height=150,
        vertical_alignment="center",
    ):
        st.metric(label, value)


def _calculate_percentage(
    availability: tuple[RouteAvailability, ...],
    numerator_attribute: str,
) -> float:
    """Return a weighted percentage across the selected routes."""
    total_running_trips = sum(item.num_running_trips for item in availability)
    if total_running_trips <= 0:
        return 0.0

    numerator = sum(
        int(getattr(item, numerator_attribute))
        for item in availability
    )
    return min(
        max((numerator / total_running_trips) * 100.0, 0.0),
        100.0,
    )


def _natural_sort_key(value: str) -> tuple[NaturalSortPart, ...]:
    """Return a case-insensitive natural sort key for route short names."""
    parts = re.split(r"(\d+)", value.casefold())
    return tuple(int(part) if part.isdigit() else part for part in parts)
