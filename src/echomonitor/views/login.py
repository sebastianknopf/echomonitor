"""Login view."""

from __future__ import annotations

import streamlit as st

from echomonitor.services.api_client import ApiError
from echomonitor.session.state import authenticate


def render_login_view() -> None:
    """Render the API selection and login form."""
    st.title("EchoMonitor")
    st.subheader("Sign In")

    with st.form("login_form"):
        base_url = st.text_input(
            "API Base URL",
            key="login_base_url",
            placeholder="https://api.example.com",
            help=(
                "Enter only the API base URL. EchoMonitor adds "
                "/api/auth/token and other API paths automatically."
            ),
        )
        username = st.text_input(
            "Username",
            key="login_username",
            autocomplete="username",
        )
        password = st.text_input(
            "Password",
            key="login_password",
            type="password",
            autocomplete="current-password",
        )
        submitted = st.form_submit_button(
            "Sign In",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return

    if not base_url.strip():
        st.error("Please enter the API base URL.")
        return

    if not username.strip():
        st.error("Please enter your username.")
        return

    if not password:
        st.error("Please enter your password.")
        return

    try:
        authenticate(base_url, username, password)
    except (ApiError, ValueError) as exc:
        st.error(str(exc))
        return

    st.session_state.pop("login_username", None)
    st.session_state.pop("login_password", None)
    st.rerun()
