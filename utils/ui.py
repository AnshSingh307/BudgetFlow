"""Shared Streamlit components, intentionally without internal CSS selectors."""

import calendar
import sqlite3
from datetime import date

import pandas as pd
import streamlit as st

from utils.calculations import amount_text
from utils.validators import (
    CURRENCIES,
    EXPENSE_CATEGORIES,
    INCOME_CATEGORIES,
    PAYMENT_METHODS,
    to_paise,
)


def db():
    return st.session_state["database"]


def currency():
    return db().setting("currency") or "INR"


def heading(title, subtitle, icon):
    st.caption(f"BUDGETFLOW  /  {title.upper()}")
    st.title(title, anchor=False)
    st.caption(subtitle)
    st.divider()


def month_picker(key):
    today = date.today()
    transaction_years = [
        int(row["transaction_date"][:4]) for row in db().transactions()
    ]
    years = sorted(
        set(range(today.year - 5, today.year + 6)) | set(transaction_years)
    )
    first, second = st.columns(2)
    month = first.selectbox(
        "Month",
        range(1, 13),
        index=today.month - 1,
        format_func=lambda value: calendar.month_name[value],
        key=key + "_month",
    )
    year = second.selectbox(
        "Year", years, index=years.index(today.year), key=key + "_year"
    )
    return f"{year:04d}-{month:02d}"


def metrics(items):
    columns = st.columns(len(items))
    for column, (label, value, help_text) in zip(columns, items):
        column.metric(label, value, border=True, help=help_text)


def plot(figure, key):
    st.plotly_chart(
        figure,
        width="stretch",
        theme="streamlit",
        key=key,
        config={"displaylogo": False, "scrollZoom": False},
    )


def transaction_table(records, key="transactions", *, select=False):
    data = pd.DataFrame(
        [
            {
                "ID": row["id"],
                "Date": date.fromisoformat(row["transaction_date"]),
                "Type": row["kind"].title(),
                "Category": row["category"],
                "Amount": row["amount_paise"] / 100,
                "Description": row["description"],
                "Payment": row["payment_method"],
                "Source": "Demo" if row.get("is_demo") else "Personal",
            }
            for row in records
        ]
    )
    if data.empty:
        st.info(
            "No transactions match this view. Add a record or adjust your filters.",
            icon=":material/receipt_long:",
        )
        return None
    options = (
        {"on_select": "rerun", "selection_mode": "single-row"}
        if select
        else {}
    )
    event = st.dataframe(
        data,
        width="stretch",
        hide_index=True,
        key=key,
        column_config={
            "Date": st.column_config.DateColumn(format="DD MMM YYYY"),
            "Amount": st.column_config.NumberColumn(
                format=CURRENCIES[currency()] + "%.2f"
            ),
        },
        **options,
    )
    return (
        records[event.selection.rows[0]]["id"]
        if select and event.selection.rows
        else None
    )


def action(callback, message):
    try:
        callback()
    except (ValueError, sqlite3.Error, OSError) as error:
        st.error(str(error))
        return False
    st.session_state["notification"] = message
    st.rerun()


def transaction_form(kind, record=None):
    """One form supports both record types and add/edit modes."""
    record = record or {}
    editing = "id" in record
    categories = EXPENSE_CATEGORIES if kind == "expense" else INCOME_CATEGORIES
    key = f"{kind}_{record.get('id', 'new')}"
    with st.form("transaction_form_" + key, clear_on_submit=not editing):
        left, right = st.columns(2)
        transaction_date = left.date_input(
            "Transaction date",
            value=date.fromisoformat(record["transaction_date"])
            if editing
            else date.today(),
            key=key + "_date",
        )
        amount = right.text_input(
            f"Amount ({currency()})",
            value=amount_text(record["amount_paise"]) if editing else "",
            placeholder="e.g. 1250.50",
            key=key + "_amount",
        )
        category = left.selectbox(
            "Category",
            categories,
            index=categories.index(record["category"]) if editing else 0,
            key=key + "_category",
        )
        method = right.selectbox(
            "Payment method",
            PAYMENT_METHODS,
            index=PAYMENT_METHODS.index(record["payment_method"])
            if editing
            else PAYMENT_METHODS.index(
                "Bank Transfer" if kind == "income" else "UPI"
            ),
            key=key + "_payment",
        )
        description = st.text_area(
            "Description",
            value=record.get("description", ""),
            max_chars=500,
            placeholder="What was this transaction for?",
            key=key + "_description",
        )
        if st.form_submit_button(
            "Save changes" if editing else f"Add {kind}",
            type="primary",
            width="stretch",
        ):

            def save():
                values = dict(
                    kind=kind,
                    amount_paise=to_paise(amount),
                    category=category,
                    transaction_date=transaction_date,
                    description=description,
                    payment_method=method,
                )
                if editing:
                    db().update_transaction(record["id"], **values)
                else:
                    db().add_transaction(**values)

            action(
                save,
                "Transaction updated."
                if editing
                else f"{kind.title()} added.",
            )
