import csv
from pathlib import Path

import pandas as pd


def _source_from_filename(path):
    name = Path(path).name
    if "JointChecking" in name:
        return "sofi_checking"
    if "JointSavings" in name:
        return "sofi_savings"
    raise ValueError(f"cannot determine sofi source from filename: {path}")


def parse(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    df = pd.DataFrame(rows)
    df = df.rename(
        columns={
            "Date": "date",
            "Description": "description",
            "Type": "raw_type",
        }
    )
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d").dt.date
    df["amount"] = -df["Amount"].astype(float)
    df["source"] = _source_from_filename(path)
    return df[["date", "description", "amount", "source", "raw_type"]]
