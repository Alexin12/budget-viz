import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.parsers import chase_credit

SAPPHIRE = ROOT / "Card Statements" / "Chase" / "Chase3209_Activity20240512_20260512_20260512.CSV"
FLEX = ROOT / "Card Statements" / "Chase" / "Chase5878_Activity20240512_20260512_20260512.CSV"


def test_sapphire():
    df = chase_credit.parse(SAPPHIRE)
    assert len(df) == 147, f"expected 147 rows, got {len(df)}"
    assert (df["source"] == "chase_sapphire").all()

    doordash = df[(df["date"] == dt.date(2026, 5, 9)) & (df["description"].str.contains("DOORDASH"))]
    assert len(doordash) == 1
    assert doordash.iloc[0]["amount"] == 34.80, f"DoorDash expected +34.80, got {doordash.iloc[0]['amount']}"

    payment = df[(df["date"] == dt.date(2026, 5, 6)) & (df["raw_type"] == "Payment")]
    assert len(payment) == 1
    assert payment.iloc[0]["amount"] == -7.98, f"Payment expected -7.98, got {payment.iloc[0]['amount']}"


def test_freedom_flex():
    df = chase_credit.parse(FLEX)
    assert len(df) == 576, f"expected 576 rows, got {len(df)}"
    assert (df["source"] == "chase_freedom_flex").all()

    target = df[(df["date"] == dt.date(2026, 5, 9)) & (df["description"].str.contains("TARGET"))]
    assert len(target) == 1
    assert target.iloc[0]["amount"] == 43.75

    payment_4000 = df[(df["date"] == dt.date(2026, 5, 7)) & (df["raw_type"] == "Payment")]
    assert len(payment_4000) == 1
    assert payment_4000.iloc[0]["amount"] == -4000.00


if __name__ == "__main__":
    test_sapphire()
    test_freedom_flex()
    print("all tests passed")
