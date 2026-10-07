import csv
from io import StringIO

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse


def _schema(report):
    if not report.get("sections"):
        return "current_comparative"
    first = report["sections"][0]
    if isinstance(first.get("sections"), list):
        return "fiscal_neraca"
    for section in report["sections"]:
        for group in section.get("groups", []):
            for account in group.get("accounts", []):
                return "opening_closing" if "closing_amount" in account else "current_comparative"
        return "opening_closing" if "closing_total" in section else "current_comparative"
    return "current_comparative"


def _account_values(account, schema):
    if schema == "opening_closing":
        return (account["opening_amount"], account["closing_amount"], "", "")
    return (account.get("current_amount"), account.get("comparative_amount"), account.get("variance_amount"), account.get("variance_percentage"))


def _group_values(group, schema):
    if schema == "opening_closing":
        return (group["opening_total"], group["closing_total"], "", "")
    return (group.get("total"), group.get("comparative_total"), group.get("variance_amount"), group.get("variance_percentage"))


def _section_values(section, schema):
    if schema == "opening_closing":
        return (section["opening_total"], section["closing_total"], "", "")
    return (section.get("total"), section.get("comparative_total"), section.get("variance_amount"), section.get("variance_percentage"))


def flatten_sections(report):
    schema = _schema(report)
    rows = []
    if schema == "fiscal_neraca":
        for top in report["sections"]:
            rows.append((top["label"], (top.get("total"),), "section"))
            for sub in top.get("sections", []):
                rows.append((f"  {sub['label']}", ("",), "group"))
                for line in sub.get("lines", []):
                    label = f"    {line['fiscal_code']} — {line['account_name']}"
                    rows.append((label, (line["amount"],), "account"))
                rows.append((f"  Subtotal {sub['label']}", (sub.get("total"),), "subtotal"))
        return rows, schema
    for section in report["sections"]:
        rows.append((section["label"], _section_values(section, schema), "section"))
        for group in section["groups"]:
            rows.append((f"  {group['label']}", _group_values(group, schema), "group"))
            for account in group["accounts"]:
                code = account.get("account_code") or ""
                label = f"    {account['account_name']}"
                rows.append((label, _account_values(account, schema), "account"))
    return rows, schema


def export_statement(report, report_name, period, filters, format, filename, summary_rows):
    """Export a financial statement in a Lambda-safe format.

    XLSX generation is intentionally not part of the Lambda runtime because it
    requires the worker-only ``openpyxl`` dependency. CSV remains available for
    browser downloads and can be converted to XLSX by the EC2/manual worker.
    """
    if format.lower() != "csv":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={
                "code": "XLSX_EXPORT_NOT_AVAILABLE",
                "message": "XLSX export is available only through the EC2 reporting worker. Use CSV export from the API.",
            },
        )

    rows, schema = flatten_sections(report)
    if schema == "opening_closing":
        headers = ["Account / Section", "Opening Amount", "Closing Amount", "", ""]
    elif schema == "fiscal_neraca":
        headers = ["Account / Section", "Amount"]
    else:
        headers = ["Account / Section", "Current Amount", "Comparative Amount", "Variance", "Variance %"]
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([report_name])
    writer.writerow([period])
    writer.writerow([f"Filters: {filters}"])
    writer.writerow([])
    writer.writerow(headers)
    for label, values, _ in rows:
        writer.writerow([label, *values])
    for label in summary_rows:
        if isinstance(label, (tuple, list)):
            writer.writerow([label[0], label[1]])

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )
