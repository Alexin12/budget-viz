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

df = load(latest_mtime(STATEMENTS_DIR))

c1, c2, c3 = st.columns(3)
c1.metric("Rows", f"{len(df):,}")
c2.metric("Sources", df["source"].nunique())
c3.metric("Date range", f"{df['date'].min()} → {df['date'].max()}")

st.subheader("Rows per source")
st.dataframe(df.groupby("source").size().rename("rows").reset_index())

st.subheader("All transactions")
st.dataframe(df, use_container_width=True, height=600)
