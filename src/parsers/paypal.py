import csv

import pandas as pd


def parse(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    df = pd.DataFrame(rows)
    df = df.rename(
        columns={
            "Date": "date",
            "Name": "description",
            "Type": "raw_type",
            "Status": "raw_status",
        }
    )
    df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y").dt.date
    df["amount"] = -df["Amount"].str.replace(",", "", regex=False).astype(float)
    df["source"] = "paypal"
    return df[["date", "description", "amount", "source", "raw_type", "raw_status"]]
