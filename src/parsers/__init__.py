import json
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def load_card_aliases():
    return json.loads((CONFIG_DIR / "card_aliases.json").read_text())


def detect_parser(path):
    from src.parsers import (
        amex,
        chase_credit,
        chase_debit,
        discover_credit,
        discover_debit,
        paypal,
        sofi,
    )

    name = Path(path).name
    if name.startswith("Chase3209_") or name.startswith("Chase5878_"):
        return chase_credit.parse
    if name.startswith("Chase8290_"):
        return chase_debit.parse
    if name.startswith("Discover-Last12Months"):
        return discover_credit.parse
    if name.startswith("Debt-"):
        return discover_debit.parse
    if name == "activity.csv":
        return amex.parse
    if name == "Download.CSV":
        return paypal.parse
    if name.startswith("SOFI-Joint"):
        return sofi.parse
    return None
