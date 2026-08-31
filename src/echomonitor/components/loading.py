"""Reusable loading screen component."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import streamlit as st


_LOADING_SCREEN_HTML = """
<style>
@keyframes echomonitor-loading-spin {
    0% {
        transform: rotate(0deg);
    }

    100% {
        transform: rotate(360deg);
    }
}

.echomonitor-loading-screen {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: calc(100vh - 6rem);
    width: 100%;
}

.echomonitor-loading-spinner {
    box-sizing: border-box;
    width: 3rem;
    height: 3rem;
    border: 0.3rem solid rgba(23, 50, 77, 0.18);
    border-top-color: #17324D;
    border-radius: 50%;
    animation-name: echomonitor-loading-spin;
    animation-duration: 0.8s;
    animation-timing-function: linear;
    animation-iteration-count: infinite;
    transform-origin: 50% 50%;
    will-change: transform;
}
</style>

<div class="echomonitor-loading-screen" role="status" aria-label="Loading">
    <div class="echomonitor-loading-spinner" aria-hidden="true"></div>
</div>
"""


@contextmanager
def loading_screen() -> Iterator[None]:
    """Display a centered rotating circular loader while a view is rendered."""
    placeholder = st.empty()

    with placeholder.container():
        st.html(_LOADING_SCREEN_HTML)

    try:
        yield
    finally:
        placeholder.empty()
