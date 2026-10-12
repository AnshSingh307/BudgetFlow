"""Plotly figures inherit Streamlit's active light or dark theme."""

import plotly.graph_objects as go
import plotly.express as px

PALETTE = [
    "#23B5A2",
    "#7B8CF6",
    "#ECAA5B",
    "#E77A88",
    "#62AEE5",
    "#B68CE5",
    "#78C2A4",
    "#EDAE91",
    "#8296AA",
    "#C8B86E",
    "#8CCBD4",
]


def finish(figure, height=300):
    figure.update_layout(
        height=height,
        margin=dict(l=12, r=12, t=12, b=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=-0.22, x=0),
        font=dict(family="sans-serif", size=12),
    )
    figure.update_xaxes(showgrid=False, title=None)
    figure.update_yaxes(
        title=None, gridcolor="rgba(128,128,128,0.12)", zeroline=False
    )
    return figure


def cash_flow(data, currency):
    figure = go.Figure()
    labels = data["period"].dt.strftime("%b %Y")
    for column, label, color in (
        ("income_paise", "Income", PALETTE[0]),
        ("expense_paise", "Expenses", PALETTE[1]),
    ):
        figure.add_bar(
            x=labels,
            y=data[column] / 100,
            name=label,
            marker_color=color,
            hovertemplate=f"%{{x}}<br>{label}: {currency} %{{y:,.2f}}<extra></extra>",
        )
    figure.update_layout(barmode="group", bargap=0.4)
    return finish(figure)


def donut(data, currency, field="category"):
    figure = px.pie(
        data,
        names=field,
        values="amount_paise",
        hole=0.73,
        color_discrete_sequence=PALETTE,
    )
    figure.update_traces(
        textposition="none",
        marker_line_width=0,
        customdata=data["amount_paise"] / 100,
        hovertemplate=f"%{{label}}<br>{currency} %{{customdata:,.2f}} · %{{percent}}<extra></extra>",
    )
    return finish(figure)


def trend(data, currency, column="expense_paise", label="Expenses"):
    figure = go.Figure(
        go.Scatter(
            x=data["period"],
            y=data[column] / 100,
            name=label,
            mode="lines+markers",
            line=dict(
                color=PALETTE[0] if column == "savings_paise" else PALETTE[1],
                width=3,
            ),
            marker=dict(size=5),
            fill="tozeroy",
            fillcolor="rgba(123,140,246,0.08)",
            hovertemplate=f"%{{x|%d %b %Y}}<br>{label}: {currency} %{{y:,.2f}}<extra></extra>",
        )
    )
    return finish(figure, 250)


def categories(data, currency, field="category", label="Expenses"):
    figure = go.Figure(
        go.Bar(
            x=data["amount_paise"] / 100,
            y=data[field],
            orientation="h",
            marker_color=PALETTE[0],
            hovertemplate=f"%{{y}}<br>{label}: {currency} %{{x:,.2f}}<extra></extra>",
        )
    )
    figure.update_yaxes(autorange="reversed")
    return finish(figure, max(250, len(data) * 30))
