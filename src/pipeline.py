from pathlib import Path

import pandas as pd

from src.parsers import detect_parser

ROOT = Path(__file__).resolve().parents[1]
STATEMENTS_DIR = ROOT / "Card Statements"

CORE_COLUMNS = ["date", "description", "amount", "source"]


def build_transactions():
    frames = []
    for path in sorted(STATEMENTS_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() != ".csv":
            continue
        parser = detect_parser(path)
        if parser is None:
            continue
        frames.append(parser(path))
    if not frames:
        return pd.DataFrame(columns=CORE_COLUMNS)
    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values("date", ascending=False).reset_index(drop=True)
    return df
