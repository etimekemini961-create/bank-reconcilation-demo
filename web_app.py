import csv
import io
import tempfile
from collections import Counter
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from reconcile import load_statement, reconcile as reconcile_transactions

app = FastAPI(title="Bank Reconciliation Demo")

MAX_FILE_SIZE = 2 * 1024 * 1024

REPORT_FIELDS = [
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

STATUS_ORDER = [
    "matched",
    "matched_with_date_tolerance",
    "duplicate",
    "amount_mismatch",
    "date_mismatch",
    "missing_from_bank_a",
    "missing_from_bank_b",
]

PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bank Reconciliation Demo</title>
  <style>
    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      padding: 32px 16px;
      color: #f5f1e6;
      font-family: "Segoe UI", Arial, sans-serif;
      background:
        radial-gradient(ellipse at 15% 0%, #30250c 0, transparent 38%),
        linear-gradient(145deg, #090909, #11100d 65%, #080808);
    }

    main {
      width: min(1100px, 100%);
      margin: 0 auto;
    }

    .panel {
      margin-bottom: 20px;
      padding: 24px;
      border: 1px solid #514322;
      border-radius: 18px;
      background: #141310;
      box-shadow: 0 16px 45px rgb(0 0 0 / 32%);
    }

    h1, h2 { color: #f1cc63; }
    h1 { margin-top: 0; }
    p { color: #c8c0ae; line-height: 1.5; }

    label {
      display: block;
      margin-top: 18px;
      color: #e6c45a;
      font-weight: 650;
    }

    input {
      display: block;
      width: 100%;
      margin-top: 8px;
      padding: 12px;
      border: 1px solid #66521b;
      border-radius: 9px;
      color: #f5f1e6;
      background: #0d0d0c;
      font: inherit;
    }

    button {
      margin-top: 20px;
      padding: 11px 16px;
      border: 1px solid #e0bd4f;
      border-radius: 10px;
      color: #171307;
      background: #d4af37;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }

    button:hover { background: #f1cc63; }
    button:disabled { opacity: .6; cursor: wait; }
    .notice, #message { color: #e6c45a; }
    #message.error { color: #ffb4a8; }
    #results[hidden] { display: none; }

    .summary {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      margin: 16px 0;
    }

    .summary-card {
      padding: 14px;
      border: 1px solid #514322;
      border-radius: 12px;
      background: #0d0d0c;
    }

    .summary-count {
      display: block;
      margin-bottom: 6px;
      color: #e6c45a;
      font-size: 24px;
      font-weight: 700;
    }

    .table-wrap { overflow-x: auto; }

    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
    }

    th, td {
      padding: 11px 12px;
      border-bottom: 1px solid #332b18;
      vertical-align: top;
    }

    th {
      color: #d4af37;
      font-size: 12px;
      text-transform: uppercase;
    }

    .empty { color: #c8c0ae; text-align: center; }

    @media (max-width: 520px) {
      body { padding: 18px 10px; }
      .panel { padding: 18px 14px; }
    }
  </style>
</head>
<body>
  <main>
    <section class="panel">
      <h1>Bank Reconciliation</h1>
      <p>
        Select two CSV statements to compare. They must include the columns
        <strong>reference, amount, date</strong>.
      </p>
      <p class="notice">
        Learning demo only. Use synthetic data; do not upload real customer,
        bank, or payment records. Each file must be no larger than 2 MB.
      </p>

      <form id="reconcile-form">
        <label>
          Bank A statement
          <input type="file" name="bank_a" accept=".csv" required>
        </label>

        <label>
          Bank B statement
          <input type="file" name="bank_b" accept=".csv" required>
        </label>

        <label>
          Date tolerance in days
          <input
            type="number"
            name="date_tolerance_days"
            min="0"
            max="365"
            value="0"
            required
          >
        </label>

        <button id="submit-button" type="submit">Reconcile statements</button>
      </form>
      <p id="message" role="status"></p>
    </section>

    <section id="results" class="panel" hidden>
      <h2>Results summary</h2>
      <div id="summary" class="summary"></div>

      <h2>Transaction details</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Reference</th>
              <th>Status</th>
              <th>Bank A total</th>
              <th>Bank B total</th>
              <th>Bank A dates</th>
              <th>Bank B dates</th>
              <th>Difference</th>
              <th>Date difference</th>
            </tr>
          </thead>
          <tbody id="results-body"></tbody>
        </table>
      </div>

      <button id="download-button" type="button">Download CSV report</button>
    </section>
  </main>

  <script>
    const form = document.getElementById("reconcile-form");
    const message = document.getElementById("message");
    const submitButton = document.getElementById("submit-button");
    const resultsSection = document.getElementById("results");
    const summaryBox = document.getElementById("summary");
    const resultsBody = document.getElementById("results-body");
    const downloadButton = document.getElementById("download-button");

    let latestReport = null;

    const statusLabels = [
      ["matched", "Matched"],
      ["matched_with_date_tolerance", "Matched with date tolerance"],
      ["duplicate", "Duplicate"],
      ["amount_mismatch", "Amount mismatch"],
      ["date_mismatch", "Date mismatch"],
      ["missing_from_bank_a", "Missing from Bank A"],
      ["missing_from_bank_b", "Missing from Bank B"]
    ];

    function addCell(row, value) {
      const cell = document.createElement("td");
      cell.textContent = value ?? "";
      row.appendChild(cell);
    }

    function renderResults(data) {
      latestReport = data;
      summaryBox.replaceChildren();
      resultsBody.replaceChildren();

      for (const [status, label] of statusLabels) {
        const card = document.createElement("div");
        card.className = "summary-card";

        const count = document.createElement("span");
        count.className = "summary-count";
        count.textContent = String(data.summary[status] || 0);

        const description = document.createElement("span");
        description.textContent = label;

        card.append(count, description);
        summaryBox.appendChild(card);
      }

      if (data.rows.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 8;
        cell.className = "empty";
        cell.textContent = "No transactions were found in the two statements.";
        row.appendChild(cell);
        resultsBody.appendChild(row);
      } else {
        for (const item of data.rows) {
          const row = document.createElement("tr");

          addCell(row, item.reference);
          addCell(row, item.status);
          addCell(row, item.bank_a_total);
          addCell(row, item.bank_b_total);
          addCell(row, item.bank_a_dates || "—");
          addCell(row, item.bank_b_dates || "—");
          addCell(row, item.difference);

          const dateDifference = item.date_difference_days === ""
            ? "—"
            : `${item.date_difference_days} day(s)`;

          addCell(row, dateDifference);
          resultsBody.appendChild(row);
        }
      }

      resultsSection.hidden = false;
    }

    form.addEventListener("submit", async event => {
      event.preventDefault();
      message.className = "";
      message.textContent = "Comparing statements…";
      submitButton.disabled = true;
      resultsSection.hidden = true;

      try {
        const response = await fetch("/reconcile", {
          method: "POST",
          body: new FormData(form)
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
          throw new Error(data.detail || "Could not reconcile these files.");
        }

        renderResults(data);
        message.textContent = "Reconciliation complete.";
      } catch (error) {
        message.className = "error";
        message.textContent = error.message;
      } finally {
        submitButton.disabled = false;
      }
    });

    downloadButton.addEventListener("click", () => {
      if (!latestReport) return;

      const fields = latestReport.fields;
      const lines = [
        fields.map(csvValue).join(","),
        ...latestReport.rows.map(row =>
          fields.map(field => csvValue(row[field])).join(",")
        )
      ];

      const blob = new Blob(["\\uFEFF" + lines.join("\\r\\n")], {
        type: "text/csv;charset=utf-8"
      });

      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "reconciliation_report.csv";
      link.click();
      URL.revokeObjectURL(url);
    });

    function csvValue(value) {
      const text = String(value ?? "");
      return '"' + text.replaceAll('"', '""') + '"';
    }
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE


@app.post("/reconcile")
async def reconcile_files(
    bank_a: UploadFile = File(...),
    bank_b: UploadFile = File(...),
    date_tolerance_days: int = Form(0),
):
    if date_tolerance_days < 0 or date_tolerance_days > 365:
        raise HTTPException(
            status_code=400,
            detail="Date tolerance must be between 0 and 365 days.",
        )

    for upload in (bank_a, bank_b):
        filename = upload.filename or ""
        if Path(filename).suffix.lower() != ".csv":
            raise HTTPException(
                status_code=400,
                detail="Please select CSV files for both statements.",
            )

    contents_a = await bank_a.read(MAX_FILE_SIZE + 1)
    contents_b = await bank_b.read(MAX_FILE_SIZE + 1)

    if len(contents_a) > MAX_FILE_SIZE or len(contents_b) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Each CSV file must be no larger than 2 MB.",
        )

    try:
        with tempfile.TemporaryDirectory() as temporary_folder:
            bank_a_path = Path(temporary_folder) / "bank_a.csv"
            bank_b_path = Path(temporary_folder) / "bank_b.csv"

            bank_a_path.write_bytes(contents_a)
            bank_b_path.write_bytes(contents_b)

            statement_a = load_statement(bank_a_path)
            statement_b = load_statement(bank_b_path)
            report = reconcile_transactions(
                statement_a,
                statement_b,
                date_tolerance_days,
            )

        summary_counts = Counter(row["status"] for row in report)
        summary = {
            status: summary_counts.get(status, 0)
            for status in STATUS_ORDER
        }

        return {
            "fields": REPORT_FIELDS,
            "summary": summary,
            "rows": report,
        }

    except (OSError, UnicodeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error))