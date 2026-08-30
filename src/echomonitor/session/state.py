"""Session-state management for EchoMonitor."""

from __future__ import annotations

from typing import cast

import streamlit as st

from echomonitor.models.api_config import ApiConfig
from echomonitor.services.api_client import ApiClient

AUTHENTICATED_KEY = "authenticated"
API_CLIENT_KEY = "api_client"


def initialize_session_state() -> None:
    """Initialize all session-local state required by the application."""
    if AUTHENTICATED_KEY not in st.session_state:
        st.session_state[AUTHENTICATED_KEY] = False

    if API_CLIENT_KEY not in st.session_state:
        st.session_state[API_CLIENT_KEY] = None


def create_api_client(base_url: str) -> ApiClient:
    """Create and store a session-bound API client."""
    client = ApiClient(config=ApiConfig(base_url=base_url))
    st.session_state[API_CLIENT_KEY] = client
    return client


def get_api_client() -> ApiClient:
    """Return the current session-bound API client."""
    client = st.session_state.get(API_CLIENT_KEY)
    if not isinstance(client, ApiClient):
        raise RuntimeError("No authenticated API client is available.")
    return cast(ApiClient, client)


def authenticate(base_url: str, username: str, password: str) -> None:
    """Authenticate the current session against the configured API."""
    client = create_api_client(base_url)
    try:
        client.login(username=username, password=password)
    except Exception:
        st.session_state[API_CLIENT_KEY] = None
        st.session_state[AUTHENTICATED_KEY] = False
        raise

    st.session_state[AUTHENTICATED_KEY] = True


def logout() -> None:
    """Clear authentication state for the current browser session."""
    client = st.session_state.get(API_CLIENT_KEY)
    if isinstance(client, ApiClient):
        client.clear_token()

    st.session_state[API_CLIENT_KEY] = None
    st.session_state[AUTHENTICATED_KEY] = False
