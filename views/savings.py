from datetime import date, timedelta

import pandas as pd
import streamlit as st

from utils.calculations import amount_text, money
from utils.ui import action, currency, db, heading, metrics
from utils.validators import to_paise


def render():
    heading(
        "Make room for your next chapter.",
        "Turn a wish into a goal, one contribution at a time.",
        "",
    )
    code = currency()
    goals = db().goals()
    metrics(
        [
            (
                "Goal contributions",
                money(sum(goal["saved_paise"] for goal in goals), code),
                "All recorded contributions, independent of income and expense calculations.",
            ),
            (
                "Active goals",
                str(sum(not goal["completed"] for goal in goals)),
                "Goals not yet marked complete.",
            ),
            (
                "Completed goals",
                str(sum(bool(goal["completed"]) for goal in goals)),
                "Goals explicitly completed after reaching the target.",
            ),
        ]
    )
    st.info(
        "Contributions are allocation records, not new income or expenses. They never deduct from your balance. If you spend money to buy a goal item, record that purchase as an expense.",
        icon=":material/info:",
    )
    with st.expander("Create a savings goal", expanded=not goals):
        with st.form("new_goal", clear_on_submit=True):
            name = st.text_input(
                "Goal name", max_chars=80, placeholder="e.g. New laptop"
            )
            first, second = st.columns(2)
            target = first.text_input(
                f"Target amount ({code})", placeholder="60000.00"
            )
            target_date = second.date_input(
                "Target date", value=date.today() + timedelta(days=90)
            )
            if st.form_submit_button("Create goal", type="primary"):
                action(
                    lambda: db().add_goal(name, to_paise(target), target_date),
                    "Savings goal created.",
                )
    if not goals:
        st.info(
            "Your first goal starts here. Create one above to track your progress."
        )
        return
    for goal in goals:
        with st.container(border=True):
            first, second = st.columns([3, 1])
            first.subheader(goal["name"], anchor=False)
            second.badge(
                "Completed" if goal["completed"] else "Active",
                color="green" if goal["completed"] else "blue",
            )
            percent = goal["saved_paise"] / goal["target_paise"] * 100
            st.progress(
                min(percent / 100, 1.0),
                text=f"{money(goal['saved_paise'], code)} of {money(goal['target_paise'], code)} · {percent:.1f}%",
            )
            remaining = max(goal["target_paise"] - goal["saved_paise"], 0)
            st.caption(
                f"Target date: {goal['target_date']} · Still to save: {money(remaining, code)}"
            )
            if (
                date.fromisoformat(goal["target_date"]) < date.today()
                and remaining > 0
            ):
                st.warning(
                    "The target date has passed. You can update it in Manage goal."
                )
            with st.expander("Contribute & view history"):
                if not goal["completed"]:
                    with st.form(
                        f"contribute_{goal['id']}", clear_on_submit=True
                    ):
                        amount = st.text_input(
                            f"Contribution ({code})",
                            key=f"contribution_amount_{goal['id']}",
                        )
                        when = st.date_input(
                            "Contribution date",
                            value=date.today(),
                            key=f"contribution_date_{goal['id']}",
                        )
                        note = st.text_input(
                            "Note",
                            max_chars=500,
                            key=f"contribution_note_{goal['id']}",
                        )
                        if st.form_submit_button(
                            "Add contribution", type="primary"
                        ):
                            action(
                                lambda: db().add_contribution(
                                    goal["id"], to_paise(amount), when, note
                                ),
                                "Contribution recorded.",
                            )
                history = db().contributions(goal["id"])
                if history:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "ID": row["id"],
                                    "Date": row["contribution_date"],
                                    "Amount": money(row["amount_paise"], code),
                                    "Note": row["note"],
                                    "Source": "Demo"
                                    if row["is_demo"]
                                    else "Personal",
                                }
                                for row in history
                            ]
                        ),
                        hide_index=True,
                        width="stretch",
                    )
                    lookup = {row["id"]: row for row in history}
                    contribution = st.selectbox(
                        "Contribution to correct",
                        list(lookup),
                        format_func=lambda value: (
                            f"#{value} · {lookup[value]['contribution_date']} · {money(lookup[value]['amount_paise'], code)}"
                        ),
                        key=f"correct_contribution_{goal['id']}",
                    )
                    confirmed = st.checkbox(
                        "Confirm removal of this contribution.",
                        key=f"remove_contribution_confirm_{goal['id']}_{contribution}",
                    )
                    if st.button(
                        "Remove contribution",
                        key=f"remove_contribution_{goal['id']}",
                        disabled=not confirmed,
                    ):
                        action(
                            lambda: db().delete_contribution(contribution),
                            "Contribution removed; goal reopened.",
                        )
                else:
                    st.caption("No contributions yet.")
            with st.expander("Manage goal"):
                with st.form(f"edit_goal_{goal['id']}"):
                    name = st.text_input(
                        "Goal name", value=goal["name"], max_chars=80
                    )
                    target = st.text_input(
                        f"Target amount ({code})",
                        value=amount_text(goal["target_paise"]),
                    )
                    when = st.date_input(
                        "Target date",
                        value=date.fromisoformat(goal["target_date"]),
                    )
                    if st.form_submit_button("Update goal"):
                        action(
                            lambda: db().update_goal(
                                goal["id"], name, to_paise(target), when
                            ),
                            "Goal updated.",
                        )
                if st.button(
                    "Reopen goal" if goal["completed"] else "Mark completed",
                    key=f"complete_{goal['id']}",
                    disabled=not goal["completed"] and remaining > 0,
                ):
                    action(
                        lambda: db().complete_goal(
                            goal["id"], not goal["completed"]
                        ),
                        "Goal status updated.",
                    )
                confirmed = st.checkbox(
                    "Delete this goal and all its contributions.",
                    key=f"delete_goal_confirm_{goal['id']}",
                )
                if st.button(
                    "Delete goal",
                    disabled=not confirmed,
                    key=f"delete_goal_{goal['id']}",
                ):
                    action(
                        lambda: db().delete_goal(goal["id"]), "Goal deleted."
                    )
