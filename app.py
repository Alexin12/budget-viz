import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
month_mode = st.sidebar.radio(
    "Month filter mode",
    options=["Range", "Pick months"],
    horizontal=True,
)

if month_mode == "Range":
    start_label, end_label = st.sidebar.select_slider(
        "Month range",
        options=month_labels,
        value=(default_start, default_end),
    )
    start_month = pd.Timestamp(start_label)
    end_month = pd.Timestamp(end_label)
    selected_months = [
        pd.Timestamp(m) for m in month_labels
        if start_month <= pd.Timestamp(m) <= end_month
    ]
else:
    default_picks = month_labels[max(0, len(month_labels) - 6):]
    picked_labels = st.sidebar.multiselect(
        "Months",
        options=month_labels,
        default=default_picks,
    )
    if not picked_labels:
        st.warning("Select at least one month.")
        st.stop()
    selected_months = [pd.Timestamp(m) for m in picked_labels]

sources = sorted(df["source"].unique())
sel_sources = st.sidebar.multiselect("Sources", sources, default=sources)
sel_cats = st.sidebar.multiselect(
    "Categories", SPEND_CATEGORIES, default=SPEND_CATEGORIES
)
show_transfers = st.sidebar.checkbox("Include transfers in table", value=False)
monthly_budget = st.sidebar.number_input(
    "Monthly budget ($)", min_value=0, value=0, step=100,
    help="0 = hide budget line on the monthly trend chart.",
)

base_mask = (
    df["month"].isin(selected_months)
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

monthly_total = (
    spending.groupby("month", as_index=False)["amount"].sum().sort_values("month")
)
if not monthly_total.empty:
    fig_trend = go.Figure()
    fig_trend.add_trace(
        go.Scatter(
            x=monthly_total["month"],
            y=monthly_total["amount"],
            mode="lines+markers",
            name="Monthly spend",
            line=dict(width=3),
            hovertemplate="%{x|%b %Y}<br>$%{y:,.2f}<extra></extra>",
        )
    )
    if monthly_budget > 0:
        fig_trend.add_hline(
            y=monthly_budget,
            line_dash="dash",
            line_color="crimson",
            annotation_text=f"Budget ${monthly_budget:,}",
            annotation_position="top right",
        )
    fig_trend.update_layout(
        title="Monthly total spending",
        xaxis_title="Month",
        yaxis_title="$",
        yaxis_tickformat="$,.0f",
        height=380,
    )
    st.plotly_chart(fig_trend, width='stretch')

    cat_avg = (
        spending.groupby("category", as_index=False)["amount"].sum()
    )
    cat_avg["avg"] = cat_avg["amount"] / n_months
    cat_avg = cat_avg[cat_avg["avg"] > 0].sort_values("avg", ascending=False)
    if not cat_avg.empty:
        fig_cat_avg = px.scatter(
            cat_avg,
            x="category",
            y="avg",
            size="avg",
            color="category",
            size_max=40,
            title=f"Average monthly spending by category ({n_months} month{'s' if n_months != 1 else ''})",
        )
        fig_cat_avg.update_traces(
            hovertemplate="%{x}<br>Avg: $%{y:,.2f}/mo<extra></extra>",
        )
        fig_cat_avg.update_xaxes(
            title=None,
            categoryorder="array",
            categoryarray=cat_avg["category"].tolist(),
        )
        fig_cat_avg.update_yaxes(tickformat="$,.0f", title="Avg $/month")
        fig_cat_avg.update_layout(height=380, showlegend=False)
        st.plotly_chart(fig_cat_avg, width='stretch')

st.markdown("---")

# Chart 2 — Category Breakdown (stacked bar, top 6 + other)
if spending.empty:
    st.info("No spending data in the selected range.")
else:
    monthly_cat = (
        spending.groupby(["month", "category"], as_index=False)["amount"].sum()
    )
    totals = (
        monthly_cat.groupby("category")["amount"].sum().sort_values(ascending=False)
    )
    top_n = 6
    major = set(totals.head(top_n).index)
    other_cats = [c for c in totals.index if c not in major]
    monthly_cat["category"] = monthly_cat["category"].where(
        monthly_cat["category"].isin(major), "other"
    )
    monthly_cat = (
        monthly_cat.groupby(["month", "category"], as_index=False)["amount"].sum()
    )
    monthly_cat = monthly_cat.sort_values("month")
    monthly_cat["month_label"] = monthly_cat["month"].dt.strftime("%Y-%m")
    month_totals = monthly_cat.groupby("month")["amount"].transform("sum")
    monthly_cat["pct"] = monthly_cat["amount"] / month_totals * 100
    monthly_cat["pct_label"] = monthly_cat["pct"].map(lambda p: f"{p:.1f}%")
    month_order = (
        monthly_cat.sort_values("month")["month_label"].drop_duplicates().tolist()
    )
    category_order = [c for c in totals.head(top_n).index if c in major]
    if (monthly_cat["category"] == "other").any():
        category_order.append("other")
    fig_stack = px.bar(
        monthly_cat,
        x="month_label",
        y="amount",
        color="category",
        barmode="stack",
        title="Monthly spending by category (top 6 + other)",
        category_orders={"month_label": month_order, "category": category_order},
        text="pct_label",
        custom_data=["pct"],
    )
    fig_stack.update_traces(
        textposition="inside",
        insidetextanchor="middle",
        textfont_size=11,
        hovertemplate=(
            "%{x}<br>%{fullData.name}: $%{y:,.2f} "
            "(%{customdata[0]:.1f}%)<extra></extra>"
        ),
    )
    fig_stack.update_yaxes(tickformat="$,.0f", title="Spending")
    fig_stack.update_xaxes(title="Month")
    fig_stack.update_layout(legend_title_text="Category", uniformtext_minsize=8, uniformtext_mode="hide")
    st.plotly_chart(fig_stack, width='stretch')
    if other_cats:
        other_totals = totals.loc[other_cats]
        other_note = ", ".join(
            f"{c}: \\${v:,.2f}" for c, v in other_totals.items()
        )
        st.caption(f"**Other** includes: {other_note}")
    else:
        st.caption("**Other** is empty — all categories fit in the top 6.")

st.markdown("---")

# Chart 3 — Top Categories (horizontal bar, 3/6/12-month lookback)
window = st.radio(
    "Lookback window",
    options=[3, 6, 12],
    index=1,
    horizontal=True,
    format_func=lambda n: f"{n} months",
    key="top_categories_window",
)

anchor = df["month"].max()
if pd.isna(anchor):
    st.info("No data available for top categories.")
else:
    start = (anchor - pd.DateOffset(months=window - 1)).to_period("M").to_timestamp()
    window_df = df[
        (df["month"] >= start)
        & (df["month"] <= anchor)
        & (df["source"].isin(sel_sources))
        & (~df["is_transfer"])
        & (~df["is_refund"])
    ]
    if window_df.empty:
        st.info(f"No spending in the last {window} months for the selected sources.")
    else:
        by_cat = (
            window_df.groupby("category", as_index=False)["amount"]
            .sum()
            .sort_values("amount", ascending=False)
        )
        by_cat = by_cat[by_cat["amount"] > 0]
        if by_cat.empty:
            st.info(f"No positive spending in the last {window} months.")
        else:
            fig_top = px.bar(
                by_cat,
                x="amount",
                y="category",
                orientation="h",
                text_auto="$,.0f",
                title=f"Top categories — last {window} months",
            )
            fig_top.update_yaxes(categoryorder="total ascending", title=None)
            fig_top.update_xaxes(tickformat="$,.0f", title="Spending")
            fig_top.update_traces(textposition="outside", cliponaxis=False)
            st.plotly_chart(fig_top, width='stretch')

st.markdown("---")

# Chart 4 — Category Trend (multi-line)
focus_options = [c for c in CATEGORIES if c != "transfer"]
default_focus = [
    c for c in ["shopping", "dining", "entertainment", "transportation", "grocery"]
    if c in focus_options
]
selected_focus = st.multiselect(
    "Focus categories",
    options=focus_options,
    default=default_focus,
    key="chart4_focus_categories",
)
focus_df = spending[spending["category"].isin(selected_focus)]
if focus_df.empty or not selected_focus:
    st.info("No spending in the selected focus categories for this range.")
else:
    trend = (
        focus_df.groupby(["month", "category"], as_index=False)["amount"]
        .sum()
        .sort_values("month")
    )
    fig_trend_cat = px.line(
        trend,
        x="month",
        y="amount",
        color="category",
        markers=True,
        title="Category trend over time",
    )
    fig_trend_cat.update_yaxes(tickformat="$,.0f", title="Spending")
    fig_trend_cat.update_xaxes(type="date", title="Month")
    st.plotly_chart(fig_trend_cat, width='stretch')

st.markdown("---")

# Chart 5 — Budget vs Actual (grouped horizontal bar)
st.subheader("Budget vs actual")

budget_path = Path("config/category_budgets.json")
budgets = json.loads(budget_path.read_text()) if budget_path.exists() else {}

with st.expander("Edit category budgets"):
    editor_df = pd.DataFrame(
        {
            "category": list(SPEND_CATEGORIES),
            "monthly_budget": [float(budgets.get(c, 0)) for c in SPEND_CATEGORIES],
        }
    )
    budget_edited = st.data_editor(
        editor_df,
        column_config={
            "category": st.column_config.TextColumn("category", disabled=True),
            "monthly_budget": st.column_config.NumberColumn(
                "monthly_budget", min_value=0.0, step=10.0, format="$%.0f"
            ),
        },
        hide_index=True,
        width='stretch',
        key="budget_editor",
    )
    if st.button("Save budgets"):
        new_budgets = {
            row["category"]: float(row["monthly_budget"])
            for _, row in budget_edited.iterrows()
        }
        budget_path.parent.mkdir(parents=True, exist_ok=True)
        budget_path.write_text(json.dumps(new_budgets, indent=2))
        st.cache_data.clear()
        st.rerun()

if spending.empty:
    st.info("No spending in the selected range — Budget vs Actual chart skipped.")
else:
    actuals = (
        spending.groupby("category")["amount"].sum() / n_months
    ).reindex(SPEND_CATEGORIES, fill_value=0.0)
    chart_df = pd.DataFrame(
        {
            "category": list(SPEND_CATEGORIES),
            "Budget": [float(budgets.get(c, 0)) for c in SPEND_CATEGORIES],
            "Actual": actuals.values,
        }
    )
    chart_df = chart_df.sort_values("Actual", ascending=True)
    category_order_ba = chart_df["category"].tolist()
    long_df = chart_df.melt(
        id_vars="category",
        value_vars=["Budget", "Actual"],
        var_name="series",
        value_name="amount",
    )
    fig_ba = px.bar(
        long_df,
        x="amount",
        y="category",
        color="series",
        orientation="h",
        barmode="group",
        text_auto="$,.0f",
        title="Budget vs actual (monthly average)",
        category_orders={"category": category_order_ba, "series": ["Budget", "Actual"]},
        color_discrete_map={"Budget": "#9CA3AF", "Actual": "#2563EB"},
    )
    fig_ba.update_xaxes(tickformat="$,.0f", title="Monthly $")
    fig_ba.update_yaxes(title="")
    fig_ba.update_layout(
        legend_title_text="",
        height=max(360, 32 * len(category_order_ba) + 120),
    )
    st.plotly_chart(fig_ba, width='stretch')

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
table_src = table_src[display_cols].sort_values("date", ascending=False).reset_index(drop=True)

month_series = table_src["date"].dt.strftime("%Y-%m")
month_options = sorted(month_series.unique().tolist(), reverse=True)
source_options = sorted(table_src["source"].dropna().unique().tolist())
category_options = sorted(table_src["category"].dropna().unique().tolist())

fc1, fc2, fc3 = st.columns(3)
with fc1:
    sel_months = st.multiselect("Month", month_options, default=[], placeholder="All months")
with fc2:
    sel_sources = st.multiselect("Source", source_options, default=[], placeholder="All sources")
with fc3:
    sel_categories = st.multiselect("Category", category_options, default=[], placeholder="All categories")

mask = pd.Series(True, index=table_src.index)
if sel_months:
    mask &= month_series.isin(sel_months)
if sel_sources:
    mask &= table_src["source"].isin(sel_sources)
if sel_categories:
    mask &= table_src["category"].isin(sel_categories)

display = table_src[mask].reset_index(drop=True)
total_amount = float(display["amount"].sum())
st.markdown(
    f"<div style='color:#9aa0a6;font-size:0.875rem;'>Showing {len(display):,} of {len(table_src):,} rows · "
    f"Total: <span style='color:#22c55e;font-weight:600;'>${total_amount:,.2f}</span></div>",
    unsafe_allow_html=True,
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
