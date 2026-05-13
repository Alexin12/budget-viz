import json

import pandas as pd

from src.parsers import CONFIG_DIR

CROSS_HINT_TOKENS = [
    "CHASE",
    "SOFI",
    "DISCOVER",
    "AMEX",
    "AMERICAN EXPRESS",
    "JPMORGAN",
    "ROBINHOOD",
    "MOOMOO",
    "PAYPAL",
    "TRANSFER",
    "PAYMENT THANK YOU",
]


def load_rules():
    return json.loads((CONFIG_DIR / "transfer_rules.json").read_text())


def _layer1_mask(df, rules):
    mask = pd.Series(False, index=df.index)
    has_type = "raw_type" in df.columns
    for source, rule in rules.items():
        sub = df["source"] == source
        if not sub.any():
            continue
        type_list = rule.get("types", []) + rule.get("type_equals", [])
        if type_list and has_type:
            mask |= sub & df["raw_type"].isin(type_list)
        if has_type:
            for t, needles in rule.get("type_plus_description", {}).items():
                t_match = sub & (df["raw_type"] == t)
                for n in needles:
                    mask |= t_match & df["description"].str.contains(n, case=False, na=False)
        for n in rule.get("description_contains", []):
            mask |= sub & df["description"].str.contains(n, case=False, na=False)
    return mask


def _layer2_pairs(df, already_flagged):
    remaining = df[~already_flagged]
    pos = remaining[remaining["amount"] > 0]
    neg = remaining[remaining["amount"] < 0]
    pair_idx = set()
    used_neg = set()
    neg_rows = list(neg.itertuples())
    for p in pos.itertuples():
        p_date = pd.Timestamp(p.date)
        for n in neg_rows:
            if n.Index in used_neg:
                continue
            if n.source == p.source:
                continue
            if abs((p_date - pd.Timestamp(n.date)).days) > 3:
                continue
            if abs(p.amount + n.amount) > 0.01:
                continue
            combined = f"{p.description} {n.description}".upper()
            if not any(tok in combined for tok in CROSS_HINT_TOKENS):
                continue
            pair_idx.add(p.Index)
            pair_idx.add(n.Index)
            used_neg.add(n.Index)
            break
    return pair_idx


def tag_transfers(df):
    rules = load_rules()
    layer1 = _layer1_mask(df, rules)
    pair_idx = _layer2_pairs(df, layer1)
    layer2 = pd.Series(False, index=df.index)
    if pair_idx:
        layer2.loc[list(pair_idx)] = True
    is_transfer = layer1 | layer2
    df = df.copy()
    df["is_transfer"] = is_transfer
    df["transfer_layer"] = ""
    df.loc[layer1, "transfer_layer"] = "layer1"
    df.loc[layer2 & ~layer1, "transfer_layer"] = "layer2"
    df["category"] = ""
    df.loc[is_transfer, "category"] = "transfer"
    return df
