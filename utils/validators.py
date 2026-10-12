"""Validate at the database boundary as well as in forms."""

from datetime import date
from decimal import Decimal, InvalidOperation

EXPENSE_CATEGORIES = (
    "Food",
    "Transportation",
    "Shopping",
    "Education",
    "Entertainment",
    "Healthcare",
    "Rent",
    "Bills",
    "Subscriptions",
    "Travel",
    "Other",
)
INCOME_CATEGORIES = (
    "Salary",
    "Freelancing",
    "Allowance",
    "Scholarship",
    "Business",
    "Investments",
    "Gifts",
    "Other",
)
PAYMENT_METHODS = ("Cash", "UPI", "Debit Card", "Credit Card", "Bank Transfer")
CURRENCIES = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}
MAX_PAISE = 1_000_000_000_000


def to_paise(value, *, allow_zero=False):
    """Parse decimal text exactly; never silently round a third decimal place."""
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValueError("Enter a valid amount, such as 1250.50.") from None
    if not amount.is_finite():
        raise ValueError("Amount must be finite.")
    minimum = Decimal(0) if allow_zero else Decimal("0.01")
    if amount < minimum or amount > Decimal(MAX_PAISE) / 100:
        raise ValueError(
            "Amount must be positive and no more than 10,000,000,000."
        )
    scaled = amount * 100
    if scaled != scaled.to_integral_value():
        raise ValueError("Use no more than two decimal places.")
    return int(scaled)


def validate_paise(value, *, allow_zero=False):
    minimum = 0 if allow_zero else 1
    if type(value) is not int or not minimum <= value <= MAX_PAISE:
        raise ValueError(
            "Money must be integer paise within the permitted range."
        )
    return value


def iso_date(value):
    try:
        text = value.isoformat() if isinstance(value, date) else str(value)
        parsed = date.fromisoformat(text)
        if parsed.isoformat() != text:
            raise ValueError
        return text
    except (ValueError, TypeError):
        raise ValueError("Choose a valid date in YYYY-MM-DD format.") from None


def month_key(value):
    text = str(value)
    try:
        parsed = date.fromisoformat(text + "-01")
        if len(text) != 7 or parsed.strftime("%Y-%m") != text:
            raise ValueError
    except ValueError:
        raise ValueError("Month must have the format YYYY-MM.") from None
    return text


def clean_text(value, *, label="Description", maximum=500, required=False):
    text = str(value).strip()
    if required and not text:
        raise ValueError(f"{label} cannot be empty.")
    if len(text) > maximum:
        raise ValueError(f"{label} must be at most {maximum} characters.")
    if any(ord(char) < 32 and char not in "\n\t" for char in text):
        raise ValueError(f"{label} contains unsupported control characters.")
    return text


def transaction_values(
    kind,
    amount_paise,
    category,
    transaction_date,
    description="",
    payment_method="UPI",
):
    categories = {"income": INCOME_CATEGORIES, "expense": EXPENSE_CATEGORIES}
    if kind not in categories:
        raise ValueError("Transaction type must be income or expense.")
    if category not in categories[kind]:
        raise ValueError("Select a category valid for this transaction type.")
    if payment_method not in PAYMENT_METHODS:
        raise ValueError("Select a supported payment method.")
    return (
        kind,
        validate_paise(amount_paise),
        category,
        iso_date(transaction_date),
        clean_text(description),
        payment_method,
    )
