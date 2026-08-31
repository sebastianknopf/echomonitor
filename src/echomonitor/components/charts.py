"""Reusable chart rendering helpers."""

from __future__ import annotations

import altair as alt
import streamlit as st


def render_scrollable_x_chart(
    chart: alt.Chart,
    *,
    category_count: int,
    minimum_category_width: int = 24,
    key: str,
) -> None:
    """Render a full-width categorical chart with horizontal overflow."""
    if category_count <= 0:
        raise ValueError("category_count must be greater than zero.")
    if minimum_category_width <= 0:
        raise ValueError("minimum_category_width must be greater than zero.")

    minimum_chart_width = category_count * minimum_category_width
    responsive_chart = chart.properties(width="container")

    st.html(
        f"""
        <style>
        .st-key-{key} {{
            min-width: max(100%, {minimum_chart_width}px);
            flex: 0 0 auto;
        }}
        </style>
        """
    )

    with st.container(horizontal=True, wrap=False):
        with st.container(key=key):
            st.altair_chart(
                responsive_chart,
                width="stretch",
            )
