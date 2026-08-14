"""Create repeatable XLSX samples for targeted Historical Import Center checks."""
from pathlib import Path
from openpyxl import Workbook
from app.services.historical_import_service import SPECS

OUTPUT = Path("samples/historical-import")
SAMPLES = {
    "purchase-order": ("PURCHASE_ORDER", [
        ["PO-HIST-SAMPLE-001","DIRECT","","DEV-SUP-001","2026-08-01","2026-08-10","DEV-PUR","DEV-PKU","IDR","APPROVED","DEV-ITEM-001","Cleaning Chemical",2,"LTR",150000,0,0,"Historical sample","ARCHIVE-2026-08"],
        ["PO-HIST-SAMPLE-001","DIRECT","","DEV-SUP-001","2026-08-01","2026-08-10","DEV-PUR","DEV-PKU","IDR","APPROVED","DEV-ITEM-003","Office Paper",3,"REAM",100000,0,0,"Historical sample","ARCHIVE-2026-08"],
    ]),
    "supplier-invoice": ("SUPPLIER_INVOICE", [
        ["INV-HIST-SAMPLE-001","SUP-HIST-001","DEV-SUP-001","2026-08-02","2026-08-02","2026-08-30","PO-HIST-SAMPLE-001","","DEV-FIN","DEV-PKU","IDR","POSTED","DEV-ITEM-001","Historical chemical invoice",1,"EA",300000,"510100",0,0,0,"Historical sample","ARCHIVE-2026-08"],
        ["INV-HIST-SAMPLE-002","SUP-HIST-002","DEV-SUP-001","2026-08-02","2026-08-02","2026-08-30","PO-HIST-SAMPLE-001","","DEV-FIN","DEV-PKU","IDR","POSTED","DEV-ITEM-003","Historical paper invoice",1,"EA",300000,"510200",0,0,0,"Historical sample","ARCHIVE-2026-08"],
    ]),
    "payment": ("PAYMENT", [
        ["PAY-HIST-SAMPLE-001","2026-08-03","DEV-SUP-001","BANK_TRANSFER","110100","IDR",450000,"BANK-HIST-001","","POSTED","SUP-HIST-001",300000,"Historical sample","ARCHIVE-2026-08"],
        ["PAY-HIST-SAMPLE-001","2026-08-03","DEV-SUP-001","BANK_TRANSFER","110100","IDR",450000,"BANK-HIST-001","","POSTED","SUP-HIST-002",150000,"Historical sample","ARCHIVE-2026-08"],
    ]),
    "journal-entry": ("JOURNAL_ENTRY", [
        ["JV-HIST-SAMPLE-001","2026-08-03","Historical office adjustment","HISTORICAL_IMPORT","ARCHIVE-2026-08","POSTED","510200","Office supplies expense",100000,0,"DEV-FIN","DEV-PKU","DEV-SUP-001","Historical sample"],
        ["JV-HIST-SAMPLE-001","2026-08-03","Historical office adjustment","HISTORICAL_IMPORT","ARCHIVE-2026-08","POSTED","110100","Bank adjustment",0,100000,"DEV-FIN","DEV-PKU","DEV-SUP-001","Historical sample"],
    ]),
}

def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    for slug,(kind,rows) in SAMPLES.items():
        wb=Workbook();ws=wb.active;ws.title="Import";ws.append(SPECS[kind])
        for row in rows:ws.append(row)
        notes=wb.create_sheet("Notes and Instructions");notes.append(["Purpose","Repeatable targeted development sample"]);notes.append(["Date format","YYYY-MM-DD"])
        path=OUTPUT/f"{slug}.xlsx";wb.save(path);print(path)

if __name__=="__main__":main()
