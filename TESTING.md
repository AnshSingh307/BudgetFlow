# Verification record

Verification performed on 12 October 2026 in the project workspace.

## Environment actually used

- Windows, Python 3.11.9
- Streamlit 1.65.0, Pandas 2.3.3, Plotly 6.9.0
- ReportLab 4.5.1, pytest 9.1.1, pypdf 6.20.0, Ruff 0.17.0
- Exact installed packages are recorded in `requirements-lock.txt`.

## Automated results

```text
python -m pytest -q
60 passed in 30.10s

python -m pip check
No broken requirements found.

python -m ruff check app.py database.py pages utils tests --select E4,E7,E9,F
All checks passed!

python -m ruff format app.py database.py pages utils tests --check --line-length 79
22 files already formatted

python -m compileall -q app.py database.py pages utils tests
Completed successfully (exit code 0).
```

The final full suite was run after fixing the selector formatter, updating PDF pagination, and formatting the Python source. The two selector failures found earlier were corrected; they are not outstanding failures.

## What the tests verify

| Area | Verification |
| --- | --- |
| Monetary calculations | Exact decimal-to-paise conversion, rejection of invalid/negative/over-precision inputs, income/expense sums, negative savings, zero-income handling, money display |
| Budget calculations | Exact 75% and 100% thresholds, overspending, negative remaining budget, and missing budgets |
| Time filters | Month boundaries, leap years, January rollover, inclusive ranges, missing periods, and daily/weekly/monthly/yearly aggregation |
| Transactions | Income/expense creation, editing, deletion, input validation, and literal SQL-like text storage |
| Persistence | A new `Database` instance reopens the same SQLite file with the saved values |
| Atomic changes | Invalid imports leave no partial records; an invalid budget replacement preserves the prior plan |
| Savings goals | Creation/editing, contributions, accurate progress, completion guards, reopening after correction, and cascading deletion |
| Demo handling | Safe reset/reload, personal-record preservation, preservation of edited demo records and goals with personal contributions, and existing budget preservation |
| Settings | Currency preference survives reopening and invalid currencies are rejected |
| CSV | Exact amounts, quoting, commas/newlines, Unicode, formula protection, reimport, invalid headers/values, and empty export |
| PDF | Correct real totals, date-range exclusion, empty report, literal escaped markup, pagination, and page numbers |
| Streamlit | Overview plus all six other pages in empty/demo states; add/edit/delete income and expense forms; invalid amount errors; month-change filters; budget/goal/contribution forms; PDF preparation button |

Automated tests use disposable temporary databases. They do not operate on the default personal ledger.

## Startup and browser review

The finished application started with the project's virtual environment using:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.headless true --server.fileWatcherType none --server.port 8501
```

The server printed its localhost URL, and the application was opened in the in-app browser. The default database was created automatically. During visual review, demo data was deliberately loaded using the app's button; the delivered local demonstration ledger contains **88 tagged demo transactions, 16 demo budget records, 3 goals, and 3 contributions**. These are synthetic entries. Users can remove them in **Settings & data** using the confirmed demo removal action.

Browser review checked the seven overview metrics, working sidebar navigation to the planner, goals, and reports, rendered Plotly charts, live PDF preparation with an enabled download button, light/dark theme switching, and a **390 × 844** mobile viewport. The mobile viewport stacked inputs and cards and collapsed the sidebar. It was reset after review. Screenshots are saved in `docs/screenshots/`. The localhost `/_stcore/health` endpoint returned `ok`.

On this managed machine, the initial sandbox blocked local sockets. The Streamlit test runner waited while constructing an asyncio socket pair, and the initial server attempt could not be reached. After allowing the required local socket access, the test suite and server ran successfully. This was an execution-environment restriction; no application security setting was disabled to work around it.

## PDF visual review

A three-page report generated from the synthetic October 2026 ledger was rendered with Poppler and every page was inspected. Its totals were income **INR 42,500.00**, expenses **INR 24,899.00**, and net savings **INR 17,601.00**. Headings now remain with their tables, long tables repeat their section/header rows, and footers and page numbers remain outside the table area. The verification PDF and its page images are intermediate QA files under the ignored `tmp/pdfs/` folder, not personal financial records.

## Scope and remaining limits

- AppTest executes actual Streamlit scripts and forms but is not a browser rendering test.
- Browser review covered desktop light/dark views and one narrow viewport; it is not an exhaustive audit of all browsers/devices or every possible input combination.
- PDF visual review covered the sample English-language ledger and automated pagination cases. Complex-script shaping and color emoji are not guaranteed by the bundled fonts.
- No cloud deployment, bank connection, account authentication, or currency conversion was attempted or claimed.
- CSV imports append records; duplicate detection is session-local rather than permanent.

## Reproduce the checks

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check app.py database.py pages utils tests --select E4,E7,E9,F
.\.venv\Scripts\python.exe -m ruff format app.py database.py pages utils tests --check --line-length 79
```

Normal local Python environments should not need the managed sandbox exception used during this run.

## Follow-up: personal entry shortcuts and credential files

On 12 October 2026, Overview received direct links for adding salary/income and expenses. New income forms now default to Salary and Bank Transfer. The Streamlit UI regression suite was rerun: **12 passed in 32.88s**. Ruff lint checks passed. The live browser confirmed both dashboard links and the salary form defaults, without entering personal amounts.

A credential-pattern scan of 31 application text files found no API-key candidates, local credential files, or credential-related database setting names. BudgetFlow does not load or display API keys. `.gitignore` now excludes `.env` variants and Streamlit secret-file variants. The scan covers this project, not credentials in other applications; Git ignore rules do not encrypt files or remove previously committed secrets.

## Before initial GitHub publication

The complete regression suite was rerun on 12 October 2026 after the personal-entry updates: **60 passed in 9.35s**. The publication excludes the local ledger, credentials, virtual environment, caches, and temporary QA outputs. Screenshots included in the project show labeled synthetic demo data or empty entry forms.
