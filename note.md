
# Dashboard Update Requirements

Legend: `[x]` done · `[ ]` not started. Strikethrough = fully complete.

## [x] ~~1. Clean Up Non-Spending Transactions From `Other`~~

The `Other` category currently contains many transactions that are not actual consumer spending, including:

- Credit card payments (e.g. Amex `MOBILE PAYMENT - THANK YOU`)
- Paystubs / payroll deposits (e.g. `PENSACOLA STATE DIR DEP`, `Early Pay PAYROLL ACH from PENSACOLA STATE`)
- Transfers from investment platforms (e.g. `ROBINHOOD`, `MOOMOO`, `FID BKG SVC`)
- Internal account moves (e.g. `ODP TRANSFER FROM SAVINGS`, `Cash Redemption`)
- Refund-style ACH credits routed through third-party services (e.g. `DepositCloud BILLPAY` — treated as transfer because it represents money returning to the user, not new spending)
- Incoming P2P payments / reimbursements (e.g. `Zelle payment from <name>`, `Pen Air CU P2P PYMTS`)
- Any other negative-amount transaction that represents income, a payment received, or a transfer

These transactions should be excluded from spending analysis.

Examples:

| Date | Account | Description | Amount | Current Category | Clean Description |
|---|---|---:|---:|---|---|
| 2026-04-28 | amex | MOBILE PAYMENT - THANK YOU | -500 | other | MOBILE PAYMENT - THANK YOU |
| 2025-10-29 | discover_debit | Early Pay PAYROLL ACH from PENSACOLA STATE | -2248.41 | other | EARLY PAY PAYROLL ACH FROM PENSACOLA STATE |
| 2026-01-30 | chase_debit | DepositCloud BILLPAY PPD ID: 1842978924 | -1071.57 | other | DEPOSITCLOUD BILLPAY |
| 2024-07-01 | chase_debit | Zelle payment from XINYAN HE | -500 | other | ZELLE PAYMENT FROM XINYAN HE |

---

## [x] ~~2. Categorize Transfer Transactions Correctly~~

Some transactions are currently categorized as `Other`, but they should be categorized as `Transfer`.

This includes:

- Investment platform transfers (e.g. `ASTRA*Moomoo` variants on chase_debit `DEBIT_CARD` type)
- Zelle payments to YUXIN (e.g. discover_debit `Zelle Payment To YUXIN ...`)
- Zelle payments to Alex Yang
- Similar account-to-account or person-to-person transfers (e.g. outgoing Zelle to YUNLONG / YAYUAN LUO / XIAOMENG / yutssy.inc)

Bug fix bundled with this step: `src/transfers.py` was passing rule patterns to `str.contains` without `regex=False`, so patterns containing `*` (like `ASTRA*Moomoo`) were silently treated as regex and never matched. Fixed by passing `regex=False`.

PayPal dedup follow-up (caught during Step 2 testing): same purchase was showing up 3x (1 card row + 2 paypal rows). Two fixes in `src/paypal_dedup.py`:
- Drop PayPal `General Authorization (Completed)` when a same-day/same-amount settlement row exists (`Express Checkout Payment`, `General Payment`, etc.) — the Authorization is just the pre-auth hold.
- Cross-card dedup now matches card descriptions containing `PP*` (Chase's PayPal-funded shorthand), not only `PAYPAL`.

Examples:

| Date | Account | Description | Amount | Current Category | Clean Description |
|---|---|---:|---:|---|---|
| 2026-02-12 | chase_debit | ASTRA*Moomoou Visa Direct CA 02/12 | 3000 | other | ASTRA MOOMOOU VISA DIRECT |
| 2025-08-07 | discover_debit | Zelle Payment To YUXIN LBZ1L7SQD | 1200 | other | ZELLE PAYMENT TO YUXIN |
| 2026-01-14 | paypal (x2) + chase_freedom_flex | Vivid Seats LLC / PP*VIVID SEATS BRUNO M | 1057.88 each | entertainment | Same purchase recorded 3 times; keep only the card row |

---

## [x] ~~3. Improve Category Structure~~

The slash-grouped names in the original spec ("Housing / Utilities", "Transportation / Gas / Car", "Education / AI", "Other / Personal") are SINGLE merged categories at the data layer, not display groups over granular data. Implemented as 11 categories in `src/categorize.py` plus the special `transfer` tag.

Final category list:

| Category | Includes |
|---|---|
| `housing` | Rent (Governors Gate), electricity (FPL), internet, water, Lemonade home insurance, recurring household services (`PY ONELINK USA`, `PY ZENTRO`) |
| `grocery` | Whole Foods, Publix, Costco food, Aldi, Tony Food Market |
| `dining` | Restaurants, coffee, fast food, DoorDash, UberEats, vending machines (Coca Cola, CPI R&R Vending, PMUSA) |
| `transportation` | Gas (Circle K, Shell, Chevron, 7-Eleven), car loans (Mazda Financial, MFSUSA), **ALL State Farm rows (auto insurance)**, GEICO, Progressive, auto repair, body shops, parts, DMV / tag / license, tolls (NTTA, HCTRA), parking permits |
| `shopping` | Amazon, Target, Walmart, clothing, electronics, CVS, Walgreens, general retail, office furniture, home goods, **`PAYPAL *PYPL PAYIN4` (BNPL installments for retail purchases)** |
| `education` | AI services and developer APIs (Anthropic, Claude, OpenAI, ChatGPT, OpenRouter, Cursor, Perplexity, Immersive Translate, GitHub Copilot), online courses (Udemy, Coursera, Skillshare), graduate school applications, academic fees |
| `entertainment` | Netflix, Spotify, Kindle, Audible, streaming, YouTube Premium, Google One, games, PlayStation, concerts (Ticketmaster, StubHub, Vivid Seats), AMC, Apple Services, WSJ, Medium, gym, tennis |
| `health` | Doctor, clinic, hospital, MinuteClinic, Sacred Heart, urgent care, dentist, Aspen Dental, vision (America's Best), pharmacies (standalone, not CVS shopping), medical labs (Quest Diagnostics, Touchstone Imaging, Vivid Pathology), health insurance |
| `travel` | Hotels, flights, Airbnb, Uber, Lyft, transit, MTA, parking for trips, tickets for visits or activities **outside of Pensacola**, theme parks, museums outside Pensacola |
| `personal` | Phone bills (Visible, IPHONE CITIZENS, AT&T, Verizon, T-Mobile), haircuts (Supercuts, Sport Clips, salons), spa, nail, massage, dry cleaning, laundry, USPS / UPS Store, immigration law (HOPE IMMIGRATION, AFP HOPE IMMIGRATION), general legal services (TABEA LAW, Rifkin & Fox-Isicoff, attorneys), pet boarding, bank fees (monthly service fee, wire fee, FX adjustment fee, late fee, annual membership fee), any genuinely unclear merchant |
| `taxes` | IRS, state tax, franchise tax |
| `transfer` | Special — not in spending totals. Set by `src/transfers.py`. |

### PayPal-prefix handling

If a signature starts with `PAYPAL `, ignore the PAYPAL prefix and classify by the merchant after it (e.g. `PAYPAL GOOGLE` → entertainment, `PAYPAL UDEMY` → education, `PAYPAL VISIBLESERV` → personal, `PAYPAL *PYPL PAYIN4` → shopping).

### Migration notes

- Cache (`data/category_cache.json`) was migrated: `utilities` → `housing`; `gas` and `car` → `transportation`; `ai` → `education`; `other` entries were cleared so the LLM reclassifies them under the new prompt.
- Pipeline-level transfer rules also extended during this step: `DISCOVER E-PAYMENT` (chase_debit `ACH_DEBIT` paying Discover credit) and `PAYPAL *ADD TO` (PayPal balance funding) now correctly land as `transfer`.

---

## [x] ~~4. Remove Refund Transaction Pairs~~

Refund pairs and standalone credits are now excluded from spending. Implementation in `src/refunds.py`:

- Pair detection: same merchant + opposite amounts within ±$0.01 + dates within 60 days. Cross-source pairing allowed when descriptions share a meaningful merchant token (stopwords like `PAYPAL`, `AMZN`, `MKTP`, `INC`, `COM` skipped). Picks the closest-date candidate.
- Standalone credits: any remaining negative non-transfer row is also flagged `is_refund=True` (Chase Travel Credit, GEICO refund, Aspen Dental refund, etc.).
- Dashboard spending mask now filters `~is_transfer & ~is_refund`.

Bug fix bundled with this step: `src/paypal_dedup.py` cross-card dedup originally skipped negative amounts (`if row["amount"] <= 0: continue`), so refunds passing through PayPal showed up twice (once on PayPal, once on the funding card). Switched to signed-amount matching so refund direction dedups the same as purchase direction.

Examples now caught:

| Date | Account | Description | Amount | Pair partner |
|---|---|---:|---:|---|
| 2026-01-29 | chase_freedom_flex | PAYPAL *TIFFANY CO | -1128.75 | chase_sapphire `Tiffany and Co.` +1128.75 (cross-source) |
| 2026-01-09 | discover_credit | RIFKIN & FOX-ISICOFF PA MIAMI FL | -250 | discover_credit `RIFKIN & FOX-ISICOFF PA MIAMI FL` +250 |
| 2025-11-07 | chase_sapphire | ASPEN DENTAL REFUND 0002 | -143.60 | chase_sapphire `ASPEN PENSACOLA N 4137` +143.60 (different signature) |
| 2024-11-23 | chase_sapphire | Chase Travel Credit | -272.35 | chase_sapphire `CL *Chase Travel` +272.35 |

---

## [x] ~~5. Update Dashboard Charts~~

The dashboard should be updated to focus on monthly spending trends, category composition, top spending areas, category trends, and budget comparison.

---

### [x] ~~Chart 1: Monthly Total Spending~~

Implemented in `app.py` directly under the KPI row (top of dashboard).

- Line chart with markers (`plotly.graph_objects.Scatter`, mode `lines+markers`).
- X-axis: month (first day of month timestamp); Y-axis: total monthly spend (already excludes transfers and refunds).
- Sidebar adds a `Monthly budget ($)` number input. When > 0, a dashed crimson `add_hline` is drawn as the budget reference; when 0 the line is hidden.
- Y-axis formatted as `$,.0f`; hover shows `Mon YYYY` + `$X,XXX.XX`.

---

### [x] ~~Chart 2: Category Breakdown~~

Implemented as a `px.bar(barmode="stack")` over (month_label, category). Top 6 categories by total spend in the selected range are kept; everything else is rebucketed into a synthetic `other` series so the chart stays readable. Legend ordered by total spend with `other` pinned last. Y-axis `$,.0f`.

---

### (original spec)

Use a stacked bar chart.

Purpose:

- Show total spending by month
- Show how much each category contributes to each month
- Show whether the spending mix changes over time

Chart design:

- X-axis: Month
- Y-axis: Spending amount
- Each bar should be stacked by category

Only show the major categories in the stacked bar chart. Group small categories into `Other`.

---

### [x] ~~Chart 3: Top Categories~~

Implemented as a horizontal `px.bar` with `st.radio` (3/6/12 month) lookback selector, default 6. Window anchored to `df["month"].max()` so it's "last N months of available data" rather than "last N months from today." Sources filter respected; transfers and refunds excluded. `update_yaxes(categoryorder="total ascending")` puts the biggest bar at the top. Dollar values shown via `text_auto="$,.0f"`.

---

### (original spec)

Use a horizontal bar chart.

Purpose:

- Show where most money was spent over the past 3, 6, or 12 months.

Chart design:

- Y-axis: Category
- X-axis: Spending amount
- Sort categories from highest to lowest spending

This chart should make it easy to compare spending across categories.

---

### [x] ~~Chart 4: Category Trend~~

Implemented as `px.line(markers=True)`. `st.multiselect` picks the focus categories; default is `[shopping, dining, entertainment, transportation, grocery]` — note "gas" maps to `transportation` per the merged Step 3 schema. Options exclude `transfer`.

---

### (original spec)

Use a multi-line chart.

Purpose:

- Show whether selected categories are increasing or decreasing over time.

Only include a few important categories, such as:

- Shopping
- Dining
- Entertainment
- Gas
- Groceries

Do not include every category, because too many lines will make the chart difficult to read.

---

### [x] ~~Chart 5: Budget vs Actual~~

Implemented as a grouped horizontal `px.bar` with `barmode="group"`. Per-category monthly budgets persist to `config/category_budgets.json` (created on first save). An `st.expander("Edit category budgets")` exposes a `st.data_editor` and a `Save budgets` button that writes the JSON and reruns. Actuals are computed as monthly average over the selected range (`sum(amount) / n_months`) so they're directly comparable to the stored monthly budget. Categories sorted by Actual descending (largest at the top).

---

### (original spec)

Use a grouped horizontal bar chart.

If the dashboard tool supports it, a bullet chart can also be used.

Purpose:

- Compare planned budget against actual spending by category.

Chart design:

- Category
- Budget amount
- Actual spending amount

Example:

| Category | Budget | Actual |
|---|---:|---:|
| Food | 600 | 720 |
| Shopping | 300 | 480 |
| Gas | 150 | 130 |

---

## Challenge and solution

### [ ] 6. Refund pairing misses generic-named refunds (e.g. Amazon)

#### Problem

`src/refunds.py` pairs a negative (refund) row with a positive (charge) row only when both descriptions share at least one ≥4-character token that is NOT in `STOP_TOKENS`. The stop list includes generic merchant words such as `AMAZON`, `AMZN`, `MKTPLACE`, `MKTP`, `PMTS`. Real-world example:

- Refund row: `chase_freedom_flex` `2026-04-16` `AMAZON MKTPLACE PMTS` `-$116.09` → tokens after stop-word filter = `{}` (everything is a stop word).
- Charge row: `chase_freedom_flex` `2026-04-10` `AMAZON MKTPL*BY0UT71L2` `+$116.09` → tokens = `{MKTPL, BY0UT71L2}`.
- Token intersection is empty → the refund is left unpaired (marked `is_refund=True`, empty `refund_pair_id`), so it IS excluded from spending — but the corresponding +$116.09 charge is NOT excluded. Total spend is overstated.

The fragility: any future merchant whose refund description differs structurally from its charge description (truncations, alternate suffixes, generic billing prefixes) will hit the same failure.

#### Candidate solutions considered

1. **Loosen `STOP_TOKENS`** (remove `AMAZON / AMZN / MKTPLACE / MKTP / PMTS`).
   - Pros: one-line fix for the immediate Amazon case.
   - Cons: doesn't generalize. Future merchants with a similar token-naming gap will silently break again. Treats symptom, not root cause.

2. **LLM-based fallback adjudicator (gpt-4o-mini)**.
   - For each unpaired refund, build the candidate set (same source, opposite amount within $0.01, within 60 days), and ask the LLM to pick the matching charge or "none". Cache results to `data/refund_pair_cache.json`.
   - Pros: robust to any future merchant naming variation. Cheap (<30 calls per full rebuild, well under $0.01). Reuses existing OpenAI client + cache pattern from `src/categorize.py`.
   - Cons: requires an `OPENAI_API_KEY` to be present (must degrade gracefully when missing). Non-determinism risk (mitigated by `temperature=0` and caching).

3. **Embed merchant strings + cosine similarity**.
   - Pros: no per-pair LLM call after embedding once.
   - Cons: introduces a new dependency (embeddings model + vector storage). Overkill for the data volume here.

4. **Have the LLM extract a normalized `brand` field during categorization**.
   - Pros: solves the matching problem at the source — rows for the same brand always share a `brand` value, regardless of description noise.
   - Cons: requires extending `categorize.py`'s schema and re-running categorization to backfill. Larger blast radius.

5. **Manual UI override only** (in the Refunds & credits panel).
   - Pros: 100% reliable. No LLM cost.
   - Cons: requires manual work for every new unmatched refund.

6. **Single-candidate auto-pair shortcut**.
   - When the candidate set (same source + opposite amount + 60-day window) contains exactly ONE positive charge, auto-pair without checking merchant name. Ambiguity is essentially zero.
   - Pros: free, deterministic, fixes most everyday cases.
   - Cons: doesn't help when there are multiple equal-amount candidates.

#### Chosen approach (hybrid)

A four-stage pairing pipeline, evaluated in order:

1. **Pass 1 — current rule-based pairing** (`refunds.py`): unchanged. Catches obvious cases with shared distinctive tokens.
2. **Pass 1.5 — single-candidate auto-pair**: if exactly one candidate charge matches by source + opposite amount + ≤60 days, pair it without merchant check.
3. **Pass 2 — LLM adjudicator** (only if `OPENAI_API_KEY` is present): for refunds with multiple candidates, send a short prompt to `gpt-4o-mini` asking it to pick a candidate index or "none". Cache results in `data/refund_pair_cache.json` keyed by stable hash of `(refund_signature, sorted candidate signatures, amount)`.
4. **Pass 3 — manual override**: read `config/manual_refund_pairs.json` (user-edited via UI). Manual pins always win over auto/LLM decisions.

Rationale: cheap deterministic fixes run first; LLM is only invoked for genuinely ambiguous cases; the user retains final authority via manual pinning. Degrades gracefully without an API key (Passes 1, 1.5, 3 still work).

UI changes in `app.py` Refunds & credits panel:
- Two dropdowns (unpaired refund + candidate charge) + "Pin pair" button → writes JSON.
- Listing of currently pinned pairs with an "Unpin" control.

#### Verification

See `plan.md` for the implementation plan and end-to-end test steps.
