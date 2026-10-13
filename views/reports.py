from datetime import date

import streamlit as st

from utils import charts
from utils.calculations import (
    category_summary,
    money,
    period_metrics,
    timeline,
)
from utils.exports import report_pdf, summary_csv, transactions_csv
from utils.ui import currency, db, heading, metrics, plot, transaction_table


def render():
    heading(
        "See the bigger picture.",
        "Find the patterns behind your spending, with reports you can take with you.",
        "",
    )
    today = date.today()
    first, second = st.columns([3, 1])
    dates = first.date_input(
        "Report date range",
        value=(today.replace(day=1), today),
        key="report_dates",
    )
    frequency = second.selectbox(
        "Analysis interval", ["Daily", "Weekly", "Monthly", "Yearly"], index=2
    )
    if len(dates) != 2:
        st.info("Select both dates to build your report.")
        return
    start, end = dates
    if start > end:
        st.error("Start date must be on or before end date.")
        return
    if frequency == "Daily" and (end - start).days > 3660:
        st.warning(
            "Choose a shorter range for daily analysis (up to ten years), or select a larger interval."
        )
        return
    records = db().transactions(start=start, end=end)
    code = currency()
    totals = period_metrics(records)
    metrics(
        [
            (
                "Income",
                money(totals["income"], code),
                "Income within the chosen date range.",
            ),
            (
                "Expenses",
                money(totals["expenses"], code),
                "Expenses within the chosen date range.",
            ),
            (
                "Net savings",
                money(totals["savings"], code),
                "Income minus expenses, not goal contributions.",
            ),
            (
                "Savings rate",
                f"{totals['savings_rate']:.1f}%"
                if totals["savings_rate"] is not None
                else "—",
                "Net savings divided by income; undefined without income.",
            ),
        ]
    )
    if not records:
        st.info(
            "No transactions in this range. Empty CSV and PDF reports are still available below."
        )
    history = timeline(records, start, end, frequency)
    with st.container(border=True):
        st.subheader(f"{frequency} cash flow", anchor=False)
        if frequency == "Monthly":
            plot(charts.cash_flow(history, code), "report_cashflow")
        else:
            import plotly.graph_objects as go

            figure = go.Figure()
            for column, label, color in (
                ("income_paise", "Income", charts.PALETTE[0]),
                ("expense_paise", "Expenses", charts.PALETTE[1]),
            ):
                figure.add_bar(
                    x=history["period"],
                    y=history[column] / 100,
                    name=label,
                    marker_color=color,
                    hovertemplate=f"%{{x|%d %b %Y}}<br>{code} %{{y:,.2f}}<extra>{label}</extra>",
                )
            plot(charts.finish(figure), "report_cashflow")
        if frequency == "Weekly":
            st.caption(
                "Weeks start on Monday. First and last weeks include only dates inside your selected range."
            )
    left, right = st.columns(2)
    categories = category_summary(records)
    with left, st.container(border=True):
        st.subheader("Category comparison", anchor=False)
        if categories.empty:
            st.caption("No expenses recorded.")
        else:
            plot(charts.categories(categories, code), "report_categories")
            top = categories.iloc[0]
            st.caption(
                f"Highest spending: {top['category']} · {money(top['amount_paise'], code)}"
            )
    with right, st.container(border=True):
        st.subheader("Payment methods", anchor=False)
        methods = category_summary(records, field="payment_method")
        if not methods.empty:
            plot(
                charts.donut(methods, code, "payment_method"),
                "report_payments",
            )
        else:
            st.caption("No expenses recorded.")
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader("Expense trend", anchor=False)
        plot(charts.trend(history, code), "report_expenses")
    with right, st.container(border=True):
        st.subheader("Savings trend", anchor=False)
        plot(
            charts.trend(history, code, "savings_paise", "Net savings"),
            "report_savings",
        )
    with st.expander("View report transactions"):
        transaction_table(records, "report_transactions")
    st.subheader("Take your report with you", anchor=False)
    st.caption(
        "Exports contain the actual records in this range. Loaded demo data is labeled as synthetic. Currency selection changes the display label without exchange-rate conversion."
    )
    first, second, third = st.columns(3)
    first.download_button(
        "Transactions CSV",
        data=transactions_csv(records),
        file_name=f"transactions-{start}-{end}.csv",
        mime="text/csv",
        width="stretch",
    )
    second.download_button(
        "Category summary CSV",
        data=summary_csv(records),
        file_name=f"categories-{start}-{end}.csv",
        mime="text/csv",
        width="stretch",
    )
    if third.button("Prepare PDF report", type="primary", width="stretch"):
        with st.spinner("Preparing your financial report..."):
            try:
                st.session_state["report_pdf"] = (
                    (start, end, code, records),
                    report_pdf(records, start, end, code),
                )
            except (ValueError, OSError) as error:
                st.error(f"Could not generate report: {error}")
    prepared = st.session_state.get("report_pdf")
    if prepared and prepared[0] == (start, end, code, records):
        third.download_button(
            "Download PDF",
            data=prepared[1],
            file_name=f"budgetflow-{start}-{end}.pdf",
            mime="application/pdf",
            width="stretch",
        )
