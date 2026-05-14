import json
import os
import re
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "data" / "category_cache.json"

CATEGORIES = [
    "grocery",
    "gas",
    "shopping",
    "travel",
    "dining",
    "utilities",
    "entertainment",
    "housing",
    "taxes",
    "car",
    "ai",
    "other",
]

MODEL = "gpt-4o-mini"
BATCH_SIZE = 50

NOISE_PATTERNS = [
    r"^ACH WITHDRAWAL\s+",
    r"^ACH DEPOSIT\s+",
    r"APPLE PAY ENDING IN \d+",
    r"APLPAY",
    r"PPD ID:\s*\w+",
    r"WEB ID:\s*\w+",
    r"CO ID:\s*\w+",
    r"REF #?\s*\w+",
    r"PURCHASE AUTHORIZED ON \d{2}/\d{2}",
    r"\b\d{2}/\d{2}(/\d{2,4})?\b",
    r"\b\d{3}-\d{3}-\d{4}\b",
    r"\b800-\d{3}-\d{4}\b",
    r"#\s*\d{4,}",
    r"\bX{2,}\d+\b",
    r"\b[A-Z]{1,3}\d[A-Z0-9]{4,}\b",
    r"\b\d{6,}\b",
    r"\s[A-Z]{2}\s*$",
]


def merchant_signature(description: str) -> str:
    s = str(description or "").upper().strip()
    for pat in NOISE_PATTERNS:
        s = re.sub(pat, " ", s)
    s = re.sub(r"[*#]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    return json.loads(CACHE_PATH.read_text())


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))


def _client() -> OpenAI:
    load_dotenv(ROOT / ".env")
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def _classify_batch(client: OpenAI, signatures: list[str]) -> dict[str, str]:
    cat_list = ", ".join(CATEGORIES)
    user = (
        "Classify each merchant signature into one of these categories: "
        f"{cat_list}.\n"
        "Rules:\n"
        "- rent / mortgage / property management / HOA -> housing\n"
        "- IRS / state tax / franchise tax -> taxes\n"
        "- electricity / water / internet / phone / home insurance / auto insurance (GEICO, State Farm, Progressive) -> utilities\n"
        "- restaurants / coffee / fast food / food delivery (DoorDash, UberEats) -> dining\n"
        "- supermarkets / Whole Foods / Trader Joe's / Publix / Costco food / Aldi / Tony Food Market -> grocery\n"
        "- gas stations / EV charging / Shell / Circle K / Chevron / 7-Eleven gas -> gas\n"
        "- flights / hotels / Airbnb / Uber / Lyft / transit / MTA / parking -> travel\n"
        "- Netflix / Spotify / Kindle / Kindle Unlimited / Audible / streaming / YouTube Premium / Google One / video games / PlayStation / concerts (Ticketmaster, StubHub, Vivid Seats) / cinema (AMC) / Patreon / Apple Services / Apple.com (App Store, iCloud, Apple Music, Apple TV) / Udemy / online courses / museums / theaters / gym / tennis -> entertainment\n"
        "- Amazon / Target / Walmart / clothing / electronics retail / CVS / Walgreens -> shopping\n"
        "- car loans (Mazda Financial, Toyota Financial), auto insurance (GEICO, Progressive, State Farm Auto), auto repair, parts (Advance Auto, AutoZone), DMV / tag / license -> car\n"
        "- AI services and developer APIs ONLY: Anthropic, Claude, OpenAI, ChatGPT, OpenRouter, Cursor, Perplexity, Immersive Translate, GitHub Copilot. Do NOT put Apple Services, Kindle, Spotify, YouTube, Google One, or Udemy here -> ai\n"
        "- anything unclear -> other\n"
        "Return strict JSON: an object mapping each input signature (exact string) to its category.\n\n"
        "Signatures:\n" + "\n".join(f"- {s}" for s in signatures)
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": user}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    data = json.loads(resp.choices[0].message.content)
    out = {}
    for sig in signatures:
        cat = data.get(sig)
        if cat not in CATEGORIES:
            cat = "other"
        out[sig] = cat
    return out


def categorize(df: pd.DataFrame, dry_run: bool = False) -> pd.DataFrame:
    df = df.copy()
    if "category" not in df.columns:
        df["category"] = ""
    df["signature"] = df["description"].map(merchant_signature)

    needs_llm_mask = (~df["is_transfer"]) & (df["category"] == "")
    cache = load_cache()

    df.loc[needs_llm_mask, "category"] = df.loc[needs_llm_mask, "signature"].map(
        lambda s: cache.get(s, "")
    )

    uncached = sorted(
        set(df.loc[needs_llm_mask & (df["category"] == ""), "signature"]) - {""}
    )

    if uncached and not dry_run:
        client = _client()
        for i in range(0, len(uncached), BATCH_SIZE):
            batch = uncached[i : i + BATCH_SIZE]
            result = _classify_batch(client, batch)
            cache.update(result)
        save_cache(cache)
        df.loc[needs_llm_mask & (df["category"] == ""), "category"] = df.loc[
            needs_llm_mask & (df["category"] == ""), "signature"
        ].map(lambda s: cache.get(s, "other"))

    df.loc[df["is_transfer"], "category"] = "transfer"
    df.loc[df["category"] == "", "category"] = "other"
    return df
