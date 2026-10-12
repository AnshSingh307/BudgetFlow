from datetime import date

import pytest

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
from utils.validators import iso_date, month_key, to_paise


def transaction(kind, amount, when="2026-10-12", category="Food"):
    return {
        "id": 1,
        "kind": kind,
        "amount_paise": amount,
        "transaction_date": when,
        "category": category,
        "description": "",
        "payment_method": "UPI",
        "is_demo": 0,
    }


@pytest.mark.parametrize(
    "value,expected",
    [("0.01", 1), ("1.10", 110), ("1200.50", 120050), (" 99.99 ", 9999)],
)
def test_exact_money(value, expected):
    assert to_paise(value) == expected


@pytest.mark.parametrize(
    "value",
    ["0", "-1", "nan", "Infinity", "1.001", "abc", "", "10000000000.01"],
)
def test_reject_bad_amounts(value):
    with pytest.raises(ValueError):
        to_paise(value)


def test_exact_totals_and_negative_savings():
    records = [
        transaction("income", 10001),
        transaction("expense", 3333),
        transaction("expense", 9999),
    ]
    values = period_metrics(records)
    assert values["income"] == 10001
    assert values["expenses"] == 13332
    assert values["savings"] == -3331
    assert values["savings_rate"] == pytest.approx(-3331 / 10001 * 100)
    assert money(-123456, "INR") == "-₹1,234.56"
    assert money(10001, "USD") == "$100.01"


def test_empty_and_zero_income():
    assert period_metrics([]) == {
        "income": 0,
        "expenses": 0,
        "savings": 0,
        "savings_rate": None,
        "count": 0,
    }
    assert (
        period_metrics([transaction("expense", 100)])["savings_rate"] is None
    )
    assert category_summary([]).empty
    assert budget_status(100, None)["remaining"] is None
    assert budget_status(0, 0)["label"] == "No budget"


@pytest.mark.parametrize(
    "spent,label,remaining",
    [
        (7499, "Within Budget", 2501),
        (7500, "Approaching Limit", 2500),
        (9999, "Approaching Limit", 1),
        (10000, "Budget Exceeded", 0),
        (12000, "Budget Exceeded", -2000),
    ],
)
def test_budget_boundaries(spent, label, remaining):
    state = budget_status(spent, 10000)
    assert state["label"] == label
    assert state["remaining"] == remaining
    assert 0 <= state["progress"] <= 1


def test_calendar_and_year_rollover():
    assert month_range("2024-02") == (date(2024, 2, 1), date(2024, 2, 29))
    assert month_range("2025-02")[1].day == 28
    assert previous_month("2026-01") == "2025-12"
    with pytest.raises(ValueError):
        month_key("2026-13")
    with pytest.raises(ValueError):
        iso_date("2026-02-30")


@pytest.mark.parametrize("frequency", ["Daily", "Weekly", "Monthly", "Yearly"])
def test_timeline_fills_gaps_and_retains_totals(frequency):
    records = [
        transaction("income", 90000, "2025-12-31"),
        transaction("expense", 15001, "2026-01-03"),
        transaction("expense", 20000, "2026-02-10"),
        transaction("income", 80000, "2026-01-04"),
    ]
    data = timeline(records, date(2025, 12, 31), date(2026, 2, 11), frequency)
    assert int(data["income_paise"].sum()) == 170000
    assert int(data["expense_paise"].sum()) == 35001
    assert int(data["savings_paise"].sum()) == 134999
    assert not data.isna().any().any()


def test_timeline_excludes_outside_range_and_empty_months():
    records = [
        transaction("expense", 500, "2026-10-01"),
        transaction("expense", 1000, "2026-09-30"),
    ]
    data = timeline(records, date(2026, 10, 1), date(2026, 12, 31))
    assert list(data["expense_paise"]) == [500, 0, 0]
    empty = timeline([], date(2026, 1, 1), date(2026, 1, 3), "Daily")
    assert len(empty) == 3
    assert int(empty["expense_paise"].sum()) == 0


def test_insights_use_actual_data():
    records = [transaction("income", 100000), transaction("expense", 15000)]
    prior = [transaction("expense", 10000, "2026-09-12")]
    messages = insights(
        records, prior, [{"category": "Food", "amount_paise": 16000}]
    )
    assert any("85.0%" in message for message in messages)
    assert any("increased by 50.0%" in message for message in messages)
    assert any("93.8%" in message for message in messages)
    assert any("Food is your highest" in message for message in messages)
    assert len(insights([], [], [])) == 1
