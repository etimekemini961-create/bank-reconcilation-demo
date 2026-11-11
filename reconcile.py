import argparse
import csv
from collections import Counter, defaultdict
from datetime import date as Date
from decimal import Decimal, InvalidOperation
from pathlib import Path

PROJECT_FOLDER = Path(__file__).resolve().parent
SAMPLE_BANK_A_FILE = PROJECT_FOLDER / "bank_a.csv"
SAMPLE_BANK_B_FILE = PROJECT_FOLDER / "bank_b.csv"
DEFAULT_REPORT_FILE = PROJECT_FOLDER / "reconciliation_report.csv"

SAMPLE_BANK_A = [
    {"reference": "TX1001", "amount": "125.50", "date": "2026-11-01"},
    {"reference": "TX1002", "amount": "80.00", "date": "2026-11-01"},
    {"reference": "TX1003", "amount": "42.75", "date": "2026-11-02"},
    {"reference": "TX1004", "amount": "19.99", "date": "2026-11-02"},
    {"reference": "TX1006", "amount": "10.00", "date": "2026-11-04"},
    {"reference": "TX1007", "amount": "25.00", "date": "2026-11-05"},
]

SAMPLE_BANK_B = [
    {"reference": "TX1001", "amount": "125.50", "date": "2026-11-01"},
    {"reference": "TX1002", "amount": "80.00", "date": "2026-11-01"},
    {"reference": "TX1003", "amount": "42.75", "date": "2026-11-02"},
    {"reference": "TX1003", "amount": "42.75", "date": "2026-11-02"},
    {"reference": "TX1005", "amount": "60.00", "date": "2026-11-03"},
    {"reference": "TX1006", "amount": "12.00", "date": "2026-11-04"},
    {"reference": "TX1007", "amount": "25.00", "date": "2026-11-06"},
]

REQUIRED_COLUMNS = {"reference", "amount", "date"}


def create_sample_file(file_path, rows):
    """Create a sample CSV only if it does not already exist."""
    if file_path.exists():
        return

    with file_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["reference", "amount", "date"])
        writer.writeheader()
        writer.writerows(rows)


def load_statement(file_path):
    """Read a CSV statement and validate its fields."""
    transactions = []

    with file_path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        columns = set(reader.fieldnames or [])
        missing_columns = REQUIRED_COLUMNS - columns

        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"{file_path.name} is missing columns: {missing}")

        for row_number, row in enumerate(reader, start=2):
            reference = (row.get("reference") or "").strip()
            date_text = (row.get("date") or "").strip()

            try:
                amount = Decimal((row.get("amount") or "").strip())
            except InvalidOperation:
                raise ValueError(
                    f"{file_path.name}, row {row_number}: "
                    "amount is not a valid number"
                )

            if not reference:
                raise ValueError(
                    f"{file_path.name}, row {row_number}: "
                    "reference cannot be blank"
                )

            if amount <= 0:
                raise ValueError(
                    f"{file_path.name}, row {row_number}: "
                    "amount must be greater than zero"
                )

            if not date_text:
                raise ValueError(
                    f"{file_path.name}, row {row_number}: "
                    "date cannot be blank"
                )

            try:
                Date.fromisoformat(date_text)
            except ValueError:
                raise ValueError(
                    f"{file_path.name}, row {row_number}: "
                    "date must use YYYY-MM-DD, for example 2026-11-05"
                )

            transactions.append({
                "reference": reference,
                "amount": amount,
                "date": date_text,
            })

    return transactions


def group_by_reference(transactions):
    grouped = defaultdict(list)

    for transaction in transactions:
        grouped[transaction["reference"]].append(transaction)

    return grouped


def reconcile(bank_a, bank_b, date_tolerance_days):
    """Compare transaction counts, totals, and dates by reference."""
    grouped_a = group_by_reference(bank_a)
    grouped_b = group_by_reference(bank_b)
    all_references = sorted(set(grouped_a) | set(grouped_b))
    report_rows = []

    for reference in all_references:
        entries_a = grouped_a.get(reference, [])
        entries_b = grouped_b.get(reference, [])

        total_a = sum(
            (entry["amount"] for entry in entries_a),
            Decimal("0.00"),
        )
        total_b = sum(
            (entry["amount"] for entry in entries_b),
            Decimal("0.00"),
        )

        dates_a = sorted({entry["date"] for entry in entries_a})
        dates_b = sorted({entry["date"] for entry in entries_b})

        date_difference_days = ""
        if len(entries_a) == 1 and len(entries_b) == 1:
            date_a = Date.fromisoformat(entries_a[0]["date"])
            date_b = Date.fromisoformat(entries_b[0]["date"])
            date_difference_days = abs((date_a - date_b).days)

        if not entries_a:
            status = "missing_from_bank_a"
        elif not entries_b:
            status = "missing_from_bank_b"
        elif len(entries_a) > 1 or len(entries_b) > 1:
            status = "duplicate"
        elif total_a != total_b:
            status = "amount_mismatch"
        elif date_difference_days == 0:
            status = "matched"
        elif date_difference_days <= date_tolerance_days:
            status = "matched_with_date_tolerance"
        else:
            status = "date_mismatch"

        report_rows.append({
            "reference": reference,
            "bank_a_count": len(entries_a),
            "bank_a_total": f"{total_a:.2f}",
            "bank_a_dates": ";".join(dates_a),
            "bank_b_count": len(entries_b),
            "bank_b_total": f"{total_b:.2f}",
            "bank_b_dates": ";".join(dates_b),
            "difference": f"{total_a - total_b:.2f}",
            "date_difference_days": date_difference_days,
            "date_tolerance_days": date_tolerance_days,
            "status": status,
        })

    return report_rows


def save_report(rows, file_path):
    fieldnames = [
        "reference",
        "bank_a_count",
        "bank_a_total",
        "bank_a_dates",
        "bank_b_count",
        "bank_b_total",
        "bank_b_dates",
        "difference",
        "date_difference_days",
        "date_tolerance_days",
        "status",
    ]

    with file_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Compare two CSV transaction statements."
    )
    parser.add_argument(
        "--bank-a",
        type=Path,
        help="Path to Bank A's CSV statement",
    )
    parser.add_argument(
        "--bank-b",
        type=Path,
        help="Path to Bank B's CSV statement",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT_FILE,
        help="Path for the reconciliation report CSV",
    )
    parser.add_argument(
        "--date-tolerance-days",
        type=int,
        default=0,
        help="Allowed difference between dates; defaults to 0 days",
    )
    args = parser.parse_args()

    if args.date_tolerance_days < 0:
        raise SystemExit("--date-tolerance-days cannot be negative.")

    if bool(args.bank_a) != bool(args.bank_b):
        raise SystemExit(
            "Please provide both --bank-a and --bank-b, or neither."
        )

    if args.bank_a is None:
        bank_a_path = SAMPLE_BANK_A_FILE
        bank_b_path = SAMPLE_BANK_B_FILE
        create_sample_file(bank_a_path, SAMPLE_BANK_A)
        create_sample_file(bank_b_path, SAMPLE_BANK_B)
    else:
        bank_a_path = args.bank_a
        bank_b_path = args.bank_b

    try:
        bank_a = load_statement(bank_a_path)
        bank_b = load_statement(bank_b_path)
        report = reconcile(
            bank_a,
            bank_b,
            args.date_tolerance_days,
        )
        save_report(report, args.output)
    except (OSError, ValueError) as error:
        raise SystemExit(f"Could not reconcile statements: {error}")

    print("Reconciliation results:")
    for row in report:
        print(
            f"{row['reference']}: {row['status']} "
            f"(Bank A: {row['bank_a_total']} on "
            f"{row['bank_a_dates'] or '—'}; "
            f"Bank B: {row['bank_b_total']} on "
            f"{row['bank_b_dates'] or '—'})"
        )

    counts = Counter(row["status"] for row in report)
    summary_order = [
        "matched",
        "matched_with_date_tolerance",
        "duplicate",
        "amount_mismatch",
        "date_mismatch",
        "missing_from_bank_a",
        "missing_from_bank_b",
    ]

    print("\nSummary:")
    for status in summary_order:
        label = status.replace("_", " ").title()
        print(f"{label}: {counts.get(status, 0)}")

    print(f"\nSaved reconciliation report to {args.output}")


if __name__ == "__main__":
    main()