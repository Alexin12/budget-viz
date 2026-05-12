# Budget Viz — Claude Code Project Instructions

## What this project is

A local Streamlit dashboard for analyzing household spending across Chase Sapphire / Freedom Flex / debit, Discover credit + debit, Amex, PayPal, and SoFi joint checking + savings. The user drops raw bank CSVs into `Card Statements/<bank>/`, runs the dashboard, and gets average spend per category, percent breakdown, and month-over-month shifts. Categorization is done via the OpenAI API with a local cache.

Full design lives in `plan.md`. Read it before any structural change.

## Stack

- **Python** via `uv` only. Never use `pip`, `python`, or `python3` directly.
  - Run scripts: `uv run <script>` · Install: `uv add <pkg>` · Dashboard: `uv run streamlit run app.py`
- **Streamlit** for UI, **pandas** + **pyarrow** for data, **plotly** for charts, **openai** for categorization. CSVs use Python's `csv` module (descriptions contain commas).

## Layout

```
Card Statements/   # raw files (user-managed). Source = subfolder + filename.
config/            # card_aliases.json, transfer_rules.json
data/              # transactions.parquet, category_cache.json (gitignored)
src/
  parsers/         # one file per source; each owns its own column + sign logic
  normalize.py
  transfers.py     # Layer-1 rules + Layer-2 cross-account pairing
  paypal_dedup.py
  categorize.py
  pipeline.py
app.py
```

## Source identification

| File pattern | Source |
|---|---|
| `Chase3209_*.CSV` | `chase_sapphire` |
| `Chase5878_*.CSV` | `chase_freedom_flex` |
| `Chase8290_*.CSV` | `chase_debit` |
| `Discover-Last12Months*.csv` | `discover_credit` |
| `Debt-*.csv` (inside `Discover/`) | `discover_debit` |
| `Amx/activity.csv` | `amex` |
| `Paypal/Download.CSV` | `paypal` |
| `SOFI-JointChecking*.csv` | `sofi_checking` |
| `SOFI-JointSavings*.csv` | `sofi_savings` |

Last-4 mapping is in `config/card_aliases.json`. Unknown last-4 → `chase_unknown_<digits>` plus dashboard warning.

## Per-source sign convention (memorize before touching parsers)

| Source | Raw purchase sign | Action |
|---|---|---|
| Chase Sapphire (3209) | negative | **flip** |
| Chase Freedom Flex (5878) | negative | **flip** |
| Chase debit (8290) | negative | **flip** |
| Discover credit | positive | no flip |
| Discover debit | split `Debit` / `Credit` columns ($-prefixed) | combine → expense positive |
| Amex | positive | no flip |
| PayPal | negative | **flip** |
| SoFi checking / savings | negative | **flip** |

After normalization: **positive = expense, negative = refund/credit/incoming**. This is invariant — every parser MUST output this.

## Categories

`grocery, gas, shopping, travel, dining, utilities, entertainment, housing, taxes, other` — plus the special `transfer` tag (excluded from spending totals). Rent → `housing`, IRS → `taxes`, electricity/insurance → `utilities`, car-loan → `housing` (LLM decides; user can override).

## Transfer rules (hard-coded reference)

A transfer is any movement of the user's own money between accounts. Tagged `category = "transfer"`, excluded from spending totals.

**Two-layer detection:**

**Layer 1 — per-row rules in `config/transfer_rules.json`:**
- **Chase debit `Type`**: `LOAN_PMT`, `ACCT_XFER`, `CHASE_TO_PARTNERFI`, `PARTNERFI_TO_CHASE`
- **Chase debit `ACH_DEBIT` only when description contains** `CHASE CREDIT CRD AUTOPAY` (other ACH_DEBIT rows are bills — those ARE spending)
- **Chase debit `MISC_CREDIT` / `MISC_DEBIT`** when description matches another bank/broker: `AMERICAN EXPRESS ACH PMT`, `Discover ... PREARRANGE`, `SoFi Bank TRANSFER`, `Moomoo Financial`, `ROBINHOOD`
- **Discover debit description** contains: `DISCOVER E-PAYMENT`, `ROBINHOOD DEBITS`, `MOOMOO`, `SOFI`
- **Chase credit `Type = Payment`** rows (all of them)
- **Discover credit description** contains: `INTERNET PAYMENT - THANK YOU`, `DIRECTPAY`, `CASHBACK BONUS REDEMPTION`, `AUTOMATIC PAYMENT`
- **SoFi `Type`**: `DIRECT_DEPOSIT`, `INTEREST_EARNED` (these are income, not spending — treat as transfer for spending-only scope)
- **SoFi description** contains: `To Savings`, `From Savings`, `To Checking`, `From Checking`, `JPMORGAN CHASE`, `Discover`, `American Express`, `ROBINHOOD`, `Moomoo`

**Brokerage moves (Robinhood, Moomoo) ARE transfers** per user decision. Not spending, not a separate "investing" bucket.

**Layer 2 — cross-account pairing**: after Layer 1, also flag any unmatched rows that pair across sources with `|date_a - date_b| ≤ 3 days`, `amount_a + amount_b ≈ 0`, and one side's description mentioning the other account.

## PayPal special handling

PayPal double-records every card-funded payment. Rules:

1. **Drop** rows where `Status = Pending` (every pending row has a `Completed` twin once settled).
2. **Drop** rows where `Type = General Card Deposit` (internal offset for card-funded payment).
3. **Drop** `General Card Withdrawal` when paired same-day/same-amount with a `Payment Refund` (internal offset).
4. **Drop** `Bank Deposit to PP Account` (handle via transfer pairing instead).
5. **Cross-card dedup**: for each remaining PayPal expense, look across Chase/Discover/Amex for a row with `±3 days`, same `abs(amount)`, description containing `PAYPAL`. If found → drop the PayPal row (the card row is the true source of funds).
6. Keep merchant-bearing rows: `PreApproved Payment Bill User Payment`, `Express Checkout Payment`, `General Payment`, `General PayPal Debit Card Transaction`, `Payment Refund`, Completed `General Authorization`.

## Categorization

- Model: OpenAI `gpt-4o-mini`. Key in `.env` as `OPENAI_API_KEY`.
- Cache: `data/category_cache.json` maps normalized merchant signature → category.
- **Manual edits to the cache always win** — never overwritten by the LLM.
- Signature normalization strips: `APPLE PAY ENDING IN XXXX`, `AplPay`, `PPD ID:`, `WEB ID:`, trailing store numbers, trailing dates, transaction IDs. Goal: "AMAZON MKTP US*A1B2" and "AMAZON MKTP US*X9Y8" collapse to the same key.
- Transfer rows skip the LLM (category is already `transfer`).

## CSV parsing notes (gotchas seen in real files)

- Chase debit descriptions contain commas inside the field — **use `csv` module, not `awk` / naive splits**.
- Discover debit amounts are `$`-prefixed strings (`$100.00`) with literal `0` (not `$0.00`) for empty side.
- SoFi dates are ISO (`2026-05-04`); everything else is `MM/DD/YYYY`.
- PayPal's first line has a BOM (`﻿`). Strip it.
- Chase credit `Memo` column is usually empty but exists in header.
- SoFi filenames contain a `•` (bullet) character — handle as UTF-8.

## Coding conventions (globally — also in `~/.claude/CLAUDE.md`)

- Keep it simple. No over-engineering. Three similar lines beats a premature abstraction.
- No defensive programming for things that can't happen. Validate only at real boundaries (CSV parsing, API calls).
- No emojis anywhere — code, comments, files, responses.
- No docstrings, type hints, or comments added to code you didn't change.
- Comments only where logic isn't self-evident.
- Don't refactor surrounding code when fixing a bug.
- Remove dead code entirely. No commented-out code, no backwards-compat shims.
- Root cause before fix. Prove with evidence. Never suppress errors as a workaround.

## Workflow

- Build incrementally per `plan.md`'s Build Sequence. Don't jump ahead.
- After each step, run the dashboard and spot-check against the raw CSVs.
- One concrete change at a time.
- Need to do tests after each one step is finished, and return "This step has been tested!"

## Gitignore

`data/`, `.env`, `.superpowers/`, `__pycache__/`, `.venv/`, `.DS_Store`. Keep `Card Statements/` ignored too (real financial data).
