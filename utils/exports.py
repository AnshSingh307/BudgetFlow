"""Round-trip CSV imports and printable reports, using the supplied ledger only."""

import csv
import io
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)

from utils.calculations import (
    amount_text,
    category_summary,
    period_metrics,
    timeline,
)
from utils.validators import to_paise, transaction_values

CSV_COLUMNS = [
    "kind",
    "amount",
    "category",
    "transaction_date",
    "description",
    "payment_method",
]


def csv_safe(value):
    text = str(value)
    # Prevent user-entered text from becoming a spreadsheet formula on opening.
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def transactions_csv(records):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS + ["source"])
    writer.writeheader()
    for record in records:
        row = {
            column: csv_safe(record.get(column, "")) for column in CSV_COLUMNS
        }
        row["amount"] = amount_text(record["amount_paise"])
        row["source"] = "Demo" if record.get("is_demo") else "Personal"
        writer.writerow(row)
    return output.getvalue().encode("utf-8-sig")


def parse_transactions_csv(content):
    if len(content) > 2 * 1024 * 1024:
        raise ValueError("CSV must be no larger than 2 MB.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(
            "Save the file as UTF-8 CSV before importing."
        ) from None
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    if not reader.fieldnames or not set(CSV_COLUMNS).issubset(
        reader.fieldnames
    ):
        raise ValueError("CSV needs these columns: " + ", ".join(CSV_COLUMNS))
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError("CSV has duplicate column names.")
    records = []
    try:
        for number, row in enumerate(reader, start=2):
            if len(records) >= 10_000:
                raise ValueError("Import at most 10,000 rows at a time.")
            try:
                if None in row or any(
                    row.get(column) is None for column in CSV_COLUMNS
                ):
                    raise ValueError("Row has missing or extra cells.")
                description = row["description"]
                # Undo only the safety prefix used by our own CSV exporter.
                if description.startswith("'") and description[
                    1:
                ].lstrip().startswith(("=", "+", "-", "@")):
                    description = description[1:]
                record = {
                    "kind": row["kind"].strip().lower(),
                    "amount_paise": to_paise(row["amount"]),
                    "category": row["category"].strip(),
                    "transaction_date": row["transaction_date"].strip(),
                    "description": description,
                    "payment_method": row["payment_method"].strip(),
                }
                transaction_values(**record)
                records.append(record)
            except ValueError as error:
                raise ValueError(f"Row {number}: {error}") from None
    except csv.Error as error:
        raise ValueError(f"Malformed CSV: {error}") from None
    if not records:
        raise ValueError("CSV contains no transactions.")
    return records


def summary_csv(records):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["category", "expense_amount"])
    for row in category_summary(records).to_dict("records"):
        writer.writerow(
            [csv_safe(row["category"]), amount_text(row["amount_paise"])]
        )
    return output.getvalue().encode("utf-8-sig")


def report_pdf(records, start, end, currency="INR"):
    """Generate a paginated financial report with wrapped cells and repeated headers."""
    if start > end:
        raise ValueError("Start date must be on or before end date.")
    records = [
        row
        for row in records
        if start.isoformat() <= row["transaction_date"] <= end.isoformat()
    ]
    output = io.BytesIO()
    font = "Helvetica"
    bold = "Helvetica-Bold"
    fonts = Path(__file__).resolve().parents[1] / "assets" / "fonts"
    if (fonts / "DejaVuSans.ttf").exists():
        if "BudgetFlow" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(
                TTFont("BudgetFlow", str(fonts / "DejaVuSans.ttf"))
            )
            pdfmetrics.registerFont(
                TTFont("BudgetFlowBold", str(fonts / "DejaVuSans-Bold.ttf"))
            )
        font, bold = "BudgetFlow", "BudgetFlowBold"
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "ReportTitle",
            fontName=bold,
            fontSize=23,
            leading=29,
            textColor=colors.HexColor("#135D54"),
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            "SectionTitle",
            fontName=bold,
            fontSize=12,
            leading=17,
            spaceBefore=17,
            spaceAfter=8,
            textColor=colors.HexColor("#135D54"),
        )
    )
    styles.add(ParagraphStyle("Cell", fontName=font, fontSize=8, leading=12))
    styles.add(
        ParagraphStyle("Number", parent=styles["Cell"], alignment=TA_RIGHT)
    )
    styles.add(
        ParagraphStyle("ReportBody", fontName=font, fontSize=9, leading=14)
    )

    def paragraph(value, style="Cell"):
        text = str(value)
        if font == "Helvetica":
            text = text.encode("cp1252", errors="replace").decode("cp1252")
        return Paragraph(escape(text).replace("\n", "<br/>"), styles[style])

    def amount(paise):
        whole, fraction = divmod(abs(int(paise)), 100)
        sign = "-" if paise < 0 else ""
        return f"{currency} {sign}{whole:,}.{fraction:02d}"

    def report_table(headers, rows, widths, section=None):
        data = (
            [[paragraph(section, "SectionTitle")] + [""] * (len(headers) - 1)]
            if section
            else []
        )
        header_index = len(data)
        data.append([paragraph(header) for header in headers])
        data += [[paragraph(value) for value in row] for row in rows]
        table = LongTable(
            data, colWidths=widths, repeatRows=header_index + 1, hAlign="LEFT"
        )
        table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, header_index),
                        (-1, header_index),
                        colors.HexColor("#E5F3EF"),
                    ),
                    (
                        "ROWBACKGROUNDS",
                        (0, header_index + 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F6F8FA")],
                    ),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    (
                        "LINEBELOW",
                        (0, header_index),
                        (-1, header_index),
                        0.5,
                        colors.HexColor("#CCDAD7"),
                    ),
                ]
            )
        )
        if section:
            table.setStyle(
                TableStyle(
                    [
                        ("SPAN", (0, 0), (-1, 0)),
                        ("LEFTPADDING", (0, 0), (-1, 0), 0),
                        ("TOPPADDING", (0, 0), (-1, 0), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ]
                )
            )
        return table

    metrics = period_metrics(records)
    flow = [
        paragraph("BudgetFlow", "ReportTitle"),
        paragraph(
            "Personal Budget & Expense Tracker | Financial report",
            "ReportBody",
        ),
        paragraph(
            f"{start:%d %b %Y} to {end:%d %b %Y} | Currency: {currency}",
            "ReportBody",
        ),
        Spacer(1, 14),
    ]
    demo_count = sum(bool(row.get("is_demo")) for row in records)
    if demo_count:
        flow.append(
            paragraph(
                f"DEMO DATA: {demo_count} of {len(records)} entries are synthetic demonstration records.",
                "ReportBody",
            )
        )
    summary = [
        ("Income", amount(metrics["income"])),
        ("Expenses", amount(metrics["expenses"])),
        ("Net savings", amount(metrics["savings"])),
        (
            "Savings rate",
            f"{metrics['savings_rate']:.1f}%"
            if metrics["savings_rate"] is not None
            else "N/A - no income",
        ),
        ("Transactions", str(metrics["count"])),
    ]
    flow.append(
        report_table(["Period overview", "Value"], summary, [290, 225])
    )
    flow.append(
        paragraph(
            "Net savings = income minus expenses for this date range. Goal contributions are tracked separately and are not deducted a second time.",
            "ReportBody",
        )
    )
    if records:
        monthly = timeline(records, start, end)
        flow.append(
            report_table(
                ["Month", "Income", "Expenses", "Net savings"],
                [
                    (
                        row["period"].strftime("%b %Y"),
                        amount(row["income_paise"]),
                        amount(row["expense_paise"]),
                        amount(row["savings_paise"]),
                    )
                    for row in monthly.to_dict("records")
                ],
                [95, 140, 140, 140],
                "Monthly cash flow",
            )
        )
        categories = category_summary(records)
        if categories.empty:
            flow.append(paragraph("Expense categories", "SectionTitle"))
            flow.append(
                paragraph("No expenses in this date range.", "ReportBody")
            )
        else:
            flow.append(
                report_table(
                    ["Category", "Total expenses", "Share"],
                    [
                        (
                            row["category"],
                            amount(row["amount_paise"]),
                            f"{row['amount_paise'] / metrics['expenses'] * 100:.1f}%",
                        )
                        for row in categories.to_dict("records")
                    ],
                    [220, 195, 100],
                    "Expense categories",
                )
            )
        methods = category_summary(records, field="payment_method")
        flow.append(
            report_table(
                ["Payment method", "Expenses"],
                [
                    (row["payment_method"], amount(row["amount_paise"]))
                    for row in methods.to_dict("records")
                ],
                [290, 225],
                "Payment method distribution (expenses)",
            )
        )
        rows = [
            (
                row["transaction_date"],
                row["kind"].title(),
                row["category"],
                row["description"] or "-",
                amount(row["amount_paise"]),
            )
            for row in sorted(
                records, key=lambda r: (r["transaction_date"], r["id"])
            )
        ]
        flow.append(
            report_table(
                ["Date", "Type", "Category", "Description", "Amount"],
                rows,
                [68, 53, 78, 193, 123],
                "Transaction ledger",
            )
        )
    else:
        flow.append(
            paragraph(
                "No transactions were recorded in this date range.",
                "ReportBody",
            )
        )

    def footer(canvas, document):
        canvas.setStrokeColor(colors.HexColor("#CCDAD7"))
        canvas.line(40, 39, A4[0] - 40, 39)
        canvas.setFont(font, 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(40, 25, "BudgetFlow | Local financial report")
        canvas.drawRightString(A4[0] - 40, 25, f"Page {document.page}")

    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=38,
        bottomMargin=52,
        title="BudgetFlow Financial Report",
    )
    document.build(flow, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
