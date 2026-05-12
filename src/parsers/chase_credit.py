import re
from pathlib import Path

import pandas as pd

from src.parsers import load_card_aliases

LAST4_RE = re.compile(r"Chase(\d{4})_")


def _source_from_filename(path):
    m = LAST4_RE.search(Path(path).name)
    if not m:
        raise ValueError(f"cannot extract last-4 from filename: {path}")
    last4 = m.group(1)
    aliases = load_card_aliases()
    return aliases.get(last4, f"chase_unknown_{last4}")


def parse(path):
    df = pd.read_csv(path)
    df = df.rename(
        columns={
            "Transaction Date": "date",
            "Description": "description",
            "Amount": "amount",
            "Type": "raw_type",
            "Category": "raw_category",
        }
    )
    df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y").dt.date
    df["amount"] = -df["amount"].astype(float)
    df["source"] = _source_from_filename(path)
    return df[["date", "description", "amount", "source", "raw_type", "raw_category"]]
