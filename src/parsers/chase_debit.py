import csv
from pathlib import Path

import pandas as pd

from src.parsers import load_card_aliases

LAST4 = "8290"


def parse(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    df = pd.DataFrame(rows)
    df = df.rename(
        columns={
            "Posting Date": "date",
            "Description": "description",
            "Amount": "amount",
            "Type": "raw_type",
            "Details": "raw_details",
        }
    )
    df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y").dt.date
    df["amount"] = -df["amount"].astype(float)
    aliases = load_card_aliases()
    df["source"] = aliases.get(LAST4, f"chase_unknown_{LAST4}")
    return df[["date", "description", "amount", "source", "raw_type", "raw_details"]]
