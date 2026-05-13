import csv

import pandas as pd


def _money(s):
    s = s.strip().lstrip("$").replace(",", "")
    if s == "" or s == "0":
        return 0.0
    return float(s)


def parse(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    df = pd.DataFrame(rows)
    df = df.rename(
        columns={
            "Transaction Date": "date",
            "Transaction Description": "description",
            "Transaction Type": "raw_type",
        }
    )
    df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y").dt.date
    debit = df["Debit"].map(_money)
    credit = df["Credit"].map(_money)
    df["amount"] = debit.where(debit > 0, -credit)
    df["source"] = "discover_debit"
    return df[["date", "description", "amount", "source", "raw_type"]]
