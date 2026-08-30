"""Streamlit entry point for EchoMonitor."""

from __future__ import annotations

import streamlit as st

from echomonitor.session.state import get_api_client, initialize_session_state
from echomonitor.views.login import render_login_view
from echomonitor.views.main import render_main_view


def main() -> None:
    """Render the appropriate view for the current Streamlit session."""
    st.set_page_config(
        page_title="EchoMonitor",
        page_icon=None,
        layout="wide",
        initial_sidebar_state="expanded",
    )

    initialize_session_state()

    if not st.session_state.authenticated:
        render_login_view()
        return

    client = get_api_client()
    render_main_view(client)


if __name__ == "__main__":
    main()
