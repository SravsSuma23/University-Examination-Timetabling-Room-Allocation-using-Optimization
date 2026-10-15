"""
visualization.py
================
High-impact, interactive Plotly visualization components for ExamOpt.
Uses professional dark-mode aligned color palettes and clear annotations.
"""

from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go


# Theme palette
PALETTE = {
    "primary": "#0D9488",     # Teal accent
    "primary_dark": "#115E59",
    "secondary": "#6366F1",   # Indigo
    "accent": "#F59E0B",      # Amber
    "danger": "#EF4444",      # Red
    "success": "#10B981",     # Emerald
    "bg_dark": "#0F172A",     # Slate dark
    "card_dark": "#1E293B",
    "text": "#F8FAFC",
    "text_muted": "#94A3B8",
}


def plot_exams_per_period(timetable_df: pd.DataFrame) -> go.Figure:
    """Bar chart of exams scheduled per period, colored by period penalty."""
    counts = timetable_df.groupby("period_id").agg({
        "exam_id": "count",
        "period_penalty": "first",
        "day": "first",
        "time": "first",
    }).reset_index()

    counts.rename(columns={"exam_id": "exam_count"}, inplace=True)
    counts["Period Label"] = counts.apply(lambda r: f"P{r['period_id']} ({r['day']})", axis=1)

    # Color map based on penalty
    color_map = {0: "#0D9488", 1: "#F59E0B", 4: "#EF4444"}
    colors = [color_map.get(p, "#6366F1") for p in counts["period_penalty"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=counts["period_id"],
        y=counts["exam_count"],
        marker_color=colors,
        text=counts["exam_count"],
        textposition="outside",
        customdata=np.stack((counts["day"], counts["time"], counts["period_penalty"]), axis=-1),
        hovertemplate=(
            "<b>Period %{x}</b><br>"
            "Exams: %{y}<br>"
            "Day: %{customdata[0]}<br>"
            "Time: %{customdata[1]}<br>"
            "Penalty: %{customdata[2]}<extra></extra>"
        ),
    ))

    fig.update_layout(
        title="<b>Examination Load Distribution Across Periods</b> (Colored by Period Penalty)",
        xaxis=dict(title="Examination Period (1 to 29)", tickmode="linear", dtick=1),
        yaxis=dict(title="Number of Scheduled Exams"),
        template="plotly_dark",
        margin=dict(l=40, r=40, t=60, b=40),
        height=380,
    )
    return fig


def plot_students_per_period(timetable_df: pd.DataFrame) -> go.Figure:
    """Campus student load per period across the examination schedule."""
    stud_counts = timetable_df.groupby("period_id").agg({
        "students": "sum",
        "day": "first",
        "time": "first",
    }).reset_index()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=stud_counts["period_id"],
        y=stud_counts["students"],
        mode="lines+markers",
        line=dict(color="#6366F1", width=3),
        marker=dict(size=8, color="#0D9488"),
        fill="tozeroy",
        fillcolor="rgba(99, 102, 241, 0.15)",
        customdata=np.stack((stud_counts["day"], stud_counts["time"]), axis=-1),
        hovertemplate=(
            "<b>Period %{x}</b> (%{customdata[0]})<br>"
            "Active Students: %{y:,}<br>"
            "Slot: %{customdata[1]}<extra></extra>"
        ),
    ))

    fig.update_layout(
        title="<b>Total Concurrent Campus Students per Examination Period</b>",
        xaxis=dict(title="Period (1 to 29)", tickmode="linear", dtick=1),
        yaxis=dict(title="Active Students Seated"),
        template="plotly_dark",
        margin=dict(l=40, r=40, t=60, b=40),
        height=360,
    )
    return fig


def plot_exam_size_distribution(exams_df: pd.DataFrame) -> go.Figure:
    """Histogram of student enrollments per exam."""
    col = "number_of_students" if "number_of_students" in exams_df.columns else "average_students"
    sizes = exams_df[col]

    fig = px.histogram(
        exams_df,
        x=col,
        nbins=50,
        title="<b>Distribution of Exam Enrollments (Purdue Fall 2008)</b>",
        labels={col: "Number of Students Registered"},
        color_discrete_sequence=["#0D9488"],
        template="plotly_dark",
    )

    # Highlight threshold for large exams
    fig.add_vline(
        x=600,
        line_dash="dash",
        line_color="#EF4444",
        annotation_text="Large Exam Threshold (≥600)",
        annotation_position="top right",
    )

    fig.update_layout(
        margin=dict(l=40, r=40, t=60, b=40),
        height=360,
    )
    return fig


def plot_room_capacity_distribution(rooms_df: pd.DataFrame) -> go.Figure:
    """Room capacity distribution."""
    fig = px.histogram(
        rooms_df,
        x="capacity",
        nbins=40,
        title="<b>Room Seating Capacity Distribution</b>",
        labels={"capacity": "Room Capacity (Seats)"},
        color_discrete_sequence=["#6366F1"],
        template="plotly_dark",
    )
    fig.update_layout(
        margin=dict(l=40, r=40, t=60, b=40),
        height=360,
    )
    return fig


def plot_conflict_degree_distribution(degrees: List[int]) -> go.Figure:
    """Distribution of conflict degrees across all examinations."""
    fig = px.histogram(
        x=degrees,
        nbins=40,
        title="<b>Exam Conflict Degree Distribution (Number of Co-Enrolled Exams)</b>",
        labels={"x": "Conflict Degree (Degree of Node)"},
        color_discrete_sequence=["#F59E0B"],
        template="plotly_dark",
    )
    fig.update_layout(
        margin=dict(l=40, r=40, t=60, b=40),
        height=360,
    )
    return fig


def plot_room_utilization_gauge(utilization_pct: float) -> go.Figure:
    """Gauge indicator for overall room capacity utilization."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=utilization_pct,
        number={"suffix": "%", "valueformat": ".1f"},
        title={"text": "<b>Overall Room Capacity Utilization</b>"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#0D9488"},
            "steps": [
                {"range": [0, 50], "color": "rgba(239, 68, 68, 0.3)"},
                {"range": [50, 75], "color": "rgba(245, 158, 11, 0.3)"},
                {"range": [75, 100], "color": "rgba(16, 185, 129, 0.3)"},
            ],
            "threshold": {
                "line": {"color": "white", "width": 3},
                "thickness": 0.75,
                "value": utilization_pct,
            },
        },
    ))
    fig.update_layout(
        template="plotly_dark",
        margin=dict(l=30, r=30, t=60, b=30),
        height=280,
    )
    return fig


def plot_goal_tradeoff_scenarios(scenario_df: pd.DataFrame) -> go.Figure:
    """Grouped bar chart comparing different Goal Programming weight trade-offs."""
    fig = go.Figure()

    # Safely get series with fallbacks in case of old session state
    unused = scenario_df["Unused Capacity"] if "Unused Capacity" in scenario_df.columns else 0
    penalty = scenario_df["Room Penalty"] if "Room Penalty" in scenario_df.columns else 0
    splits = scenario_df["Room Splits"] if "Room Splits" in scenario_df.columns else (scenario_df["Splits"] if "Splits" in scenario_df.columns else 0)

    fig.add_trace(go.Bar(
        name="Unused Capacity (Seats)",
        x=scenario_df["Scenario"],
        y=unused,
        marker_color="#6366F1",
    ))

    fig.add_trace(go.Bar(
        name="Room Penalties",
        x=scenario_df["Scenario"],
        y=penalty,
        marker_color="#F59E0B",
    ))

    fig.add_trace(go.Bar(
        name="Room Splits",
        x=scenario_df["Scenario"],
        y=splits,
        marker_color="#EF4444",
    ))

    fig.update_layout(
        title="<b>Multi-Objective Goal Programming Trade-off Comparison</b>",
        barmode="group",
        xaxis_title="Weight Configuration Scenario",
        yaxis_title="Metric Value",
        template="plotly_dark",
        margin=dict(l=40, r=40, t=60, b=40),
        height=400,
    )
    return fig
