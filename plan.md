# Budget Viz — Personal Spending Dashboard

## Context

A Python tool to analyze household spending across multiple bank/credit-card statements (Chase Sapphire, Chase Freedom Flex, Chase debit, Discover credit, Discover debit, Amex, PayPal, SoFi joint checking, SoFi joint savings). Statements come as CSV files. Different issuers use different schemas and sign conventions. The goal: drop new statements into a folder, get an auto-updating Streamlit dashboard showing average spend per category, percent breakdown, and month-over-month shifts. Categorization is done by the OpenAI API. Tracking is combined (household). Sample files for every source already live in `Card Statements/`.

## Statements Folder

User-dropped raw files live in `Card Statements/<bank>/` (existing layout — keep). The pipeline scans this tree recursively.

```
Card Statements/
├── Amx/activity.csv
├── Chase/Chase3209_Activity*.CSV           (Sapphire Preferred credit)
├── Chase/Chase5878_Activity*.CSV           (Freedom Flex credit)
├── Chase/Chase8290_Activity*.CSV           (Chase debit / checking)
├── Discover/Discover-Last12Months*.csv     (Discover credit)
├── Discover/Debt-*.csv                     (Discover cashback debit)
├── Paypal/Download.CSV
└── Sofi/
    ├── SOFI-JointChecking•8439-*.csv
    └── SOFI-JointSavings•3712-*.csv
```

## High-Level Architecture

```
Budget Viz/
├── Card Statements/             # raw CSV/XLS files (user-managed)
├── config/
│   ├── card_aliases.json        # last-4 digits -> friendly source name
│   └── transfer_rules.json      # patterns that mark a row as a transfer
├── data/
│   ├── transactions.parquet     # parsed + normalized + categorized cache
│   └── category_cache.json      # merchant signature -> category
├── src/
│   ├── parsers/
│   │   ├── __init__.py          # detect_source(path) -> parser
│   │   ├── chase_credit.py      # 3209, 5878 — same format
│   │   ├── chase_debit.py       # 8290
│   │   ├── discover_credit.py
│   │   ├── discover_debit.py
│   │   ├── amex.py
│   │   ├── paypal.py
│   │   └── sofi.py              # both checking and savings
│   ├── normalize.py             # txn_id, merchant_signature
│   ├── transfers.py             # transfer detection + cross-account pairing
│   ├── paypal_dedup.py          # PayPal vs funding-card dedup
│   ├── categorize.py            # OpenAI batch categorization + cache
│   └── pipeline.py              # orchestrator
├── app.py
├── .env.example
├── pyproject.toml
├── plan.md
├── CLAUDE.md
└── README.md
```

## Unified Transaction Schema

| Column | Type | Notes |
|---|---|---|
| `date` | date | Transaction date |
| `description` | string | Original merchant / memo |
| `amount` | float | **Positive = expense. Negative = refund/credit.** |
| `source` | string | Card-level: `chase_sapphire`, `chase_freedom_flex`, `chase_debit`, `discover_credit`, `discover_debit`, `amex`, `paypal`, `sofi_checking`, `sofi_savings` |
| `category` | string | `grocery, gas, shopping, travel, dining, utilities, entertainment, housing, taxes, other, transfer` (11 — `transfer` is special and excluded from spending charts) |
| `is_transfer` | bool | True if this row is a transfer (also reflected in `category`) |
| `txn_id` | string | Stable hash of date + description + amount + source for dedup |

## Categories

`grocery, gas, shopping, travel, dining, utilities, entertainment, housing, taxes, other` plus the special `transfer` tag. Rent goes to `housing`, IRS to `taxes`, insurance/electricity to `utilities`, car-loan payments to `housing` or `other` (per LLM judgment).

## Card-Level Identification (Chase)

`config/card_aliases.json`:
```json
{
  "3209": "chase_sapphire",
  "5878": "chase_freedom_flex",
  "8290": "chase_debit"
}
```

Chase parser extracts the last 4 from the filename (`Chase3209_…`, `Chase5878_…`, `Chase8290_…`) and resolves the alias. Files 3209 and 5878 share the credit-card format; 8290 uses the debit format — detected by the header row (`Details, Posting Date, …` vs. `Transaction Date, Post Date, …`).

## Per-Source Parsing Rules

### Chase credit (3209 Sapphire, 5878 Freedom Flex)
- Columns: `Transaction Date, Post Date, Description, Category, Type, Amount, Memo`
- `Type ∈ {Sale, Payment, Return, Adjustment, Fee}`.
- Sign: purchases are **negative** in the raw file; payments to the card are positive. Flip the sign so expense = positive.
- Rows with `Type = Payment` are credit-card payments → tag as `transfer`.

### Chase debit (8290)
- Columns: `Details, Posting Date, Description, Amount, Type, Balance, Check or Slip #`
- `Details ∈ {CREDIT, DEBIT}`; `Type` is granular (see transfer rules below).
- Sign: debits **negative**, credits positive. Flip so expense = positive.
- **Parse with Python's `csv` module, not naive splits** — descriptions contain commas.

### Discover credit
- Columns: `Trans. Date, Post Date, Description, Amount, Category`
- Sign: purchases **positive**, payments to card negative. **No flip.**
- Rows where description matches `INTERNET PAYMENT - THANK YOU`, `DIRECTPAY`, `CASHBACK BONUS REDEMPTION` → tag as `transfer`.

### Discover debit
- Columns: `Transaction Date, Transaction Description, Transaction Type, Debit, Credit, Balance`
- Two amount columns, `$`-prefixed strings, `0` when empty. Strip `$`, parse as float.
- Combine: `amount = parsed(Debit) if Debit > 0 else -parsed(Credit)`. Result: expense = positive.

### Amex
- Columns: `Date, Description, Card Member, Account #, Amount`
- Sign: purchases **positive**, refunds negative. **No flip.**

### PayPal
- Columns: `Date, Time, TimeZone, Name, Type, Status, Currency, Amount, Fees, Total, Exchange Rate, Receipt ID, Balance, Transaction ID, Item Title`
- `Amount` is already signed (spending negative). **Flip** so expense = positive.
- **Filter rules (drop rows that are PayPal-internal accounting):**
  1. Drop `Status = Pending` (the same txn has a `Completed` twin).
  2. Drop `Type = General Card Deposit` (offset for card-funded payments — internal).
  3. Drop `Type = General Card Withdrawal` when there's a same-day/same-amount `Payment Refund` row (refund pushed back to a card — internal offset).
  4. Drop `Type = Bank Deposit to PP Account` (transfer from external bank — see transfer pairing).
- Keep: `PreApproved Payment Bill User Payment`, `Express Checkout Payment`, `General Payment`, `General PayPal Debit Card Transaction`, `Payment Refund`, `General Authorization` (only the Completed ones), `General GI/Open wallet Transaction`.

### SoFi joint checking (8439) & savings (3712)
- Columns: `Date, Description, Type, Amount, Current balance, Status`
- ISO dates (`2026-05-04`).
- Sign: withdrawals **negative**, deposits positive. Flip so expense = positive.
- `DIRECT_DEPOSIT` (paycheck) and `INTEREST_EARNED` → tag as `transfer` (not income tracked here — focus is spending).
- Internal moves (`From Checking - 8439` / `To Savings - 3712`) → transfer.
- Bill pays (`DIRECT_PAY` to "Governors Gate I", IRS, etc.) → real spending, route through LLM categorization.

## Transfer Detection (`src/transfers.py`)

Two layers:

**Layer 1 — Per-row rules from `config/transfer_rules.json`.** A row is a transfer if any rule fires. Seed config:

```json
{
  "chase_debit": {
    "types": ["LOAN_PMT", "ACCT_XFER", "CHASE_TO_PARTNERFI", "PARTNERFI_TO_CHASE"],
    "type_plus_description": {
      "ACH_DEBIT": ["CHASE CREDIT CRD AUTOPAY"],
      "MISC_DEBIT": ["AMERICAN EXPRESS ACH PMT", "Discover", "SoFi", "ROBINHOOD", "Moomoo"],
      "MISC_CREDIT": ["SoFi Bank", "Moomoo", "Discover", "ROBINHOOD"]
    }
  },
  "discover_debit": {
    "description_contains": ["DISCOVER E-PAYMENT", "ROBINHOOD DEBITS", "MOOMOO", "SOFI"]
  },
  "chase_sapphire": {"type_equals": ["Payment"]},
  "chase_freedom_flex": {"type_equals": ["Payment"]},
  "discover_credit": {
    "description_contains": ["INTERNET PAYMENT - THANK YOU", "DIRECTPAY", "CASHBACK BONUS REDEMPTION", "AUTOMATIC PAYMENT"]
  },
  "sofi_checking": {
    "types": ["DIRECT_DEPOSIT", "INTEREST_EARNED"],
    "description_contains": ["To Savings", "From Savings", "JPMORGAN CHASE", "Discover", "American Express", "ROBINHOOD", "Moomoo"]
  },
  "sofi_savings": {
    "types": ["DIRECT_DEPOSIT", "INTEREST_EARNED"],
    "description_contains": ["To Checking", "From Checking", "JPMORGAN CHASE"]
  }
}
```

Brokerage moves (Robinhood, Moomoo) count as transfers per the user's preference.

**Layer 2 — Cross-account pairing.** After Layer 1, also find unflagged transfers by matching the two legs of a move:

- Pair rows where `(source_a ≠ source_b)`, `|date_a - date_b| ≤ 3 days`, `amount_a + amount_b ≈ 0` (one positive expense, one negative credit), and at least one side has a description suggesting the other account (e.g. `SoFi Bank TRANSFER` ↔ `JPMORGAN CHASE BANK`).
- Tag both legs as transfer.

## PayPal vs Funding-Card Dedup (`src/paypal_dedup.py`)

For each remaining PayPal expense after parsing:
1. Search Chase Sapphire, Chase Freedom Flex, Chase debit, Discover credit, Discover debit, Amex for any row with:
   - `|date - paypal_date| ≤ 3 days`
   - `abs(amount - paypal_amount) < $0.01`
   - description contains `PAYPAL` (case-insensitive)
2. If a match is found, drop the PayPal row. The card row is more authoritative (it's the actual funding source and shows on the cardholder statement).
3. If no match → keep PayPal row (likely funded from PayPal balance or PayPal debit card directly).

## Categorization Flow

`data/category_cache.json` maps normalized merchant signature → category. Cache is the source of truth; manual edits win.

Merchant signature: uppercase description, strip dates, store numbers, trailing transaction IDs, and standard noise like `APPLE PAY ENDING IN XXXX`, `AplPay`, `PPD ID:`, `WEB ID:`, etc.

Flow:
1. Compute signature per row.
2. Look up in cache.
3. Batch uncached signatures (50/request) to OpenAI (`gpt-4o-mini`), strict JSON output.
4. Write results back to cache.
5. Transfer rows skip the LLM (category already set to `transfer`).

## Pipeline (`src/pipeline.py`)

`build_transactions() -> pd.DataFrame`:
1. Walk `Card Statements/` for `.csv` / `.CSV` files.
2. For each file: `detect_source(path)` → call right parser → attach `source`.
3. Concatenate everything.
4. Apply Layer-1 transfer rules.
5. Apply PayPal filter + cross-card PayPal dedup.
6. Apply Layer-2 cross-account pairing.
7. Compute `txn_id`, drop exact duplicates.
8. Categorize via `categorize.py` (skipping transfers).
9. Write `data/transactions.parquet`.

Streamlit caches the result with `@st.cache_data` keyed by the max mtime under `Card Statements/`.

## Dashboard (`app.py`)

- **Sidebar**: month range (default last 6 months), source multi-select, category multi-select, "show transfers" toggle (default off).
- **KPI row**: total spend (excluding transfers), average monthly spend, txn count.
- **Chart 1**: Bar — average monthly spend per category.
- **Chart 2**: Donut — percent breakdown for most recent full month.
- **Chart 3**: Grouped bar — MoM per category.
- **Chart 4**: Line — total spend over time, stacked by category.
- **Transfers panel** (collapsible): list of detected transfers so the user can sanity-check.
- **Table**: filterable transaction list with inline category override (writes to `category_cache.json`).

## Build Sequence

Legend: `[x]` done · `[~]` in progress · `[ ]` not started. Strikethrough = fully complete.

1. [x] ~~**Skeleton**: `uv init`, deps, folder layout, `.env.example`, `.gitignore`, seed `config/` files.~~ (commit `46cae85`)
2. [x] ~~**Parsers** — one per source, working from the existing sample files in `Card Statements/`. Verify row counts against each file. Sapphire is the first to wire end-to-end.~~
   - [x] ~~`chase_credit.py` (Sapphire 3209 + Freedom Flex 5878) — commit `6ea8a8f`~~
   - [x] ~~`chase_debit.py` (8290)~~
   - [x] ~~`discover_credit.py`~~
   - [x] ~~`discover_debit.py`~~
   - [x] ~~`amex.py`~~
   - [x] ~~`paypal.py`~~
   - [x] ~~`sofi.py` (checking + savings)~~
3. [x] ~~**Pipeline (no transfers, no categorization)** — show raw merged data in a stub Streamlit page.~~
4. [x] ~~**Transfer detection** — Layer 1 rules, then Layer 2 pairing. Show transfers panel; user sanity-checks.~~
5. [x] ~~**PayPal dedup** — run before/after diff to verify which PayPal rows get dropped.~~
6. [~] **Categorization** — OpenAI + cache. Spot-check 20 random non-transfer rows.
7. [ ] **Full dashboard** — 4 charts + filters + inline override.
8. [ ] **Polish** — handle missing API key, empty months, malformed files.

## Verification

After each step, run `uv run streamlit run app.py`. Spot-checks:
- Each source's row count = (file line count − 1).
- Sapphire: confirm 5/9 DoorDash row shows `+$34.80` (expense positive) and 5/6 `AUTOMATIC PAYMENT` is tagged `transfer`.
- Chase debit: confirm the `-$4000 Payment to Chase card ending in 5878` is tagged transfer AND pairs with the Freedom Flex `+$4000 Payment Thank You-Mobile` row (also transfer).
- Chase debit ↔ SoFi: the `+$4000 SoFi Bank TRANSFER` (5/7) pairs with SoFi savings `-$4000 JPMORGAN CHASE BANK` (5/7). Both transfer.
- PayPal dedup: pick a PayPal `-$11.99 Spotify` and confirm whether a matching `PAYPAL *SPOTIFY` shows on Sapphire/Flex; expect the PayPal row dropped if so.
- IRS `-$6488` on SoFi savings: category should be `taxes`, NOT transfer.
- Governors Gate rent: category should be `housing`.

## Open Items

- Whether to surface a separate "income" panel (paychecks, interest) for context — defer to v2.
- Whether refunds (negative amounts) net against expenses inline or show separately — default: net within same category and month.
