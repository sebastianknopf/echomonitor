"""Internal full conflict list view for EchoMonitor."""

from __future__ import annotations

import streamlit as st

from echomonitor.components.metric_card import render_metric_card
from echomonitor.models.conflicts import (
    CONFLICT_TYPE_CODES,
    CONFLICT_TYPE_NAMES,
    Conflict,
    DataSource,
    conflict_severity,
    parse_conflicts,
    parse_data_sources,
)
from echomonitor.services.api_client import ApiClient, ApiError
from echomonitor.session.state import logout
from echomonitor.views.conflicts import REFRESH_INTERVAL, render_conflict_list


def render_all_conflicts(client: ApiClient) -> None:
    """Render the complete conflict list with filtering controls."""
    _render_all_conflicts_content(client)


@st.fragment(run_every=REFRESH_INTERVAL)
def _render_all_conflicts_content(client: ApiClient) -> None:
    """Load and render all conflicts."""
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

    _render_filters_and_conflicts(
        client,
        data_sources,
        conflicts,
    )

    st.caption("Conflict data refreshes automatically every 30 seconds.")


def _render_filters_and_conflicts(
    client: ApiClient,
    data_sources: tuple[DataSource, ...],
    all_conflicts: tuple[Conflict, ...],
) -> None:
    """Render filters followed directly by the complete matching list."""
    level_column, conflict_type_column, datasource_column = st.columns(
        [1, 1.35, 1.35],
        gap="medium",
    )

    with level_column:
        selected_level = st.selectbox(
            "Level",
            options=["All", "Warning", "Error"],
            key="all_conflicts_level_filter",
            width="stretch",
        )

    conflict_type_options: list[int | None] = [
        None,
        *CONFLICT_TYPE_CODES,
    ]
    with conflict_type_column:
        selected_conflict_type = st.selectbox(
            "Conflict Type",
            options=conflict_type_options,
            format_func=_format_conflict_type_option,
            key="all_conflicts_type_filter",
            width="stretch",
        )

    sorted_data_sources = sorted(
        data_sources,
        key=lambda datasource: datasource.name.casefold(),
    )
    datasource_by_id = {
        datasource.id: datasource
        for datasource in sorted_data_sources
    }
    datasource_options: list[int | None] = [
        None,
        *[datasource.id for datasource in sorted_data_sources],
    ]

    with datasource_column:
        selected_datasource_id = st.selectbox(
            "Data Source",
            options=datasource_options,
            format_func=lambda datasource_id: _format_datasource_option(
                datasource_id,
                datasource_by_id,
            ),
            key="all_conflicts_datasource_filter",
            width="stretch",
        )

    try:
        selected_conflicts = _load_conflicts_for_datasource(
            client,
            selected_datasource_id,
            all_conflicts,
        )
    except ApiError as exc:
        if exc.status_code == 401:
            logout()
            st.rerun()

        st.error(str(exc))
        return
    except ValueError as exc:
        st.error(str(exc))
        return

    filtered_conflicts = _filter_conflicts(
        selected_conflicts,
        level=selected_level,
        conflict_type=selected_conflict_type,
    )

    error_count = sum(
        conflict_severity(conflict.code) == "Error"
        for conflict in filtered_conflicts
    )
    warning_count = sum(
        conflict_severity(conflict.code) == "Warning"
        for conflict in filtered_conflicts
    )

    st.write("")
    metric_columns = st.columns(4, gap="medium")

    with metric_columns[0]:
        render_metric_card(
            "Errors",
            f"{error_count:,}",
            icon="error",
            key="all_conflicts_errors_card",
        )

    with metric_columns[1]:
        render_metric_card(
            "Warnings",
            f"{warning_count:,}",
            icon="warning",
            key="all_conflicts_warnings_card",
        )

    st.write("")
    render_conflict_list(filtered_conflicts)


def _filter_conflicts(
    conflicts: tuple[Conflict, ...],
    *,
    level: str,
    conflict_type: int | None,
) -> tuple[Conflict, ...]:
    """Filter conflicts and sort the newest entries first."""
    filtered = (
        conflict
        for conflict in conflicts
        if (
            level == "All"
            or conflict_severity(conflict.code) == level
        )
        and (
            conflict_type is None
            or conflict.code == conflict_type
        )
    )
    return tuple(
        sorted(
            filtered,
            key=lambda conflict: conflict.timestamp,
            reverse=True,
        )
    )


def _format_conflict_type_option(conflict_type: int | None) -> str:
    """Format conflict type options while retaining numeric codes internally."""
    if conflict_type is None:
        return "All"

    return CONFLICT_TYPE_NAMES[conflict_type]


def _format_datasource_option(
    datasource_id: int | None,
    datasource_by_id: dict[int, DataSource],
) -> str:
    """Format datasource options while retaining IDs internally."""
    if datasource_id is None:
        return "All"

    return datasource_by_id[datasource_id].name


def _load_conflicts_for_datasource(
    client: ApiClient,
    datasource_id: int | None,
    all_conflicts: tuple[Conflict, ...],
) -> tuple[Conflict, ...]:
    """Load conflicts for one datasource, or reuse the complete snapshot."""
    if datasource_id is None:
        return all_conflicts

    payload = client.get_json(
        f"/api/monitoring/conflicts?datasourceId={datasource_id}"
    )
    return parse_conflicts(payload)
