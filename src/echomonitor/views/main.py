"""Main application view."""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from echomonitor.models.monitoring import parse_instance
from echomonitor.services.api_client import ApiClient, ApiError
from echomonitor.session.state import logout
from echomonitor.views.availability import render_availability
from echomonitor.views.dashboard import render_dashboard
from echomonitor.views.conflicts import render_conflicts

PAGE_KEY = "current_page"
DEFAULT_PAGE = "Dashboard"

PageRenderer = Callable[[ApiClient], None]


def render_main_view(client: ApiClient) -> None:
    """Render the authenticated application shell."""
    st.session_state.setdefault(PAGE_KEY, DEFAULT_PAGE)

    instance = _load_instance(client)
    if instance is None:
        return

    with st.sidebar:
        st.title("EchoMonitor")
        st.caption(instance)
        _render_navigation()

    page = str(st.session_state[PAGE_KEY])
    st.title(page)

    renderers: dict[str, PageRenderer] = {
        "Dashboard": render_dashboard,
        "Availability": render_availability,
        "Conflicts": render_conflicts,
    }
    renderers.get(page, render_dashboard)(client)


def _load_instance(client: ApiClient) -> str | None:
    """Load the current EchoGTFS instance name."""
    try:
        payload = client.get_json("/api/monitoring/system")
        return parse_instance(payload)
    except ApiError as exc:
        if exc.status_code == 401:
            logout()
            st.rerun()

        st.error(str(exc))
        return None
    except ValueError as exc:
        st.error(str(exc))
        return None


def _render_navigation() -> None:
    """Render sidebar navigation as a simple list of entries."""
    navigation_items = ("Dashboard", "Availability", "Conflicts")

    for item in navigation_items:
        if st.button(
            item,
            key=f"nav_{item.lower().replace(' ', '_')}",
            type="primary" if st.session_state[PAGE_KEY] == item else "tertiary",
            width="stretch",
        ):
            st.session_state[PAGE_KEY] = item
            st.rerun()

    st.divider()

    if st.button(
        "Log Out",
        key="nav_log_out",
        type="tertiary",
        width="stretch",
    ):
        logout()
        st.session_state.pop(PAGE_KEY, None)
        st.rerun()
