import csv
from io import StringIO

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse


def flatten_sections(report):
    rows = []
    for section in report["sections"]:
        rows.append(
            (
                section["label"],
                section["total"],
                section.get("comparative_total"),
                section.get("variance_amount"),
                section.get("variance_percentage"),
                "section",
            )
        )
        for group in section["groups"]:
            rows.append(
                (
                    f"  {group['label']}",
                    group["total"],
                    group.get("comparative_total"),
                    group.get("variance_amount"),
                    group.get("variance_percentage"),
                    "group",
                )
            )
            for account in group["accounts"]:
                code = account.get("account_code") or ""
                label = f"    {code}{' — ' if code else ''}{account['account_name']}"
                rows.append(
                    (
                        label,
                        account["current_amount"],
                        account.get("comparative_amount"),
                        account.get("variance_amount"),
                        account.get("variance_percentage"),
                        "account",
                    )
                )
    return rows


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

    headers = [
        "Account / Section",
        "Current Amount",
        "Comparative Amount",
        "Variance",
        "Variance %",
    ]
    rows = flatten_sections(report)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([report_name])
    writer.writerow([period])
    writer.writerow([f"Filters: {filters}"])
    writer.writerow([])
    writer.writerow(headers)
    for label, current, comparative, variance, percentage, _ in rows:
        writer.writerow([label, current, comparative, variance, percentage])
    for label, value in summary_rows:
        writer.writerow([label, value, "", "", ""])

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )
