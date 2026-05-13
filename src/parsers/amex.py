import pandas as pd


def parse(path):
    df = pd.read_csv(path)
    df = df.rename(
        columns={
            "Date": "date",
            "Description": "description",
            "Amount": "amount",
        }
    )
    df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y").dt.date
    df["amount"] = df["amount"].astype(float)
    df["source"] = "amex"
    return df[["date", "description", "amount", "source"]]
