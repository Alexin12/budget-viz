import pandas as pd

CARD_SOURCES = [
    "chase_sapphire",
    "chase_freedom_flex",
    "chase_debit",
    "discover_credit",
    "discover_debit",
    "amex",
]

KEEP_TYPES = {
    "PreApproved Payment Bill User Payment",
    "Express Checkout Payment",
    "General Payment",
    "General PayPal Debit Card Transaction",
    "Payment Refund",
    "General Authorization",
    "General GI/Open wallet Transaction",
}


def _internal_filter(pp: pd.DataFrame) -> pd.DataFrame:
    # Rule 1: drop Pending
    pp = pp[pp["raw_status"] != "Pending"].copy()
    # Rule 2: drop General Card Deposit
    pp = pp[pp["raw_type"] != "General Card Deposit"]
    # Rule 4: drop Bank Deposit to PP Account (handled by transfer pairing instead)
    pp = pp[~pp["raw_type"].str.strip().eq("Bank Deposit to PP Account")]
    # Rule 3: drop General Card Withdrawal paired same-day/same-amount with a Payment Refund
    refunds = pp[pp["raw_type"] == "Payment Refund"][["date", "amount"]]
    refund_keys = set(zip(refunds["date"], refunds["amount"].round(2).map(lambda v: -v)))
    is_withdrawal = pp["raw_type"] == "General Card Withdrawal"
    key_match = pd.Series(
        [(d, round(a, 2)) in refund_keys for d, a in zip(pp["date"], pp["amount"])],
        index=pp.index,
    )
    paired_mask = is_withdrawal & key_match
    pp = pp[~paired_mask]
    # Keep only known merchant-bearing types (drops General Authorization holds, reversals, voids)
    pp = pp[pp["raw_type"].isin(KEEP_TYPES)]
    # Drop General Authorization rows when a same-day/same-amount settlement row exists
    # (Authorization is the pre-auth hold; settlement types are the actual money movement)
    settle_types = {
        "Express Checkout Payment",
        "General Payment",
        "PreApproved Payment Bill User Payment",
        "General PayPal Debit Card Transaction",
    }
    settled = pp[pp["raw_type"].isin(settle_types)]
    settled_keys = set(zip(settled["date"], settled["amount"].round(2)))
    is_auth = pp["raw_type"] == "General Authorization"
    auth_match = pd.Series(
        [(d, round(a, 2)) in settled_keys for d, a in zip(pp["date"], pp["amount"])],
        index=pp.index,
    )
    pp = pp[~(is_auth & auth_match)]
    return pp


def dedup(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply PayPal internal filters and cross-card dedup.

    Returns (cleaned_df, dropped_paypal_df). dropped_paypal_df is for the
    sanity-check panel — rows removed by internal filters or cross-card matches.
    """
    if "source" not in df.columns or not (df["source"] == "paypal").any():
        return df, df.iloc[0:0].copy()

    pp_all = df[df["source"] == "paypal"].copy()
    others = df[df["source"] != "paypal"].copy()

    kept = _internal_filter(pp_all)
    internal_dropped = pp_all.loc[~pp_all.index.isin(kept.index)].copy()
    internal_dropped["drop_reason"] = "paypal_internal"

    # Cross-card dedup: drop PayPal expense rows that match a card PAYPAL row
    cards = others[others["source"].isin(CARD_SOURCES)].copy()
    cards = cards[
        cards["description"].str.contains("PAYPAL", case=False, na=False)
        | cards["description"].str.contains("PP*", case=False, na=False, regex=False)
    ]
    card_rows = [
        (pd.Timestamp(d), round(abs(a), 2)) for d, a in zip(cards["date"], cards["amount"])
    ]

    drop_idx = []
    for idx, row in kept.iterrows():
        if row["amount"] <= 0:
            continue  # only dedup expenses
        d = pd.Timestamp(row["date"])
        target = round(abs(row["amount"]), 2)
        for cd, ca in card_rows:
            if abs((d - cd).days) <= 3 and ca == target:
                drop_idx.append(idx)
                break

    cross_dropped = kept.loc[drop_idx].copy()
    cross_dropped["drop_reason"] = "paypal_cross_card"
    kept = kept.drop(index=drop_idx)

    cleaned = pd.concat([others, kept], ignore_index=False).sort_values("date", ascending=False).reset_index(drop=True)
    dropped = pd.concat([internal_dropped, cross_dropped], ignore_index=False).sort_values("date", ascending=False).reset_index(drop=True)
    return cleaned, dropped
