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
    "dining",
    "shopping",
    "travel",
    "entertainment",
    "health",
    "housing",
    "transportation",
    "education",
    "personal",
    "taxes",
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


def has_api_key() -> bool:
    load_dotenv(ROOT / ".env")
    return bool(os.environ.get("OPENAI_API_KEY"))


def _classify_batch(client: OpenAI, signatures: list[str]) -> dict[str, str]:
    cat_list = ", ".join(CATEGORIES)
    user = (
        "Classify each merchant signature into one of these categories: "
        f"{cat_list}.\n"
        "Rules:\n"
        "- supermarkets / Whole Foods / Trader Joe's / Publix / Costco food / Aldi / Tony Food Market -> grocery\n"
        "- restaurants / coffee / fast food / food delivery (DoorDash, UberEats) / vending machines (Coca Cola, CPI R&R Vending, PMUSA) -> dining\n"
        "- Amazon / Target / Walmart / clothing / electronics retail / CVS / Walgreens / general retail / office furniture / home goods -> shopping\n"
        "- flights / hotels / Airbnb / Uber / Lyft / transit / MTA / parking / tickets for trips outside Pensacola / theme parks / museums OUTSIDE Pensacola -> travel\n"
        "- Netflix / Spotify / Kindle / Kindle Unlimited / Audible / streaming / YouTube Premium / Google One / video games / PlayStation / concerts (Ticketmaster, StubHub, Vivid Seats) / cinema (AMC) / Patreon / Apple Services / Apple.com (App Store, iCloud, Apple Music, Apple TV) / WSJ / news subscriptions / Medium / gym / tennis -> entertainment\n"
        "- doctor / clinic / hospital / MinuteClinic / Sacred Heart / urgent care / dentist / Aspen Dental / vision (America's Best, LensCrafters) / pharmacy when standalone (not CVS/Walgreens shopping) / medical labs (Quest Diagnostics, Touchstone Imaging, Vivid Pathology) / health insurance -> health\n"
        "- rent / mortgage / property management / HOA / Governors Gate / electricity / water / internet / Lemonade home insurance / recurring household services (PY ONELINK USA, PY ZENTRO and similar recurring service charges) -> housing\n"
        "- gas stations / EV charging / Shell / Circle K / Chevron / 7-Eleven gas / car loans (Mazda Financial, Toyota Financial) / ALL State Farm rows (auto insurance) / GEICO / Progressive / auto repair / body shops (Gross & Son Paint & Body) / parts (Advance Auto, AutoZone) / DMV / tag / license / tolls (NTTA, HCTRA, DSI NTTA) / parking permits -> transportation\n"
        "- AI services and developer APIs (Anthropic, Claude, OpenAI, ChatGPT, OpenRouter, Cursor, Perplexity, Immersive Translate, GitHub Copilot) / online courses (Udemy, Coursera, Skillshare) / graduate school applications / academic fees -> education\n"
        "- phone bills (Visible, IPHONE CITIZENS, VISIBLE SERVICE LLC, AT&T, Verizon, T-Mobile) / haircuts (Supercuts, Sport Clips, salons) / spa / nail / massage / dry cleaning / laundry / USPS / UPS Store / immigration law (HOPE IMMIGRATION, AFP HOPE IMMIGRATION) / general legal services (TABEA LAW, Rifkin & Fox-Isicoff, attorneys) / pet boarding / bank fees (monthly service fee, wire fee, foreign exchange adjustment fee, late fee, annual membership fee) / any genuinely unclear merchant -> personal\n"
        "- IRS / state tax / franchise tax -> taxes\n"
        "IMPORTANT: If a signature starts with 'PAYPAL ' (PayPal-funded purchase), IGNORE the PAYPAL prefix and classify by the merchant name after it. Examples: 'PAYPAL GOOGLE' = Google service (entertainment); 'PAYPAL MEDIUM.COM' = Medium subscription (entertainment); 'PAYPAL WSJ' = WSJ (entertainment); 'PAYPAL UDEMY' = Udemy course (education); 'PAYPAL VISIBLESERV' = Visible phone (personal); 'PAYPAL SPOTIFY' = Spotify (entertainment); 'PAYPAL PYPL PAYIN4' = Pay-in-4 BNPL installments for a retail purchase -> shopping.\n"
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
            cat = "personal"
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
        ].map(lambda s: cache.get(s, "personal"))

    df.loc[df["is_transfer"], "category"] = "transfer"
    df.loc[df["category"] == "", "category"] = "personal"
    return df
