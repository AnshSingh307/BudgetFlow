from datetime import date

import pytest

from database import Database
from utils.calculations import period_metrics


def test_income_expense_crud_and_restart(database):
    income = database.add_transaction(
        "income",
        100000,
        "Salary",
        "2026-10-01",
        "Monthly salary",
        "Bank Transfer",
    )
    expense = database.add_transaction(
        "expense", 12345, "Food", "2026-10-12", "Lunch"
    )
    assert period_metrics(database.transactions())["savings"] == 87655
    database.update_transaction(
        expense,
        "expense",
        12000,
        "Transportation",
        "2026-10-13",
        "Bus",
        "Cash",
    )
    reopened = Database(database.path)
    assert reopened.transactions(kind="expense")[0]["amount_paise"] == 12000
    assert (
        reopened.transactions(kind="expense")[0]["category"]
        == "Transportation"
    )
    assert period_metrics(reopened.transactions())["savings"] == 88000
    reopened.delete_transaction(income)
    assert len(database.transactions()) == 1
    reopened.delete_transaction(expense)
    assert database.transactions() == []


def test_month_filters_boundaries(database):
    for when in ("2026-09-30", "2026-10-01", "2026-10-31", "2026-11-01"):
        database.add_transaction("expense", 100, "Food", when)
    assert (
        len(database.transactions(start="2026-10-01", end="2026-10-31")) == 2
    )
    assert len(database.transactions(end="2026-10-31")) == 3
    with pytest.raises(ValueError):
        database.transactions(start="2026-11-01", end="2026-10-01")


@pytest.mark.parametrize(
    "amount,category,when",
    [
        (1.5, "Food", "2026-10-01"),
        (True, "Food", "2026-10-01"),
        (-1, "Food", "2026-10-01"),
        (100, "Salary", "2026-10-01"),
        (100, "Food", "2026-02-30"),
    ],
)
def test_database_validates_inputs(database, amount, category, when):
    with pytest.raises(ValueError):
        database.add_transaction("expense", amount, category, when)
    assert database.transactions() == []


def test_parameterized_queries_store_literal_text(database):
    description = "Robert'); DROP TABLE transactions;--"
    database.add_transaction("expense", 100, "Food", "2026-10-12", description)
    assert database.transactions()[0]["description"] == description
    assert len(database.transactions()) == 1


def test_atomic_import_rejects_partial_changes(database):
    valid = dict(
        kind="income",
        amount_paise=100,
        category="Gifts",
        transaction_date="2026-10-12",
    )
    invalid = {**valid, "amount_paise": 0}
    with pytest.raises(ValueError):
        database.import_transactions([valid, invalid])
    assert database.transactions() == []
    assert database.import_transactions([valid, valid]) == 2


def test_budget_edit_validation_and_atomicity(database):
    database.save_budget_plan(
        "2026-10", 100000, {"Food": 25000, "Shopping": 0}
    )
    with pytest.raises(ValueError):
        database.save_budget_plan("2026-10", 100000, {"Food": 150000})
    assert {
        row["category"]: row["amount_paise"]
        for row in database.budgets("2026-10")
    } == {"Food": 25000, "Overall": 100000}
    database.save_budget_plan("2026-10", 200000, {"Education": 100000})
    assert len(database.budgets("2026-10")) == 2
    database.delete_budget_plan("2026-10")
    assert database.budgets("2026-10") == []


def test_goals_contributions_completion_and_cascade(database):
    goal = database.add_goal("Laptop", 100000, "2027-01-01")
    with pytest.raises(ValueError):
        database.complete_goal(goal)
    contribution = database.add_contribution(
        goal, 50000, "2026-10-12", "First half"
    )
    assert database.goals()[0]["saved_paise"] == 50000
    assert database.transactions() == []
    database.update_goal(goal, "New laptop", 100000, "2027-02-01")
    database.add_contribution(goal, 50000, "2026-10-13")
    database.complete_goal(goal)
    assert database.goals()[0]["completed"] == 1
    with pytest.raises(ValueError):
        database.add_contribution(goal, 100, "2026-10-14")
    with pytest.raises(ValueError):
        database.update_goal(goal, "Laptop", 150000, "2027-02-01")
    database.delete_contribution(contribution)
    assert database.goals()[0]["completed"] == 0
    assert database.goals()[0]["saved_paise"] == 50000
    database.delete_goal(goal)
    assert database.contributions(goal) == []
    assert database.goals() == []
    with pytest.raises(ValueError):
        database.add_contribution(goal, 100, "2026-10-15")


def test_demo_removal_preserves_personal_records(database):
    personal = database.add_transaction("expense", 100, "Food", "2026-10-12")
    database.save_budget_plan("2026-10", 100, {"Food": 50})
    database.load_demo(date(2026, 10, 12))
    with pytest.raises(ValueError):
        database.load_demo(date(2026, 10, 12))
    assert len(database.transactions()) == 89
    assert all(row["is_demo"] == 0 for row in database.budgets("2026-10"))
    demo_transaction = next(
        row for row in database.transactions() if row["is_demo"]
    )
    database.update_transaction(
        demo_transaction["id"],
        "expense",
        200,
        "Food",
        "2026-10-12",
        "Personal now",
    )
    goal = database.goals()[0]["id"]
    database.add_contribution(goal, 12345, "2026-10-12")
    database.remove_demo()
    assert sorted(row["id"] for row in database.transactions()) == sorted(
        [personal, demo_transaction["id"]]
    )
    assert len(database.budgets("2026-10")) == 2
    assert len(database.goals()) == 1
    assert database.goals()[0]["saved_paise"] == 12345
    assert not any(database.demo_counts().values())
    assert database.setting("demo_loaded") is None


def test_demo_reset_can_reload_and_handles_january(database):
    database.load_demo(date(2026, 1, 1))
    assert len(database.transactions()) == 88
    assert (
        max(row["transaction_date"] for row in database.transactions())
        == "2026-01-01"
    )
    database.remove_demo()
    assert database.transactions() == []
    assert database.goals() == []
    database.load_demo(date(2026, 1, 1))
    assert len(database.transactions()) == 88


def test_settings_persist(database):
    assert database.setting("currency") == "INR"
    database.set_currency("EUR")
    assert Database(database.path).setting("currency") == "EUR"
    with pytest.raises(ValueError):
        database.set_currency("XYZ")


def test_missing_records_fail_explicitly(database):
    with pytest.raises(ValueError):
        database.delete_transaction(999)
    with pytest.raises(ValueError):
        database.update_transaction(999, "income", 100, "Salary", "2026-10-12")
