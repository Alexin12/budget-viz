import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.categorize import CACHE_PATH, CATEGORIES
from src.pipeline import STATEMENTS_DIR, build_transactions

st.set_page_config(page_title="Budget Viz", layout="wide")

SPEND_CATEGORIES = [c for c in CATEGORIES if c != "transfer"]


@st.cache_data
def load(mtime_key):
    return build_transactions()


def latest_mtime(root: Path) -> float:
    files = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".csv"]
    return max((p.stat().st_mtime for p in files), default=0.0)


def write_overrides(updates: dict[str, str]) -> None:
    cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
    cache.update(updates)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))


df, paypal_dropped = load(latest_mtime(STATEMENTS_DIR))
df["date"] = pd.to_datetime(df["date"])
df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()

st.title("Budget Viz")

all_months = sorted(pd.Series(df["month"].dropna().unique()))
if not all_months:
    st.error("No transactions found in Card Statements/.")
    st.stop()

month_labels = [m.strftime("%Y-%m") for m in all_months]
default_start = month_labels[max(0, len(month_labels) - 6)]
default_end = month_labels[-1]

st.sidebar.header("Filters")
start_label, end_label = st.sidebar.select_slider(
    "Month range",
    options=month_labels,
    value=(default_start, default_end),
)
start_month = pd.Timestamp(start_label)
end_month = pd.Timestamp(end_label)

sources = sorted(df["source"].unique())
sel_sources = st.sidebar.multiselect("Sources", sources, default=sources)
sel_cats = st.sidebar.multiselect(
    "Categories", SPEND_CATEGORIES, default=SPEND_CATEGORIES
)
show_transfers = st.sidebar.checkbox("Include transfers in table", value=False)

base_mask = (
    (df["month"] >= start_month)
    & (df["month"] <= end_month)
    & (df["source"].isin(sel_sources))
)
in_range = df.loc[base_mask].copy()
spending = in_range[
    ~in_range["is_transfer"]
    & ~in_range["is_refund"]
    & in_range["category"].isin(sel_cats)
].copy()
transfers = in_range[in_range["is_transfer"]].copy()
refunds = in_range[in_range["is_refund"]].copy()

months_in_range = sorted(spending["month"].dropna().unique())
n_months = max(1, len(months_in_range))
total_spend = spending["amount"].sum()
avg_monthly = total_spend / n_months

k1, k2, k3 = st.columns(3)
k1.metric("Total spend", f"${total_spend:,.2f}")
k2.metric("Avg monthly spend", f"${avg_monthly:,.2f}")
k3.metric("Transactions", f"{len(spending):,}")

st.markdown("---")

per_cat_month = (
    spending.groupby(["month", "category"], as_index=False)["amount"].sum()
)

if not per_cat_month.empty:
    avg_by_cat = (
        per_cat_month.groupby("category", as_index=False)["amount"].sum()
    )
    avg_by_cat["amount"] = avg_by_cat["amount"] / n_months
    avg_by_cat = avg_by_cat.sort_values("amount", ascending=False)
    fig1 = px.bar(
        avg_by_cat,
        x="category",
        y="amount",
        title=f"Average monthly spend by category ({n_months} month(s))",
        labels={"amount": "$ per month"},
        text_auto=".2f",
    )
    fig1.update_layout(showlegend=False)
    st.plotly_chart(fig1, width='stretch')
else:
    st.info("No spending rows in the selected range.")

col_a, col_b = st.columns(2)
with col_a:
    if months_in_range:
        recent_month = months_in_range[-1]
        recent = spending[spending["month"] == recent_month]
        donut = recent.groupby("category", as_index=False)["amount"].sum()
        fig2 = px.pie(
            donut,
            names="category",
            values="amount",
            hole=0.5,
            title=f"Breakdown — {pd.Timestamp(recent_month).strftime('%b %Y')}",
        )
        st.plotly_chart(fig2, width='stretch')

with col_b:
    if not per_cat_month.empty:
        mom = per_cat_month.copy()
        mom["month_label"] = mom["month"].dt.strftime("%Y-%m")
        fig3 = px.bar(
            mom,
            x="month_label",
            y="amount",
            color="category",
            barmode="group",
            title="Month-over-month by category",
            labels={"month_label": "month", "amount": "$"},
        )
        st.plotly_chart(fig3, width='stretch')

if not per_cat_month.empty:
    fig4 = px.area(
        per_cat_month.sort_values("month"),
        x="month",
        y="amount",
        color="category",
        title="Spending over time (stacked)",
        labels={"amount": "$"},
    )
    st.plotly_chart(fig4, width='stretch')

with st.expander(f"Transfers panel ({len(transfers)} rows)", expanded=False):
    st.caption("Account-to-account moves. Excluded from spending totals.")
    if len(transfers):
        st.dataframe(
            transfers[["date", "source", "description", "amount", "transfer_layer"]]
            .sort_values("date", ascending=False),
            width='stretch',
            height=300,
        )

with st.expander(f"Refunds & credits ({len(refunds)} rows)", expanded=False):
    st.caption(
        "Paired refunds (both sides) plus standalone credits (negative non-transfer rows). "
        "Excluded from spending totals."
    )
    if len(refunds):
        st.dataframe(
            refunds[["date", "source", "description", "amount", "refund_pair_id"]]
            .sort_values(["refund_pair_id", "date"], ascending=[True, False]),
            width='stretch',
            height=300,
        )

with st.expander(f"PayPal dropped rows ({len(paypal_dropped)})", expanded=False):
    st.caption(
        "Rows removed before transfer tagging — internal accounting + cross-card duplicates."
    )
    if len(paypal_dropped):
        cols = [c for c in ["date", "description", "amount", "raw_type", "raw_status", "drop_reason"] if c in paypal_dropped.columns]
        st.dataframe(paypal_dropped[cols], width='stretch', height=300)

st.markdown("---")
st.subheader("Transactions")
st.caption("Edit the `category` cell to override. Click *Save overrides* to persist (writes to `data/category_cache.json`).")

table_src = in_range if show_transfers else spending
display_cols = ["date", "source", "description", "amount", "category", "signature"]
display = (
    table_src[display_cols]
    .sort_values("date", ascending=False)
    .reset_index(drop=True)
)

edited = st.data_editor(
    display,
    column_config={
        "date": st.column_config.DateColumn("date", disabled=True),
        "source": st.column_config.TextColumn("source", disabled=True),
        "description": st.column_config.TextColumn("description", disabled=True),
        "amount": st.column_config.NumberColumn("amount", disabled=True, format="$%.2f"),
        "category": st.column_config.SelectboxColumn(
            "category", options=CATEGORIES, required=True
        ),
        "signature": st.column_config.TextColumn("signature", disabled=True),
    },
    width='stretch',
    height=600,
    key="txn_editor",
    hide_index=True,
)

changed = edited["category"] != display["category"]
n_changed = int(changed.sum())
if n_changed:
    st.write(f"{n_changed} pending override(s).")
    if st.button("Save overrides"):
        updates: dict[str, str] = {}
        for _, row in edited[changed].iterrows():
            sig = row["signature"]
            if sig and row["category"] != "transfer":
                updates[sig] = row["category"]
        if updates:
            write_overrides(updates)
            st.cache_data.clear()
            st.success(f"Saved {len(updates)} override(s). Reloading…")
            st.rerun()
        else:
            st.warning("No saveable overrides (transfer rows are ignored).")
