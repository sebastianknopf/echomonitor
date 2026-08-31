"""Reusable chart rendering helpers."""

from __future__ import annotations

import altair as alt
import streamlit as st


def render_scrollable_x_chart(
    chart: alt.Chart,
    *,
    minimum_category_width: int = 24,
) -> None:
    """Render a categorical X-axis chart with horizontal overflow."""
    if minimum_category_width <= 0:
        raise ValueError("minimum_category_width must be greater than zero.")

    chart_with_minimum_width = chart.properties(
        width=alt.Step(minimum_category_width),
    )

    with st.container(horizontal=True, wrap=False):
        st.altair_chart(
            chart_with_minimum_width,
            width="content",
        )
