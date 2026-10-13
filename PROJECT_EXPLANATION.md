# BudgetFlow: college project explanation and viva guide

## A simple introduction you can say aloud

“My project is a Personal Budget & Expense Tracker called BudgetFlow. I built it mainly in Python using Streamlit for the interface and SQLite for permanent storage. Users can manage income and expenses, set budgets, contribute to savings goals, and generate financial reports. It uses real stored entries for every calculation. I separated the interface, database, and business logic so that I can understand and test each part.”

## How to understand the project in stages

1. Read `utils/validators.py`: it defines valid categories and turns an amount such as `125.50` into `12550` integer paise.
2. Read `database.py`: the `Database` class initializes five tables and provides functions for saving and retrieving records.
3. Read `utils/calculations.py`: it calculates income, spending, savings, progress, and summaries without relying on the interface.
4. Read `app.py`: it configures the application, prepares the database, and creates navigation.
5. Read `views/transactions.py`: it reuses one workflow for both income and expenses.
6. Read the budget, savings, and reports pages to see how the same database and calculation functions are reused.
7. Run the tests, then demonstrate the app with its clearly labeled demo data.

## One expense from start to finish

Suppose I record a Food expense of ₹120.50 paid through UPI.

1. Streamlit presents the form and receives the amount as text.
2. `to_paise("120.50")` uses Python's `Decimal` and returns `12050`.
3. The database method checks the amount, date, category, and payment method again.
4. A parameterized `INSERT` stores the expense in SQLite.
5. Streamlit reruns the page after the save.
6. Dashboard totals sum integer paise. Display helpers turn `12050` back into `₹120.50`.
7. Pandas groups records for charts, and Plotly displays the results.

This repeated validation matters because CSV imports and Python calls should obey the same rules as forms.

## The calculations to explain

| Calculation | Formula | Example |
| --- | --- | --- |
| Monthly income | Sum income records in selected month | ₹10,000 + ₹2,000 = ₹12,000 |
| Monthly expenses | Sum expense records in selected month | ₹3,000 + ₹1,500 = ₹4,500 |
| Monthly savings | Income − expenses | ₹12,000 − ₹4,500 = ₹7,500 |
| Savings rate | Savings ÷ income × 100 | 7,500 ÷ 12,000 × 100 = 62.5% |
| Remaining budget | Overall limit − expenses | ₹6,000 − ₹4,500 = ₹1,500 |
| Budget utilization | Expenses ÷ limit × 100 | 4,500 ÷ 6,000 × 100 = 75% |
| Goal progress | Contributions ÷ target × 100 | ₹15,000 ÷ ₹60,000 × 100 = 25% |

Remaining balance is cumulative income minus cumulative expenses through the selected month's end, unlike monthly savings. An opening balance is not assumed. If income is zero, savings rate is undefined and the app displays a dash. Negative savings and negative remaining budgets are preserved rather than hidden.

Goal contributions are separate allocation records. Adding ₹5,000 to a laptop goal does not create ₹5,000 of income or deduct ₹5,000 again as an expense. Contributions may describe money saved before this ledger began. If the laptop is purchased, the purchase belongs in expenses.

## Database tables and relationships

- `transactions` stores both income and expenses, distinguished by `kind`.
- `budgets` stores the overall monthly limit and optional category limits. A unique constraint prevents two limits for the same month/category.
- `savings_goals` stores goal names, targets, dates, and completion state.
- `goal_contributions` references a goal using a foreign key. One goal can have many contributions.
- `settings` persists currency preference and the demo-loaded marker.

Every record ID is an integer primary key. The contribution relationship uses `ON DELETE CASCADE`, so removing a goal also removes its contribution history. The UI requires confirmation before that deletion.

## Python programming concepts demonstrated

- **Functions:** reusable tasks such as `money`, `to_paise`, and `period_metrics`.
- **Classes:** `Database` groups operations around a particular database file.
- **Lists:** lists of transaction dictionaries, categories, and report rows.
- **Dictionaries:** named record fields, budget allocations, and calculated totals.
- **Tuples:** fixed category/payment options and SQL parameter sequences.
- **Loops:** processing records, building forms, and creating goal cards.
- **Conditions:** warnings, validation, empty states, and budget status thresholds.
- **Exceptions:** invalid input raises `ValueError`; the UI explains the error.
- **Context managers:** database transactions commit on success, roll back on failure, and close connections reliably.
- **Modules:** separate files make the project easier to understand, reuse, and test.
- **File handling:** CSV is read from uploaded bytes and written to downloadable bytes; reports use an in-memory PDF buffer.

## Common viva questions and answers

**1. Why did you choose Python?**  
Python provides readable syntax, built-in SQLite and CSV support, and practical libraries for interfaces, analysis, and reporting. It lets the project remain mostly one language.

**2. What is Streamlit?**  
Streamlit turns a Python script into an interactive web interface. It supplies widgets such as buttons, forms, date selectors, tables, and download buttons.

**3. What happens when a Streamlit widget changes?**  
The script reruns to update the interface. Forms group inputs until submission. Session state remembers temporary browser-session values; SQLite stores long-term data.

**4. What is SQLite, and why use it?**  
SQLite is an embedded relational database stored in a local file. It supports SQL, constraints, and transactions without requiring a separate database server, which fits a local single-user college project.

**5. What does CRUD mean?**  
Create, Read, Update, Delete. Adding a transaction is `INSERT`, reading history is `SELECT`, editing is `UPDATE`, and removing is `DELETE`.

**6. What is a primary key?**  
A primary key uniquely identifies a table row. BudgetFlow uses IDs to edit the intended record even if two records have the same description and amount.

**7. What is a foreign key?**  
A foreign key links a child row to a parent row. Each contribution's `goal_id` must reference an existing savings goal. SQLite foreign-key enforcement is enabled on every connection.

**8. Why not store money as a Python float?**  
Binary floating point cannot represent every decimal fraction exactly. Input uses `Decimal`, and stored money uses integer paise, so sums such as ₹0.10 + ₹0.20 become exactly 10 + 20 = 30 paise. Chart coordinates and percentage display may use floats.

**9. What is input validation?**  
It checks that data obeys rules before saving: positive amounts, at most two decimal places, valid dates, valid categories, and text length limits. Validation also runs at the database boundary.

**10. How do you prevent SQL injection?**  
Queries use placeholders such as `WHERE id=?`, with values passed separately. User descriptions are stored as literal text rather than concatenated into executable SQL.

**11. What is a transaction in database terminology?**  
It is a group of operations that succeeds or fails together. A CSV import saves all validated records atomically. Replacing a budget plan cannot leave half of the new plan saved if an operation fails.

**12. What is Pandas used for?**  
Pandas organizes records into DataFrames, groups spending by category or period, and fills periods without activity with zero. Financial source amounts remain integer paise.

**13. Why use Plotly?**  
Plotly provides interactive bar, donut, and line charts with tooltips. It makes patterns easier to explore than a list of numbers.

**14. What happens when the database is empty?**  
Totals are zero, budgets are “Not set,” and explanatory empty states appear. Zero income produces no savings-rate percentage. Charts and exports remain usable.

**15. How is data preserved after restart?**  
Data is committed to `data/budgetflow.db`. Starting a new Python process opens the same file rather than rebuilding the records in memory. Tests reopen a temporary database to verify persistence.

**16. How do you avoid double counting goals?**  
Contributions have their own table and do not modify transaction totals. They describe allocation to a target rather than money entering or leaving the ledger.

**17. Can a goal be marked completed before reaching its target?**  
No. Both the UI and database require contributions to reach the target. Removing a contribution reopens the goal to avoid a misleading completion state.

**18. How are insights generated?**  
Simple Python rules compare actual category totals, savings rates, and budget percentages. There is no external AI model. The app explicitly notes that an ongoing month may be incomplete.

**19. How are CSV files handled?**  
The standard `csv` module reads UTF-8 files. All rows are checked before saving. CSV exports preserve exact two-decimal amounts, quote commas/newlines correctly, and protect text that could be interpreted as a spreadsheet formula.

**20. Why might importing the same CSV twice create duplicates?**  
Import is append-only and does not infer whether identical purchases are duplicates. The UI warns the user and blocks repeating the same file in the current browser session. Persistent duplicate detection is future scope.

**21. How is a PDF report created?**  
ReportLab builds a paginated document from the selected records. It includes period totals, monthly cash flow, category spending, payment methods, and the transaction ledger. Tables wrap long descriptions and repeat headers on subsequent pages.

**22. What is modular programming?**  
It divides a program into focused files and reusable functions. The database, calculations, charts, exports, and pages can be changed or tested independently.

**23. What did you test?**  
Arithmetic, input validation, income/expense CRUD, month boundaries, persistence, budget thresholds, atomic imports, goals, demo removal, CSV precision, PDF contents/pagination, and real Streamlit form execution. Refer to `TESTING.md` for checks actually completed.

**24. Does changing currency convert amounts?**  
No. It changes the display label only. The app explicitly tells users to keep one consistent currency in the ledger. Exchange-rate conversion would require additional accounting rules and data.

**25. What are this project's limitations?**  
It is a local single-user application. It has no login, bank synchronization, encryption, or opening balance model. Those features are outside the implemented scope and can be discussed as future improvements.

## Suggested viva demonstration

Show the overview, add income and an expense, filter history, edit the expense, save a budget, create a goal and contribute, then download a report. Explain where each value is calculated. Finish by running the automated tests and showing the modular folder structure. Demo data should always be identified as synthetic.

## How to prepare confidently

Run the project yourself and make a small personal test ledger. Change one amount and predict how the dashboard should change before checking it. Follow the function calls from form to validation to database to calculation. Explain the code in your own words instead of memorizing the file line by line.
