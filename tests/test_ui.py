"""Real Streamlit script execution and form interactions, with disposable storage."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from database import Database

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def app_environment(monkeypatch, tmp_path):
    path = tmp_path / "ui.db"
    monkeypatch.setenv("BUDGETFLOW_DB", str(path))
    return path


def page_app(page, path):
    script = f"""
import streamlit as st
from database import Database
from pages import {page}
st.session_state['database'] = Database({str(path)!r})
{page}.render()
"""
    return AppTest.from_string(script, default_timeout=15).run()


def test_dashboard_empty_and_demo(app_environment):
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    assert not app.exception
    assert len(app.metric) == 7
    assert app.metric[0].value == "₹0.00"
    Database(app_environment).load_demo()
    app.run()
    assert not app.exception
    assert app.metric[0].value != "₹0.00"


@pytest.mark.parametrize(
    "page", ["expenses", "income", "budgets", "savings", "reports", "settings"]
)
def test_each_page_empty_and_demo(page, app_environment):
    app = page_app(page, app_environment)
    assert not app.exception
    Database(app_environment).load_demo()
    app.run()
    assert not app.exception


@pytest.mark.parametrize(
    "page,kind", [("income", "income"), ("expenses", "expense")]
)
def test_add_edit_delete_form_workflow(page, kind, app_environment):
    app = page_app(page, app_environment)
    app.text_input(key=f"{kind}_new_amount").set_value("1234.56")
    app.button[0].click().run()
    assert not app.exception
    database = Database(app_environment)
    row = database.transactions()[0]
    assert row["amount_paise"] == 123456
    app.text_input(key=f"{kind}_{row['id']}_amount").set_value("1000.01")
    next(
        button for button in app.button if button.label == "Save changes"
    ).click().run()
    assert not app.exception
    assert database.transactions()[0]["amount_paise"] == 100001
    app.checkbox(key=f"{kind}_delete_confirm_{row['id']}").check().run()
    app.button(key=f"{kind}_delete").click().run()
    assert not app.exception
    assert database.transactions() == []


def test_invalid_amount_and_month_change(app_environment):
    app = page_app("expenses", app_environment)
    app.text_input(key="expense_new_amount").set_value("1.001")
    app.button[0].click().run()
    assert app.error
    assert Database(app_environment).transactions() == []
    app.selectbox(key="expense_month").set_value(2).run()
    assert not app.exception
    assert app.date_input(key="expense_range").value[0].month == 2


def test_budget_and_goal_forms(app_environment):
    app = page_app("budgets", app_environment)
    app.text_input[0].set_value("10000")
    app.text_input[1].set_value("2000")
    app.button[0].click().run()
    assert not app.exception
    database = Database(app_environment)
    assert (
        len(
            database.budgets(
                __import__("datetime").date.today().strftime("%Y-%m")
            )
        )
        == 2
    )
    app = page_app("savings", app_environment)
    app.text_input[0].set_value("Laptop")
    app.text_input[1].set_value("60000")
    app.button[0].click().run()
    assert not app.exception
    goal = database.goals()[0]
    app.text_input(key=f"contribution_amount_{goal['id']}").set_value("5000")
    next(
        button for button in app.button if button.label == "Add contribution"
    ).click().run()
    assert not app.exception
    assert database.goals()[0]["saved_paise"] == 500000


def test_report_pdf_button(app_environment):
    app = page_app("reports", app_environment)
    next(
        button for button in app.button if button.label == "Prepare PDF report"
    ).click().run()
    assert not app.exception
    assert app.session_state["report_pdf"][1].startswith(b"%PDF-")
