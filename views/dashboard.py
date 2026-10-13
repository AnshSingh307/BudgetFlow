from datetime import date

import streamlit as st

from utils import charts
from utils.calculations import (
    budget_status,
    category_summary,
    insights,
    money,
    month_range,
    period_metrics,
    previous_month,
    timeline,
)
from utils.ui import (
    currency,
    db,
    heading,
    metrics,
    month_picker,
    plot,
    transaction_table,
)


def render():
    heading(
        "Your money, in focus.",
        "Understand today. Plan for what comes next.",
        "",
    )
    salary_action, expense_action = st.columns(2)
    salary_action.page_link(
        st.session_state["income_page"],
        label="Add salary or income",
        icon=":material/account_balance_wallet:",
        width="stretch",
    )
    expense_action.page_link(
        st.session_state["expense_page"],
        label="Add an expense",
        icon=":material/payments:",
        width="stretch",
    )
    month = month_picker("dashboard")
    start, end = month_range(month)
    code = currency()
    records = db().transactions(start=start, end=end)
    totals = period_metrics(records)
    balance = period_metrics(db().transactions(end=end))["savings"]
    budgets = db().budgets(month)
    limit = next(
        (
            row["amount_paise"]
            for row in budgets
            if row["category"] == "Overall"
        ),
        None,
    )
    state = budget_status(totals["expenses"], limit)
    metrics(
        [
            (
                "Total income",
                money(totals["income"], code),
                "Income in the selected month.",
            ),
            (
                "Total expenses",
                money(totals["expenses"], code),
                "Expenses in the selected month.",
            ),
            (
                "Remaining balance",
                money(balance, code),
                "All recorded income minus expenses through this month's end. No opening balance is assumed.",
            ),
            (
                "Savings rate",
                f"{totals['savings_rate']:.1f}%"
                if totals["savings_rate"] is not None
                else "—",
                "Monthly net savings / monthly income × 100. Unavailable when income is zero.",
            ),
        ]
    )
    metrics(
        [
            (
                "Monthly budget",
                money(limit, code) if limit else "Not set",
                "The overall spending limit, separate from category allocations.",
            ),
            (
                "Remaining budget",
                money(state["remaining"], code) if limit else "—",
                "Overall limit minus expenses. Negative means overspent.",
            ),
            (
                "Total savings · month",
                money(totals["savings"], code),
                "Income minus expenses in this month. Can be negative. Goal contributions do not change this calculation.",
            ),
        ]
    )
    if not records:
        st.info(
            "This month is a fresh start. Add your first income or expense, or load clearly labeled sample data in Settings & data."
        )

    with st.container(border=True):
        left, right = st.columns([3, 1])
        left.subheader("Monthly spending", anchor=False)
        if limit:
            right.badge(state["label"], color=state["color"])
            st.progress(
                state["progress"],
                text=f"{money(totals['expenses'], code)} of {money(limit, code)} · {state['percent']:.1f}% used",
            )
        else:
            st.caption(
                "Set an overall budget to see how much room you have left."
            )
        st.page_link(
            st.session_state["budget_page"],
            label="Open budget planner",
            icon=":material/arrow_forward:",
        )

    # Six calendar months ending with the selected month.
    ordinal = start.year * 12 + start.month - 1 - 5
    year, number = divmod(ordinal, 12)
    first_month = date(year, number + 1, 1)
    history = timeline(
        db().transactions(start=first_month, end=end), first_month, end
    )
    left, right = st.columns([3, 2])
    with left, st.container(border=True):
        st.subheader("Income vs. expenses", anchor=False)
        st.caption("Six-month cash flow")
        plot(charts.cash_flow(history, code), "dashboard_cashflow")
    with right, st.container(border=True):
        st.subheader("Where your money goes", anchor=False)
        category_data = category_summary(records)
        if category_data.empty:
            st.info("Your spending mix appears after your first expense.")
        else:
            plot(charts.donut(category_data, code), "dashboard_categories")
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader("Daily expense trend", anchor=False)
        plot(
            charts.trend(timeline(records, start, end, "Daily"), code),
            "dashboard_daily",
        )
    with right, st.container(border=True):
        st.subheader("Savings over time", anchor=False)
        st.caption("Net income minus expenses in each month")
        plot(
            charts.trend(history, code, "savings_paise", "Net savings"),
            "dashboard_savings",
        )
    left, right = st.columns([3, 2])
    with left, st.container(border=True):
        st.subheader("Recent transactions", anchor=False)
        st.caption("Five latest entries in the selected month")
        transaction_table(records[:5], "dashboard_recent")
    with right, st.container(border=True):
        st.subheader("Financial insights", anchor=False)
        prior_start, prior_end = month_range(previous_month(month))
        prior = db().transactions(start=prior_start, end=prior_end)
        for message in insights(records, prior, budgets, code):
            st.write("• " + message)
        st.caption(
            "Rule-based calculations. Comparisons use full recorded calendar months; an ongoing month may be incomplete."
        )
