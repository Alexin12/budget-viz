import pandas as pd


def parse(path):
    df = pd.read_csv(path)
    df = df.rename(
        columns={
            "Trans. Date": "date",
            "Description": "description",
            "Amount": "amount",
            "Category": "raw_category",
        }
    )
    df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y").dt.date
    df["amount"] = df["amount"].astype(float)
    df["source"] = "discover_credit"
    return df[["date", "description", "amount", "source", "raw_category"]]
