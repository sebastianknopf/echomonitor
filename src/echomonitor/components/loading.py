"""Reusable loading screen component."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import streamlit as st


_LOADING_SCREEN_HTML = """
<div class="echomonitor-loading-screen" role="status" aria-label="Loading">
    <div class="echomonitor-loading-spinner"></div>
</div>
<style>
.echomonitor-loading-screen {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: calc(100vh - 6rem);
    width: 100%;
}

.echomonitor-loading-spinner {
    width: 3rem;
    height: 3rem;
    border: 0.3rem solid rgba(23, 50, 77, 0.18);
    border-top-color: #17324D;
    border-radius: 50%;
    animation: echomonitor-loading-spin 0.8s linear infinite;
}

@keyframes echomonitor-loading-spin {
    to {
        transform: rotate(360deg);
    }
}

@media (prefers-reduced-motion: reduce) {
    .echomonitor-loading-spinner {
        animation-duration: 1.6s;
    }
}
</style>
"""


@contextmanager
def loading_screen() -> Iterator[None]:
    """Display a centered circular loader while a view is rendered."""
    placeholder = st.empty()
    placeholder.markdown(
        _LOADING_SCREEN_HTML,
        unsafe_allow_html=True,
    )

    try:
        yield
    finally:
        placeholder.empty()
