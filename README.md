# Budget Viz

Local Streamlit dashboard for analyzing household spending across Chase, Discover, Amex, PayPal, and SoFi accounts. Drops raw bank CSVs into `Card Statements/<bank>/`, runs the dashboard, and shows category breakdowns, monthly trends, and budget vs. actual.

## Stack

- Python (managed with [`uv`](https://docs.astral.sh/uv/))
- Streamlit · pandas · plotly · OpenAI (for merchant categorization)

## Setup

```bash
uv sync
cp .env.example .env   # add OPENAI_API_KEY
```

Drop bank CSV exports into `Card Statements/<bank>/` (see `CLAUDE.md` for the expected filename patterns per source).

## Run

```bash
uv run streamlit run app.py
```

The first run categorizes uncached merchants via the OpenAI API and writes `data/category_cache.json`. Subsequent runs reuse the cache.

## Project layout

```
Card Statements/   raw CSVs (gitignored)
config/            card aliases, transfer rules, category budgets
data/              built parquet + caches (gitignored)
src/parsers/       one parser per source
src/               normalize, transfers, paypal_dedup, categorize, pipeline
app.py             Streamlit dashboard
```

See `plan.md` for the build sequence and `note.md` for design decisions.
