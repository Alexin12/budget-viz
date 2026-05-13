from pathlib import Path

import streamlit as st

from src.pipeline import STATEMENTS_DIR, build_transactions

st.set_page_config(page_title="Budget Viz", layout="wide")


@st.cache_data
def load(mtime_key):
    return build_transactions()


def latest_mtime(root: Path):
    files = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".csv"]
    return max((p.stat().st_mtime for p in files), default=0.0)


st.title("Budget Viz — raw merged transactions")

df, paypal_dropped = load(latest_mtime(STATEMENTS_DIR))
spending = df[~df["is_transfer"]]
transfers = df[df["is_transfer"]]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total rows", f"{len(df):,}")
c2.metric("Spending rows", f"{len(spending):,}")
c3.metric("Transfer rows", f"{len(transfers):,}")
c4.metric("Sources", df["source"].nunique())

st.subheader("Rows per source")
per_source = (
    df.assign(kind=df["is_transfer"].map({True: "transfer", False: "spending"}))
    .pivot_table(index="source", columns="kind", values="amount", aggfunc="size", fill_value=0)
    .reset_index()
)
st.dataframe(per_source, use_container_width=True)

with st.expander(f"PayPal dropped rows ({len(paypal_dropped)}) — internal + cross-card", expanded=False):
    st.caption(
        "Rows removed before transfer tagging. `paypal_internal` = PayPal accounting noise "
        "(pending, card-deposit offsets, etc.). `paypal_cross_card` = duplicate of a card row "
        "with PAYPAL in the description."
    )
    if len(paypal_dropped):
        st.dataframe(
            paypal_dropped[["date", "description", "amount", "raw_type", "raw_status", "drop_reason"]],
            use_container_width=True,
            height=400,
        )
    else:
        st.write("No PayPal rows dropped.")

with st.expander(f"Transfers panel ({len(transfers)} rows) — sanity check", expanded=False):
    st.caption("Rows flagged as account-to-account moves. Excluded from spending totals.")
    st.dataframe(
        transfers[["date", "source", "description", "amount", "transfer_layer"]],
        use_container_width=True,
        height=400,
    )

st.subheader(f"Spending transactions ({len(spending):,} rows)")
show_transfers = st.checkbox("Include transfers in table", value=False)
table = df if show_transfers else spending
st.dataframe(table, use_container_width=True, height=600)
