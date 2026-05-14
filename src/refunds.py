import re

import pandas as pd

from src.categorize import merchant_signature

WINDOW_DAYS = 60
AMOUNT_TOLERANCE = 0.01

STOP_TOKENS = {
    "PAYPAL", "PYPL", "PP", "AMZN", "AMAZON", "MKTPLACE", "MKTP", "PMTS",
    "INC", "LLC", "COM", "USA", "THE", "AND", "WWW", "ONLINE", "STORE",
    "PAYMENT", "PURCHASE", "REFUND", "CREDIT", "DEBIT", "RETURN",
}


def _tokens(description: str) -> set[str]:
    s = merchant_signature(description).upper()
    return {t for t in re.split(r"[^A-Z0-9]+", s) if len(t) >= 4 and t not in STOP_TOKENS}


def _same_merchant(a: str, b: str, src_a: str, src_b: str, sig_a: str, sig_b: str) -> bool:
    if src_a == src_b and sig_a == sig_b and sig_a != "":
        return True
    shared = _tokens(a) & _tokens(b)
    return bool(shared)


def tag_refunds(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "is_refund" not in df.columns:
        df["is_refund"] = False
    if "refund_pair_id" not in df.columns:
        df["refund_pair_id"] = ""

    work = df[~df["is_transfer"]].copy()
    work["signature"] = work["description"].map(merchant_signature)
    work["date_ts"] = pd.to_datetime(work["date"])

    pos = work[work["amount"] > 0].sort_values("date_ts")
    neg = work[work["amount"] < 0].sort_values("date_ts")
    neg_rows = list(neg.itertuples())

    paired = set()
    used_neg = set()
    pair_id = 0

    for p in pos.itertuples():
        if p.Index in paired:
            continue
        best = None
        best_dist = None
        for n in neg_rows:
            if n.Index in used_neg:
                continue
            if abs(p.amount + n.amount) > AMOUNT_TOLERANCE:
                continue
            dist = abs((p.date_ts - n.date_ts).days)
            if dist > WINDOW_DAYS:
                continue
            if not _same_merchant(p.description, n.description, p.source, n.source, p.signature, n.signature):
                continue
            if best is None or dist < best_dist:
                best = n
                best_dist = dist
        if best is not None:
            pair_id += 1
            tag = f"pair-{pair_id}"
            df.at[p.Index, "is_refund"] = True
            df.at[best.Index, "is_refund"] = True
            df.at[p.Index, "refund_pair_id"] = tag
            df.at[best.Index, "refund_pair_id"] = tag
            paired.add(p.Index)
            used_neg.add(best.Index)

    standalone = (~df["is_transfer"]) & (df["amount"] < 0) & (~df["is_refund"])
    df.loc[standalone, "is_refund"] = True
    return df
