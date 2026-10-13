import streamlit as st

from utils.calculations import (
    amount_text,
    budget_status,
    category_summary,
    money,
    month_range,
    period_metrics,
)
from utils.ui import action, currency, db, heading, metrics, month_picker
from utils.validators import EXPENSE_CATEGORIES, to_paise


def render():
    heading(
        "Give every rupee a purpose.",
        "Set a plan. See your progress. Adjust as life changes.",
        "",
    )
    month = month_picker("budgets")
    start, end = month_range(month)
    records = db().transactions(start=start, end=end)
    spending = period_metrics(records)["expenses"]
    budget_rows = db().budgets(month)
    limits = {row["category"]: row["amount_paise"] for row in budget_rows}
    total = limits.get("Overall")
    state = budget_status(spending, total)
    code = currency()
    metrics(
        [
            (
                "Monthly limit",
                money(total, code) if total else "Not set",
                "Overall budget for the selected month.",
            ),
            (
                "Spent so far",
                money(spending, code),
                "All recorded expenses for this calendar month.",
            ),
            (
                "Remaining",
                money(state["remaining"], code) if total else "—",
                "A negative value means the overall budget is exceeded.",
            ),
        ]
    )
    if total:
        st.badge(state["label"], color=state["color"])
        st.progress(
            state["progress"],
            text=f"{state['percent']:.1f}% of monthly budget used",
        )
        if state["percent"] >= 100:
            st.error(
                "Your expenses have reached or exceeded the overall spending limit."
            )
        elif state["percent"] >= 75:
            st.warning("You are approaching your monthly spending limit.")
    plan_tab, progress_tab = st.tabs(["Plan your budget", "Category progress"])
    with plan_tab:
        st.caption(
            "Allocations are parts of the overall limit. Set a category to 0 to leave it without a limit. Unallocated money remains flexible."
        )
        with st.form("budget_plan_" + month):
            overall = st.text_input(
                f"Overall monthly limit ({code})",
                value=amount_text(total) if total else "",
                placeholder="e.g. 30000.00",
            )
            columns = st.columns(3)
            allocations = {}
            for index, category in enumerate(EXPENSE_CATEGORIES):
                allocations[category] = columns[index % 3].text_input(
                    category,
                    value=amount_text(limits.get(category, 0)),
                    key=f"allocation_{month}_{category}",
                )
            if st.form_submit_button("Save budget plan", type="primary"):

                def save():
                    db().save_budget_plan(
                        month,
                        to_paise(overall),
                        {
                            category: to_paise(amount or "0", allow_zero=True)
                            for category, amount in allocations.items()
                        },
                    )

                action(save, "Budget plan saved.")
        if total:
            allocated = sum(
                amount
                for category, amount in limits.items()
                if category != "Overall"
            )
            st.caption(
                f"Category allocations: {money(allocated, code)} · Flexible: {money(total - allocated, code)}"
            )
            with st.expander("Remove this month's plan"):
                confirmed = st.checkbox(
                    "Remove overall and category budgets for this month.",
                    key="budget_confirm_" + month,
                )
                if st.button("Remove budget plan", disabled=not confirmed):
                    action(
                        lambda: db().delete_budget_plan(month),
                        "Budget plan removed.",
                    )
    with progress_tab:
        summary = (
            category_summary(records)
            .set_index("category")["amount_paise"]
            .to_dict()
        )
        for category in EXPENSE_CATEGORIES:
            used = int(summary.get(category, 0))
            limit = limits.get(category)
            status = budget_status(used, limit)
            with st.container(border=True):
                left, right = st.columns([3, 1])
                left.markdown(f"**{category}**")
                right.badge(status["label"], color=status["color"])
                if limit:
                    st.progress(
                        status["progress"],
                        text=f"{money(used, code)} / {money(limit, code)} · {status['percent']:.1f}%",
                    )
                    st.caption(
                        f"Remaining: {money(status['remaining'], code)}"
                    )
                    if status["percent"] >= 75:
                        st.markdown(
                            f":{status['color']}[{status['label']} · {category}]"
                        )
                else:
                    st.caption(
                        f"Spent {money(used, code)} · No category limit set"
                    )
        st.caption(
            "Status thresholds: below 75% Within Budget; 75% to under 100% Approaching Limit; 100% or above Budget Exceeded."
        )
