
# Dashboard Update Requirements

## 1. Clean Up Non-Spending Transactions From `Other`

The `Other` category currently contains many transactions that are not actual consumer spending, including:

- Credit card payments
- Paystubs / payroll deposits
- Transfers from investment platforms should be categorized as transfer
- Other transactions with negative amounts that represent income, payments, or transfers

These transactions should be excluded from spending analysis.

Examples:

| Date | Account | Description | Amount | Current Category | Clean Description |
|---|---|---:|---:|---|---|
| 2026-04-28 | amex | MOBILE PAYMENT - THANK YOU | -500 | other | MOBILE PAYMENT - THANK YOU |
| 2025-10-29 | discover_debit | Early Pay PAYROLL ACH from PENSACOLA STATE | -2248.41 | other | EARLY PAY PAYROLL ACH FROM PENSACOLA STATE |

---

## 2. Categorize Transfer Transactions Correctly

Some transactions are currently categorized as `Other`, but they should be categorized as `Transfer`.

This includes:

- Investment platform transfers
- Zelle payments to YUXIN
- Zelle payments to Alex Yang
- Similar account-to-account or person-to-person transfers

Examples:

| Date | Account | Description | Amount | Current Category | Clean Description |
|---|---|---:|---:|---|---|
| 2026-02-12 | chase_debit | ASTRA*Moomoou Visa Direct CA 02/12 | 3000 | other | ASTRA MOOMOOU VISA DIRECT |
| 2025-08-07 | discover_debit | Zelle Payment To YUXIN LBZ1L7SQD | 1200 | other | ZELLE PAYMENT TO YUXIN |

---

## 3. Improve Category Structure

Avoid putting too many transactions into `Other`.

Use 6-8 major spending categories for the main dashboard, and group the remaining categories into `Other`.

Recommended primary categories:

- Housing / Utilities
- Grocery
- Food / Dining
- Transportation / Gas / Car
- Shopping
- Education / AI
- Entertainment
- Health
- Travel
- Transfers
- Other / Personal


### Category Notes

`Travel` should include:

- Hotels
- Flights
- Tickets for visits or activities outside of Pensacola

`Other / Personal` should include:

- HOPE IMMIGRATION
- TABEA LAW PC
- API-related transactions
- LLM model subscription fee
- Phone-related payments, such as:

| Account | Description |
|---|---|
| discover_debit | IPHONE CITIZENS |

---

## 4. Remove Refund Transaction Pairs

Refund transactions should be removed from spending analysis.

If two transactions have the same or highly similar description and opposite amounts, they should be treated as a refund pair and excluded.

Example:

| Date | Account | Description | Amount | Current Category | Clean Description |
|---|---|---:|---:|---|---|
| 2026-01-09 | discover_credit | RIFKIN & FOX-ISICOFF PA MIAMI FL | -250 | other | RIFKIN & FOX-ISICOFF PA MIAMI |
| 2026-01-08 | discover_credit | RIFKIN & FOX-ISICOFF PA MIAMI FL | 250 | other | RIFKIN & FOX-ISICOFF PA MIAMI |

These two transactions should cancel each other out and should not appear in spending totals.

---

## 5. Update Dashboard Charts

The dashboard should be updated to focus on monthly spending trends, category composition, top spending areas, category trends, and budget comparison.

---

### Chart 1: Monthly Total Spending

Place this chart at the top of the dashboard.

Use a line chart.

Purpose:

- Show the trend of total monthly spending over time.

Chart design:

- X-axis: Month
- Y-axis: Total spending amount
- Optional: Add a budget line

This should be the main overview chart.

---

### Chart 2: Category Breakdown

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

### Chart 3: Top Categories

Use a horizontal bar chart.

Purpose:

- Show where most money was spent over the past 3, 6, or 12 months.

Chart design:

- Y-axis: Category
- X-axis: Spending amount
- Sort categories from highest to lowest spending

This chart should make it easy to compare spending across categories.

---

### Chart 4: Category Trend

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

### Chart 5: Budget vs Actual

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
