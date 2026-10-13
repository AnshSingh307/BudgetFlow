import hashlib

import pandas as pd
import streamlit as st

from utils.exports import CSV_COLUMNS, parse_transactions_csv, transactions_csv
from utils.ui import action, currency, db, heading
from utils.validators import CURRENCIES


def render():
    heading(
        "Your workspace, your way.",
        "Personalize your view and keep your data in order.",
        "",
    )
    with st.container(border=True):
        st.subheader("Preferences", anchor=False)
        with st.form("preferences"):
            codes = list(CURRENCIES)
            chosen = st.selectbox(
                "Display currency",
                codes,
                index=codes.index(currency()),
                format_func=lambda code: f"{code} ({CURRENCIES[code]})",
            )
            st.caption(
                "This changes currency labels only. Existing values are not converted. Use a single currency consistently for this ledger."
            )
            if st.form_submit_button("Save preferences", type="primary"):
                action(
                    lambda: db().set_currency(chosen),
                    "Display currency updated.",
                )
        st.markdown(
            "**Appearance:** open the **⋮** menu and choose **Light** or **Dark**."
        )
    with st.container(border=True):
        st.subheader("Import transactions", anchor=False)
        st.caption(
            "UTF-8 CSV · up to 2 MB / 10,000 rows · all rows validated before any are saved"
        )
        st.code(",".join(CSV_COLUMNS), language="text")
        template = (",".join(CSV_COLUMNS) + "\n").encode("utf-8-sig")
        st.download_button(
            "Download blank CSV template",
            template,
            "budgetflow-import-template.csv",
            "text/csv",
        )
        uploaded = st.file_uploader("Choose CSV", type=["csv"])
        if uploaded is not None:
            try:
                content = uploaded.getvalue()
                digest = hashlib.sha256(content).hexdigest()
                records = parse_transactions_csv(content)
                st.success(
                    f"Validated {len(records)} rows. Review the first ten below."
                )
                preview = pd.DataFrame(records[:10]).rename(
                    columns={"amount_paise": "amount_in_paise"}
                )
                st.dataframe(preview, width="stretch", hide_index=True)
                confirmed = st.checkbox(
                    "Append these rows as personal transactions. Importing an existing export can create duplicates.",
                    key="import_confirm_" + digest,
                )
                already = digest in st.session_state.get(
                    "imported_files", set()
                )
                if already:
                    st.info(
                        "This file was imported in this browser session. Start a new session only if you intend to import it again."
                    )
                if st.button(
                    "Import validated transactions",
                    disabled=not confirmed or already,
                    type="primary",
                ):

                    def save():
                        db().import_transactions(records)
                        st.session_state.setdefault(
                            "imported_files", set()
                        ).add(digest)

                    action(save, f"Imported {len(records)} transactions.")
            except ValueError as error:
                st.error(str(error))
    with st.container(border=True):
        st.subheader("Export your full transaction history", anchor=False)
        st.download_button(
            "Download all transactions",
            transactions_csv(db().transactions()),
            "budgetflow-all-transactions.csv",
            "text/csv",
            icon=":material/download:",
        )
        st.caption(
            "CSV exports cover the transaction ledger. For a full backup, stop the server and copy data/budgetflow.db; this also preserves budgets, goals, contributions, and settings."
        )
    with st.container(border=True):
        st.subheader("Demo workspace", anchor=False)
        st.write(
            "Explore four months of synthetic transactions, budgets, and example goals. They are always labeled as demo data."
        )
        counts = db().demo_counts()
        loaded = db().setting("demo_loaded") is not None
        if st.button(
            "Load sample demo data", disabled=loaded, icon=":material/science:"
        ):
            action(
                db().load_demo,
                "Demo records loaded. Open Overview to explore.",
            )
        if loaded or any(counts.values()):
            st.caption(
                " · ".join(
                    f"{value} {table.replace('_', ' ')}"
                    for table, value in counts.items()
                )
            )
            st.warning(
                "Removing demo data deletes only tagged demo records. A record you edit becomes personal. Personal contributions and their goals are preserved; original demo contributions are removed."
            )
            confirmed = st.checkbox(
                "I confirm removal of all tagged demo data."
            )
            if st.button("Remove demo data", disabled=not confirmed):
                action(
                    db().remove_demo,
                    "Demo records removed. Personal records preserved.",
                )
    st.caption(
        "BudgetFlow is a local, single-user project. No API keys, cloud services, or paid subscriptions are required."
    )
