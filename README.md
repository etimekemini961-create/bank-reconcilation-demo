# Bank Reconciliation Demo

A Python command-line project that compares two transaction statement CSV files and writes a reconciliation report.

This is a learning and portfolio prototype. It uses synthetic data only. It is not production banking software, and a reported mismatch does not by itself prove an error or fraud.

## What it does

- Compares transactions using their reference.
- Reports matched entries, duplicates, missing entries, amount mismatches, and date mismatches.
- Supports an optional date tolerance in days.
- Saves results to `reconciliation_report.csv`.
- Uses Python's `Decimal` type when comparing monetary amounts.

## Requirements

- Python 3.15
- PowerShell on Windows

## Run with the sample statements

From the project folder:

```powershell
py -3.15 .\reconcile.py
```

If the sample statement files do not exist yet, the program creates `bank_a.csv` and `bank_b.csv` with synthetic example data.

## Compare selected statement files

Both CSV files must have these column names:

```text
reference,amount,date
```

Example row:

```text
TX1001,125.50,2026-11-01
```

Run the program with specific input and output paths:

```powershell
py -3.15 .\reconcile.py --bank-a .\bank_a.csv --bank-b .\bank_b.csv --output .\reconciliation_report.csv
```

## Date tolerance

By default, dates must match exactly. To allow a difference of up to one day when the reference appears once in each statement and the amounts match, run:

```powershell
py -3.15 .\reconcile.py --date-tolerance-days 1
```

The report records the selected tolerance. Only use a tolerance that fits the rules of the process being modeled.

## Result statuses

- `matched`: reference, amount, and date match.
- `matched_with_date_tolerance`: reference and amount match, and the date difference is within the selected tolerance.
- `duplicate`: a reference appears more than once in either statement.
- `amount_mismatch`: a reference appears in both statements, but the amounts differ.
- `date_mismatch`: a reference and amount match, but the date difference exceeds the selected tolerance.
- `missing_from_bank_a`: the reference appears only in Bank B.
- `missing_from_bank_b`: the reference appears only in Bank A.

The `difference` column is calculated as Bank A total minus Bank B total.

## Files

```text
bank-reconciliation-demo/
├── reconcile.py
├── bank_a.csv
├── bank_b.csv
└── reconciliation_report.csv
```

The report and sample statements are generated or updated by the program. Use synthetic data only; do not put real customer, bank, or payment information in this project.