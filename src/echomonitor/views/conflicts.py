"""Conflicts view for EchoMonitor."""

from __future__ import annotations

from collections import Counter
from html import escape
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import streamlit as st

from echomonitor.components.charts import render_scrollable_x_chart
from echomonitor.models.conflicts import (
    CONFLICT_TYPE_CODES,
    Conflict,
    DataSource,
    conflict_severity,
    conflict_type_name,
    parse_conflicts,
    parse_data_sources,
)
from echomonitor.services.api_client import ApiClient, ApiError
from echomonitor.session.state import logout

REFRESH_INTERVAL = "30s"
SEVERITY_ORDER = ["Error", "Warning"]
SEVERITY_COLORS = ["#B85C5C", "#D28C45"]
PAGE_KEY = "current_page"
ALL_CONFLICTS_PAGE = "All Conflicts"


def render_conflicts(client: ApiClient) -> None:
    """Render the conflicts dashboard."""
    _render_conflicts_content(client)


@st.fragment(run_every=REFRESH_INTERVAL)
def _render_conflicts_content(client: ApiClient) -> None:
    """Load and render the current conflicts snapshot."""
    try:
        system_payload = client.get_json("/api/monitoring/system")
        conflicts_payload = client.get_json("/api/monitoring/conflicts")
        data_sources = parse_data_sources(system_payload)
        conflicts = parse_conflicts(conflicts_payload)
    except ApiError as exc:
        if exc.status_code == 401:
            logout()
            st.rerun()

        st.error(str(exc))
        return
    except ValueError as exc:
        st.error(str(exc))
        return

    st.subheader("Conflict Distribution")

    if not data_sources:
        st.info("No data sources are available for monitoring.")
        return

    render_scrollable_x_chart(
        _build_conflict_matrix(data_sources, conflicts),
        minimum_category_width=75,
    )

    st.write("")
    _render_compact_conflict_details(conflicts)


    st.caption("Conflict data refreshes automatically every 30 seconds.")


def _render_compact_conflict_details(
    conflicts: tuple[Conflict, ...],
) -> None:
    """Render compact conflict KPIs and the latest conflict entries."""
    st.subheader("Details")

    sorted_conflicts = tuple(
        sorted(
            conflicts,
            key=lambda conflict: conflict.timestamp,
            reverse=True,
        )
    )

    error_count = sum(
        1
        for conflict in sorted_conflicts
        if conflict_severity(conflict.code) == "Error"
    )
    warning_count = sum(
        1
        for conflict in sorted_conflicts
        if conflict_severity(conflict.code) == "Warning"
    )

    columns = st.columns(2, gap="medium")
    with columns[0]:
        _render_conflict_metric_card("Errors", error_count)

    with columns[1]:
        _render_conflict_metric_card("Warnings", warning_count)

    st.write("")
    _render_conflict_list_toolbar()
    render_conflict_list(sorted_conflicts[:10])


def render_conflict_list(
    conflicts: tuple[Conflict, ...],
) -> None:
    """Render conflict cards in the provided order."""
    if not conflicts:
        st.info("No conflicts are available for the selected data source.")
        return

    for conflict in conflicts:
        _render_conflict_card(conflict)


def _render_conflict_card(conflict: Conflict) -> None:
    """Render one conflict as a severity-colored card."""
    severity = conflict_severity(conflict.code)
    background_color = "#FDECEC" if severity == "Error" else "#FFF4CC"
    border_color = "#E7B1B1" if severity == "Error" else "#E8D28A"
    local_timestamp = conflict.timestamp.astimezone(
        ZoneInfo("Europe/Berlin")
    )
    timezone_code = (
        "CEST"
        if local_timestamp.dst() and local_timestamp.dst().total_seconds() != 0
        else "CET"
    )
    timestamp = (
        f"{local_timestamp.strftime('%b %d, %Y %I:%M:%S %p')} "
        f"{timezone_code}"
    )

    properties_html = _format_properties_html(conflict.properties)

    st.markdown(
        f"""
        <div style="
            background: {background_color};
            border: 1px solid {border_color};
            border-radius: 0.75rem;
            padding: 1rem 1.1rem;
            margin-bottom: 0.85rem;
        ">
            <div style="
                font-size: 1rem;
                font-weight: 600;
                margin-bottom: 0.45rem;
            ">
                {escape(conflict_type_name(conflict.code))} ({conflict.code})
            </div>
            <div style="
                display: flex;
                justify-content: space-between;
                gap: 1rem;
                font-size: 0.875rem;
                margin-bottom: 0.8rem;
            ">
                <span>{escape(conflict.datasource_name)}</span>
                <span>{escape(timestamp)}</span>
            </div>
            <div style="
                border-top: 1px solid rgba(0, 0, 0, 0.10);
                padding-top: 0.65rem;
                font-size: 0.875rem;
            ">
                {properties_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _format_properties_html(properties: dict[str, str]) -> str:
    """Format conflict properties as an escaped key-value list."""
    if not properties:
        return "<span>No properties</span>"

    rows = []
    for key, value in properties.items():
        rows.append(
            "<div style=\"display:grid;grid-template-columns:max-content minmax(0, 1fr);"
            "gap:0.4rem;padding:0.15rem 0;\">"
            f"<strong>{escape(key)}</strong>"
            f"<span>{escape(value)}</span>"
            "</div>"
        )

    return "".join(rows)



def _render_conflict_list_toolbar() -> None:
    """Render the compact list notice and navigation to all conflicts."""
    spacer_column, notice_column, action_column = st.columns(
        [4.2, 2.5, 0.7],
        gap="small",
        vertical_alignment="center",
    )

    with notice_column:
        st.html(
            "<div style=\""
            "display:flex;"
            "align-items:center;"
            "justify-content:flex-end;"
            "height:2.375rem;"
            "margin:0;"
            "padding:0;"
            "text-align:right;"
            "font-size:0.875rem;"
            "line-height:1.2;"
            "\">"
            "Only the latest 10 conflicts are shown."
            "</div>"
        )

    with action_column:
        if st.button(
            "View All",
            key="conflicts_view_all",
            type="primary",
            width="stretch",
        ):
            st.session_state[PAGE_KEY] = ALL_CONFLICTS_PAGE
            st.rerun()

def _render_conflict_metric_card(label: str, value: int) -> None:
    """Render one conflict KPI card."""
    with st.container(
        border=True,
        height=150,
        vertical_alignment="center",
    ):
        st.metric(label, f"{value:,}")


def _build_conflict_matrix(
    data_sources: tuple[DataSource, ...],
    conflicts: tuple[Conflict, ...],
) -> alt.Chart:
    """Build a bubble matrix of conflict counts by datasource and conflict type."""
    conflict_labels = [conflict_type_name(code) for code in CONFLICT_TYPE_CODES]

    sorted_data_sources = sorted(
        data_sources,
        key=lambda datasource: datasource.name.casefold(),
    )
    datasource_names = [datasource.name for datasource in sorted_data_sources]

    counts = Counter(
        (conflict.datasource_id, conflict.code)
        for conflict in conflicts
        if conflict.code in CONFLICT_TYPE_CODES
    )

    rows: list[dict[str, str | int]] = []
    for datasource in sorted_data_sources:
        for code in CONFLICT_TYPE_CODES:
            count = counts.get((datasource.id, code), 0)
            if count <= 0:
                continue

            rows.append(
                {
                    "datasource": datasource.name,
                    "conflict": conflict_type_name(code),
                    "code": code,
                    "severity": conflict_severity(code),
                    "count": count,
                }
            )

    frame = pd.DataFrame.from_records(
        rows,
        columns=["datasource", "conflict", "code", "severity", "count"],
    )

    return (
        alt.Chart(frame)
        .mark_circle(opacity=0.82)
        .encode(
            x=alt.X(
                "conflict:N",
                title="Conflict Type",
                sort=conflict_labels,
                scale=alt.Scale(domain=conflict_labels),
                axis=alt.Axis(
                    orient="top",
                    labelAngle=-45,
                    labelOverlap=False,
                    labelLimit=220,
                    grid=False,
                ),
            ),
            y=alt.Y(
                "datasource:N",
                title="Data Source",
                sort=datasource_names,
                scale=alt.Scale(
                    domain=datasource_names,
                    paddingInner=0.55,
                    paddingOuter=0.35,
                ),
                axis=alt.Axis(
                    grid=False,
                ),
            ),
            size=alt.Size(
                "count:Q",
                legend=None,
                scale=alt.Scale(range=[80, 1400]),
            ),
            color=alt.Color(
                "severity:N",
                legend=None,
                sort=SEVERITY_ORDER,
                scale=alt.Scale(
                    domain=SEVERITY_ORDER,
                    range=SEVERITY_COLORS,
                ),
            ),
            tooltip=[
                alt.Tooltip("datasource:N", title="Data Source"),
                alt.Tooltip("conflict:N", title="Conflict Type"),
                alt.Tooltip("code:Q", title="Code", format=".0f"),
                alt.Tooltip("severity:N", title="Severity"),
                alt.Tooltip("count:Q", title="Conflicts", format=".0f"),
            ],
        )
        .properties(height=alt.Step(64))
        .configure_legend(
            orient="top",
            direction="horizontal",
        )
    )
