"""BudgetFlow entry point: run with `streamlit run app.py`."""

import sqlite3
from pathlib import Path

import streamlit as st

from database import Database
from views import (
    budgets,
    dashboard,
    expenses,
    income,
    reports,
    savings,
    settings,
)

st.set_page_config(
    page_title="BudgetFlow · Personal finance", page_icon="💸", layout="wide"
)

try:
    st.session_state["database"] = Database()
except (sqlite3.Error, OSError) as error:
    st.error(f"BudgetFlow could not open its local database: {error}")
    st.stop()

st.logo(str(Path(__file__).parent / "assets" / "logo.svg"), size="large")
expense_page = st.Page(
    expenses.render,
    title="Expenses",
    icon=":material/payments:",
    url_path="expenses",
)
income_page = st.Page(
    income.render,
    title="Income",
    icon=":material/account_balance_wallet:",
    url_path="income",
)
st.session_state["expense_page"] = expense_page
st.session_state["income_page"] = income_page
budget_page = st.Page(
    budgets.render,
    title="Budget planner",
    icon=":material/donut_small:",
    url_path="budgets",
)
st.session_state["budget_page"] = budget_page
navigation = st.navigation(
    {
        "YOUR FINANCES": [
            st.Page(
                dashboard.render,
                title="Overview",
                icon=":material/dashboard:",
                default=True,
            ),
            expense_page,
            income_page,
        ],
        "PLAN & GROW": [
            budget_page,
            st.Page(
                savings.render,
                title="Savings goals",
                icon=":material/flag:",
                url_path="savings",
            ),
            st.Page(
                reports.render,
                title="Reports & analytics",
                icon=":material/monitoring:",
                url_path="reports",
            ),
        ],
        "WORKSPACE": [
            st.Page(
                settings.render,
                title="Settings & data",
                icon=":material/tune:",
                url_path="settings",
            ),
        ],
    }
)

with st.sidebar:
    st.divider()
    st.caption("PERSONAL BUDGET & EXPENSE TRACKER")
    st.caption("A little clarity. A better tomorrow.")
    st.caption("Appearance: ⋮ → Light / Dark")
    st.badge(
        "Stored locally · SQLite", icon=":material/storage:", color="green"
    )

if "notification" in st.session_state:
    st.toast(
        st.session_state.pop("notification"), icon=":material/check_circle:"
    )
demo = st.session_state["database"].demo_counts()
if any(demo.values()):
    st.info(
        "Demo records are loaded. Synthetic entries are marked Demo in tables and exports. Manage them in Settings & data.",
        icon=":material/science:",
    )

navigation.run()
