"""Exact integer calculations. Floating point is used only for chart rendering."""

import calendar
from datetime import date, timedelta

import pandas as pd

from utils.validators import CURRENCIES, month_key

TRANSACTION_COLUMNS = [
    "id",
    "kind",
    "amount_paise",
    "category",
    "transaction_date",
    "description",
    "payment_method",
    "is_demo",
    "created_at",
]


def month_range(month):
    year, number = map(int, month_key(month).split("-"))
    return date(year, number, 1), date(
        year, number, calendar.monthrange(year, number)[1]
    )


def previous_month(month):
    start, _ = month_range(month)
    return (start - timedelta(days=1)).strftime("%Y-%m")


def money(paise, currency="INR"):
    """Format integer minor units without converting them to a float."""
    sign = "-" if paise < 0 else ""
    whole, fraction = divmod(abs(int(paise)), 100)
    return f"{sign}{CURRENCIES[currency]}{whole:,}.{fraction:02d}"


def amount_text(paise):
    whole, fraction = divmod(int(paise), 100)
    return f"{whole}.{fraction:02d}"


def frame(records):
    result = pd.DataFrame(records, columns=TRANSACTION_COLUMNS)
    result["amount_paise"] = result["amount_paise"].astype("int64")
    return result


def period_metrics(records):
    income = sum(
        row["amount_paise"] for row in records if row["kind"] == "income"
    )
    expenses = sum(
        row["amount_paise"] for row in records if row["kind"] == "expense"
    )
    savings = income - expenses
    return {
        "income": income,
        "expenses": expenses,
        "savings": savings,
        "savings_rate": savings / income * 100 if income else None,
        "count": len(records),
    }


def budget_status(spent, limit):
    if limit is None or limit <= 0:
        return {
            "percent": None,
            "remaining": None,
            "label": "No budget",
            "color": "gray",
            "progress": 0.0,
        }
    percent = spent / limit * 100
    # Integer comparisons keep exact 75% and 100% boundaries reliable.
    label, color = (
        ("Budget Exceeded", "red")
        if spent >= limit
        else (
            ("Approaching Limit", "orange")
            if spent * 4 >= limit * 3
            else ("Within Budget", "green")
        )
    )
    return {
        "percent": percent,
        "remaining": limit - spent,
        "label": label,
        "color": color,
        "progress": min(max(spent / limit, 0.0), 1.0),
    }


def category_summary(records, kind="expense", field="category"):
    data = frame(records)
    return (
        data[data["kind"] == kind]
        .groupby(field, as_index=False)["amount_paise"]
        .sum()
        .sort_values(
            "amount_paise",
            ascending=False,
            ignore_index=True,
        )
    )


def timeline(records, start, end, frequency="Monthly"):
    """Fill missing periods with zero; weeks start Monday and may be partial."""
    if start > end:
        raise ValueError("Start date must be on or before end date.")
    frequencies = {
        "Daily": "D",
        "Weekly": "W-SUN",
        "Monthly": "M",
        "Yearly": "Y",
    }
    if frequency not in frequencies:
        raise ValueError("Unsupported analysis interval.")
    interval = frequencies[frequency]
    data = frame(
        [
            row
            for row in records
            if start.isoformat() <= row["transaction_date"] <= end.isoformat()
        ]
    )
    periods = pd.period_range(start=start, end=end, freq=interval)
    result = pd.DataFrame(index=periods)
    if data.empty:
        result["income_paise"] = 0
        result["expense_paise"] = 0
    else:
        data["period"] = pd.to_datetime(data["transaction_date"]).dt.to_period(
            interval
        )
        for kind, column in (
            ("income", "income_paise"),
            ("expense", "expense_paise"),
        ):
            sums = (
                data[data["kind"] == kind]
                .groupby("period")["amount_paise"]
                .sum()
            )
            result[column] = sums.reindex(periods, fill_value=0).astype(
                "int64"
            )
    result["savings_paise"] = result["income_paise"] - result["expense_paise"]
    result.insert(0, "period", result.index.start_time)
    return result.reset_index(drop=True)


def insights(records, prior_records, budgets, currency="INR"):
    if not records:
        return [
            "Add a transaction to start discovering your spending patterns."
        ]
    messages = []
    metrics = period_metrics(records)
    if metrics["savings_rate"] is not None:
        messages.append(
            f"Your savings rate this month is {metrics['savings_rate']:.1f}%."
        )
    elif metrics["expenses"]:
        messages.append(
            "You have expenses but no income recorded this month; savings rate is unavailable."
        )
    if metrics["savings"] < 0:
        messages.append(
            f"Expenses exceed this month's income by {money(-metrics['savings'], currency)}."
        )
    categories = category_summary(records)
    previous = (
        category_summary(prior_records)
        .set_index("category")["amount_paise"]
        .to_dict()
    )
    if not categories.empty:
        top = categories.iloc[0]
        messages.append(
            f"{top['category']} is your highest spending category at {money(top['amount_paise'], currency)}."
        )
        for row in categories.to_dict("records"):
            old = previous.get(row["category"], 0)
            if old:
                change = (row["amount_paise"] - old) / old * 100
                if abs(change) >= 10:
                    direction = "increased" if change > 0 else "decreased"
                    messages.append(
                        f"{row['category']} expenses {direction} by {abs(change):.1f}% compared with last month."
                    )
    spending = categories.set_index("category")["amount_paise"].to_dict()
    for budget in budgets:
        amount = (
            metrics["expenses"]
            if budget["category"] == "Overall"
            else spending.get(budget["category"], 0)
        )
        state = budget_status(amount, budget["amount_paise"])
        if state["percent"] >= 75:
            messages.append(
                f"You have used {state['percent']:.1f}% of your {budget['category'].lower()} budget: {state['label']}."
            )
    return messages[:8]
