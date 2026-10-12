"""Shared income and expense workflow: exact forms, filters, selection, and CRUD."""

import streamlit as st

from utils import charts
from utils.calculations import category_summary, money, month_range
from utils.exports import transactions_csv
from utils.ui import (
    action,
    currency,
    db,
    heading,
    metrics,
    month_picker,
    plot,
    transaction_form,
    transaction_table,
)
from utils.validators import EXPENSE_CATEGORIES, INCOME_CATEGORIES, to_paise


def render_transactions(kind):
    expense = kind == "expense"
    title = "Expenses" if expense else "Income"
    code = currency()
    heading(title, "Every entry tells a story. Keep yours up to date.", "")
    add_tab, history_tab, edit_tab = st.tabs(
        [f"Add {kind}", "Transaction history", "Edit & delete"]
    )
    with add_tab:
        left, right = st.columns([3, 2])
        with left:
            st.subheader(f"Record a new {kind}", anchor=False)
            transaction_form(kind)
        with right, st.container(border=True):
            st.subheader("Keep it simple", anchor=False)
            st.write(
                "Choose a date and category, enter an amount, and add a short note for your future self."
            )
            st.caption(
                "Amounts accept up to two decimal places and are stored exactly as integer paise."
            )
            st.caption("Tip: CSV import is available in Settings & data.")
    with history_tab:
        month = month_picker(kind)
        start, end = month_range(month)
        if st.session_state.get(kind + "_last_month") != month:
            st.session_state[kind + "_range"] = (start, end)
            st.session_state[kind + "_last_month"] = month
        with st.expander("Search & filters", expanded=True):
            left, right = st.columns(2)
            dates = left.date_input(
                "Date range", value=(start, end), key=kind + "_range"
            )
            search = right.text_input(
                "Search descriptions or categories", key=kind + "_search"
            )
            categories = left.multiselect(
                "Categories",
                EXPENSE_CATEGORIES if expense else INCOME_CATEGORIES,
                placeholder="All categories",
                key=kind + "_filters",
            )
            sort = right.selectbox(
                "Sort by",
                [
                    "Newest first",
                    "Oldest first",
                    "Highest amount",
                    "Lowest amount",
                    "Category",
                ],
                key=kind + "_sort",
            )
            minimum = left.text_input(
                "Minimum amount", value="0", key=kind + "_min"
            )
            maximum = right.text_input(
                "Maximum amount (optional)", key=kind + "_max"
            )
        if len(dates) != 2:
            st.info("Choose both the start and end date.")
            return
        try:
            low = to_paise(minimum or "0", allow_zero=True)
            high = (
                to_paise(maximum, allow_zero=True) if maximum.strip() else None
            )
            if high is not None and low > high:
                raise ValueError(
                    "Minimum amount cannot exceed maximum amount."
                )
            records = db().transactions(
                kind=kind, start=dates[0], end=dates[1]
            )
        except ValueError as error:
            st.error(str(error))
            return
        records = [
            row
            for row in records
            if (not categories or row["category"] in categories)
            and low <= row["amount_paise"]
            and (high is None or row["amount_paise"] <= high)
            and (
                not search
                or search.casefold()
                in (row["description"] + " " + row["category"]).casefold()
            )
        ]
        sort_fields = {
            "Newest first": ("transaction_date", True),
            "Oldest first": ("transaction_date", False),
            "Highest amount": ("amount_paise", True),
            "Lowest amount": ("amount_paise", False),
            "Category": ("category", False),
        }
        field, reverse = sort_fields[sort]
        records.sort(key=lambda row: (row[field], row["id"]), reverse=reverse)
        metrics(
            [
                (
                    f"Filtered {title.lower()}",
                    money(
                        sum(row["amount_paise"] for row in records), currency()
                    ),
                    "Sum of the visible records.",
                ),
                (
                    "Transactions",
                    str(len(records)),
                    "Number of records matching all filters.",
                ),
            ]
        )
        st.caption(
            "Select a row to use it in Edit & delete. Column headings also support sorting."
        )
        selected = transaction_table(records, kind + "_table", select=True)
        if selected and selected != st.session_state.get(kind + "_selected"):
            st.session_state[kind + "_selected"] = selected
            st.session_state[kind + "_edit_choice"] = selected
        st.download_button(
            "Download filtered CSV",
            data=transactions_csv(records),
            file_name=f"{kind}-{month}.csv",
            mime="text/csv",
            icon=":material/download:",
        )
        source = category_summary(records, kind=kind)
        if not source.empty:
            with st.container(border=True):
                st.subheader(
                    "Spending by category" if expense else "Income by source",
                    anchor=False,
                )
                plot(
                    charts.categories(source, currency(), label=title),
                    kind + "_sources",
                )
    with edit_tab:
        all_records = db().transactions(kind=kind)
        if not all_records:
            st.info(f"Add a {kind} before editing records.")
            return
        lookup = {row["id"]: row for row in all_records}
        selected_id = st.session_state.get(kind + "_selected")
        ids = list(lookup)
        index = ids.index(selected_id) if selected_id in lookup else 0
        labels = {
            value: f"#{value} · {row['transaction_date']} · {row['category']} · {money(row['amount_paise'], code)}"
            for value, row in lookup.items()
        }
        chosen = st.selectbox(
            "Choose a transaction",
            ids,
            index=index,
            format_func=lambda value: labels.get(value, f"#{value}"),
            key=kind + "_edit_choice",
        )
        transaction_form(kind, lookup[chosen])
        with st.expander("Delete this transaction"):
            confirmed = st.checkbox(
                "I confirm deletion of this transaction.",
                key=f"{kind}_delete_confirm_{chosen}",
            )
            if st.button(
                "Delete transaction",
                disabled=not confirmed,
                type="secondary",
                key=kind + "_delete",
            ):
                action(
                    lambda: db().delete_transaction(chosen),
                    "Transaction deleted.",
                )
