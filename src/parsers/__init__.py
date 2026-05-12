import json
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def load_card_aliases():
    return json.loads((CONFIG_DIR / "card_aliases.json").read_text())
