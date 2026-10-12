import csv
import io
from datetime import date

import pytest
from pypdf import PdfReader

from utils.exports import (
    parse_transactions_csv,
    report_pdf,
    summary_csv,
    transactions_csv,
)


def test_csv_roundtrip_retains_precision_quotes_and_unicode(database):
    database.add_transaction(
        "expense",
        12345,
        "Food",
        "2026-10-12",
        'Cafe, coffee "special" ₹\nSecond line',
    )
    database.add_transaction(
        "income",
        200000,
        "Salary",
        "2026-10-01",
        "=HYPERLINK('test')",
        "Bank Transfer",
    )
    content = transactions_csv(database.transactions())
    assert content.startswith(b"\xef\xbb\xbf")
    assert b"'=HYPERLINK" in content
    imported = parse_transactions_csv(content)
    assert sorted(row["amount_paise"] for row in imported) == [12345, 200000]
    assert any(row["description"].startswith("=HYPERLINK") for row in imported)
    assert any("₹" in row["description"] for row in imported)
    assert (
        summary_csv(database.transactions()).decode("utf-8-sig")
        == "category,expense_amount\r\nFood,123.45\r\n"
    )


@pytest.mark.parametrize(
    "content",
    [
        b"invalid,header\n1,2",
        b"\xff",
        b"kind,amount,category,transaction_date,description,payment_method\nexpense,0,Food,2026-10-12,x,UPI",
        b"kind,amount,category,transaction_date,description,payment_method\nexpense,1,Food,2026-10-12,x,UPI,extra",
    ],
)
def test_bad_csv_rejected(content):
    with pytest.raises(ValueError):
        parse_transactions_csv(content)


def test_empty_exports_are_valid():
    content = transactions_csv([]).decode("utf-8-sig")
    assert len(list(csv.DictReader(io.StringIO(content)))) == 0
    pdf = report_pdf([], date(2026, 10, 1), date(2026, 10, 31))
    assert pdf.startswith(b"%PDF-")
    reader = PdfReader(io.BytesIO(pdf))
    text = " ".join(page.extract_text() for page in reader.pages)
    assert "No transactions" in text
    assert "INR 0.00" in text


def test_pdf_actual_totals_pagination_and_escaping(database):
    database.add_transaction(
        "income", 500000, "Salary", "2026-10-01", "Pay & bonus"
    )
    for index in range(60):
        database.add_transaction(
            "expense",
            101,
            "Food",
            "2026-10-12",
            f"Lunch <b>literal</b> & tea {index}",
        )
    database.add_transaction(
        "expense", 999999, "Travel", "2026-09-30", "Outside range"
    )
    content = report_pdf(
        database.transactions(), date(2026, 10, 1), date(2026, 10, 31)
    )
    reader = PdfReader(io.BytesIO(content))
    assert len(reader.pages) >= 3
    text = " ".join(page.extract_text() for page in reader.pages)
    assert "INR 5,000.00" in text
    assert "INR 60.60" in text
    assert "INR 4,939.40" in text
    assert "Outside range" not in text
    assert "<b>literal</b>" in text
    assert all(
        f"Page {index}" in page.extract_text()
        for index, page in enumerate(reader.pages, start=1)
    )
