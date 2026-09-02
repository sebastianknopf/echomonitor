"""Reusable dashboard-style metric card component."""

from __future__ import annotations

from typing import Literal

import streamlit as st

MetricCardTone = Literal["default", "error"]

CARD_HEIGHT = 150


def render_metric_card(
    label: str,
    value: str,
    *,
    icon: str,
    key: str,
    caption: str | None = None,
    tone: MetricCardTone = "default",
) -> None:
    """Render a metric card with a Material Design icon."""
    if tone == "error":
        _render_error_card_style(key)

    with st.container(
        border=True,
        height=CARD_HEIGHT,
        vertical_alignment="center",
        key=key,
    ):
        content_column, icon_column = st.columns(
            [4, 1],
            gap="small",
            vertical_alignment="center",
        )

        with content_column:
            st.metric(label, value)
            if caption:
                st.caption(caption)

        with icon_column:
            st.markdown(
                f"### :primary[:material/{icon}:]",
                text_alignment="right",
            )


def _render_error_card_style(key: str) -> None:
    """Apply a restrained pastel-red state to one keyed card."""
    st.html(
        f"""
        <style>
        .st-key-{key} {{
            background: #FDECEC;
            border-color: #E7B1B1 !important;
            border-left: 4px solid #C96B6B !important;
        }}
        </style>
        """
    )
