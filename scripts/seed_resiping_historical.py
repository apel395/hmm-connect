#!/usr/bin/env python3
"""Seed flat RESIPING historical workbook into item/supplier masters, GR, invoices and journals.

Dry-run is the default. Use --apply only after reviewing all BLOCKED rows.

Expected columns:
tanggal penerimaan | nama supplier | lokasi | nama barang | deskripsi | satuan |
jumlah diterima | harga satuan | tanggal invoice/tagihan | ... | pajak | total
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "resiping-historical-seed-local-0123456789abcdef")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, text as sql_text

from app.core.database import SessionLocal
from app.models.business_unit import BusinessUnit
from app.models.chart_of_account import ChartOfAccount
from app.models.department import Department
from app.models.goods_receipt import GoodsReceipt
from app.models.journal_entry import JournalEntry
from app.models.location import Location
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.goods_receipt import GoodsReceiptCreate, GoodsReceiptItemCreate
from app.schemas.supplier_invoice import SupplierInvoiceInput, SupplierInvoiceLineInput
from app.services.goods_receipt_service import GoodsReceiptService
from app.services.supplier_invoice_service import SupplierInvoiceService
from scripts.hmm_item_code_format import allocate_code, infer_class

try:
    from app.api.v1 import journals
except ImportError:
    journals = None

try:
    from openpyxl import load_workbook
except ImportError:
    raise SystemExit("openpyxl is required")

ZERO = Decimal("0")
GROUP_COA = {
    "1": ("100-300-100", "500-100-100", "500-100-100"),
    "2": ("100-300-500", "500-100-102", "500-100-102"),
    "3": ("100-300-700", "500-100-999", "500-100-999"),
    "4": ("100-300-999", "500-100-999", "500-100-999"),
}
SUBGROUP_COA = {"3-6": ("100-300-800", "500-100-999", "500-100-999")}

def args():
    p=argparse.ArgumentParser()
    p.add_argument("--workbook", required=True)
    p.add_argument("--user", default="admin")
    p.add_argument("--department-code", default=None,
                   help="Optional override. Default resolves a department linked to each location.")
    p.add_argument("--warehouse-code", default=None)
    p.add_argument("--apply", action="store_true")
    return p.parse_args()

def text(v): return re.sub(r"\s+", " ", str(v or "").strip())

def dec(v):
    if v in (None, ""): return None
    try: return Decimal(str(v).replace(",", "").strip())
    except (InvalidOperation, ValueError): return None

def as_date(v):
    if isinstance(v, datetime): return v.date()
    if isinstance(v, date): return v
    return None

def supplier_key(name):
    n=text(name).upper()
    for prefix in ("PT. ","PT ","CV. ","CV ","UD. ","UD ","TOKO "):
        if n.startswith(prefix): return n[len(prefix):]
    return n

def coa_id(db, number):
    a=db.query(ChartOfAccount).filter(ChartOfAccount.account_number==number).first()
    return a.id if a else None

def product_accounts(db, cls):
    nums=SUBGROUP_COA.get(cls.subgroup_code) or GROUP_COA[cls.group_code]
    return tuple(coa_id(db,n) for n in nums)

def resolve_location(db, raw):
    key=text(raw).upper()
    # Historical source aliases. BSP PEDADA was a source-label mistake; the real
    # production site is Zamped/Zamrud (location id 4 / code 003).
    aliases={
        # Historical workbook label -> current app-managed stable location code.
        "MINAS": ("code", "005"),       # Rumin
        "RUMBAI": ("code", "005"),      # Rumin
        "HEAD OFFICE": ("code", "002"), # Pekanbaru
        "BSP PEDADA": ("code", "003"),  # Zamped / Zamrud
        "PEDADA": ("code", "003"),      # historical source-label mistake
        "DURI": ("code", "006"),        # Duri
        "NKL": ("code", "007"),         # Kalimantan / Sanga-sanga
    }
    if key in aliases:
        field, value=aliases[key]
        col=Location.code if field=="code" else Location.name
        return db.query(Location).filter(func.upper(col)==value).first()
    # Do not guess unresolved historical sites such as RUMBAI/NKL.
    return db.query(Location).filter(func.upper(Location.name)==key).first() or \
           db.query(Location).filter(func.upper(Location.code)==key).first()

def resolve_department(db, location, override_code=None):
    if override_code:
        dept=db.query(Department).filter(
            Department.code==override_code,
            Department.business_unit_id==location.business_unit_id,
            Department.is_active.is_(True),
        ).first()
        return dept

    linked_ids=[
        row[0] for row in db.execute(
            sql_text("SELECT department_id FROM location_departments WHERE location_id=:location_id"),
            {"location_id": location.id},
        ).all()
    ]
    # Project Catering locations use operational department first. Head Office
    # uses Head Office when linked; otherwise fall back to the first active,
    # explicitly linked department.
    # Business rule: Head Office uses department 02; every other
    # Project Catering location uses Operational department 01.
    preferred=["02"] if location.location_type=="HEAD_OFFICE" else ["01","OPR"]
    q=db.query(Department).filter(
        Department.business_unit_id==location.business_unit_id,
        Department.is_active.is_(True),
    )
    if linked_ids:
        q=q.filter(Department.id.in_(linked_ids))
    departments=q.all()
    by_code={d.code:d for d in departments}
    for code in preferred:
        if code in by_code:
            return by_code[code]
    return sorted(departments,key=lambda d:d.id)[0] if departments else None

def resolve_supplier(db, raw, cache, stats):
    key=supplier_key(raw)
    if key in cache: return cache[key]
    for s in db.query(Supplier).all():
        if supplier_key(s.name)==key:
            cache[key]=s; return s
    seq=(db.query(func.count(Supplier.id)).scalar() or 0)+1
    s=Supplier(code=f"HIST-SUP-{seq:05d}", name=text(raw).upper(), is_active=True,
               bank_name="", bank_account_number="", bank_account_name=text(raw).upper())
    db.add(s); db.flush(); cache[key]=s; stats["suppliers"]+=1
    return s

def resolve_product(db, name, description, uom, occupied, cache, stats):
    key=text(name).upper()
    if key in cache: return cache[key]
    p=db.query(Product).filter(func.upper(Product.name)==key).first()
    if p: cache[key]=p; return p
    cls=infer_class(key)
    code=allocate_code(cls, occupied)
    inv,pur,cogs=product_accounts(db,cls)
    p=Product(code=code,name=key,description=text(description) or None,
        group_code=cls.group_code,group_name=cls.group_name,
        subgroup_code=cls.subgroup_code,subgroup_name=cls.subgroup_name,
        uom=text(uom).upper() or "PCS",usage_uom=text(uom).upper() or "PCS",
        conversion=Decimal("1"),cost_price=ZERO,selling_price=ZERO,
        minimum_stock=ZERO,reorder_level=ZERO,maximum_stock=ZERO,lead_time_days=0,
        inventory_account_id=inv,purchase_account_id=pur,cogs_account_id=cogs,
        tax_category="NON_TAXABLE",is_taxable=False,tax_rate=ZERO,is_active=True)
    db.add(p); db.flush(); cache[key]=p; stats["products"]+=1
    return p

def parse_source_date(v):
    d=as_date(v)
    if d:
        return d
    raw=text(v).upper()
    if not raw:
        return None
    months={
        "JANUARY":1,"JANUARI":1,"FEBRUARY":2,"FEBRUARI":2,"MARCH":3,"MARET":3,
        "APRIL":4,"MAY":5,"MEI":5,"JUNE":6,"JUNI":6,"JULY":7,"JULI":7,
        "AUGUST":8,"AGUSTUS":8,"SEPTEMBER":9,"SEPTEMBER":9,"OCTOBER":10,"OKTOBER":10,
        "NOVEMBER":11,"NOVEMBER":11,"DECEMBER":12,"DESEMBER":12,
    }
    m=re.search(r"(\\d{1,2})(?:\\s*-\\s*\\d{1,2})?\\s+([A-Z]+)\\s+(20\\d{2})",raw)
    if not m:
        return None
    day=int(m.group(1)); month=months.get(m.group(2)); year=int(m.group(3))
    if not month:
        return None
    try:
        return date(year,month,day)
    except ValueError:
        return None

def parse(ws):
    blocks=[]; current=None
    for row_no,row in enumerate(ws.iter_rows(min_row=2,values_only=True),start=2):
        a,b,c,d,e,f,g,h,i,_,tax,total=(list(row)+[None]*12)[:12]
        source_date=parse_source_date(a)
        if b:
            current={"row":row_no,"supplier":text(b),"location":text(c),
                     "header_date":source_date,"invoice_date":as_date(i),"items":[]}
            blocks.append(current)
        if current is None:
            continue
        if source_date:
            current["header_date"]=source_date
        item_name=text(d)
        description=text(e)
        qty=dec(g); price=dec(h)
        if (item_name or description) and (qty is not None or price is not None):
            current["items"].append({"row":row_no,"date":source_date or current["header_date"],
                "name":item_name or description,"description":description,"uom":text(f),
                "qty":qty,"price":price})
    return blocks

def main():
    a=args(); dry=not a.apply
    wb=load_workbook(a.workbook,read_only=True,data_only=True)
    ws=wb[wb.sheetnames[0]]
    blocks=parse(ws)
    db=SessionLocal()
    stats=defaultdict(int); blocked=[]; supplier_cache={}; product_cache={}
    occupied={str(x[0]).upper() for x in db.query(Product.code).all() if x[0]}
    try:
        user=db.query(User).filter(User.username==a.user).first()
        if not user: raise RuntimeError(f"user {a.user!r} not found")
        for n,block in enumerate(blocks,1):
            loc=resolve_location(db,block["location"])
            if not loc:
                blocked.append((block["row"],"LOCATION",block["location"])); continue
            bu=db.get(BusinessUnit,loc.business_unit_id) if loc.business_unit_id else None
            if not bu:
                blocked.append((block["row"],"BUSINESS_UNIT",block["location"])); continue
            dept=resolve_department(db,loc,a.department_code)
            if not dept:
                blocked.append((block["row"],"DEPARTMENT",f"{block['location']} / location_id={loc.id}")); continue
            supplier=resolve_supplier(db,block["supplier"],supplier_cache,stats)
            warehouse=None
            if a.warehouse_code:
                warehouse=db.query(Warehouse).filter(Warehouse.code==a.warehouse_code).first()
            if not warehouse:
                warehouse=db.query(Warehouse).filter(Warehouse.location_id==loc.id).first()
            if not warehouse:
                warehouse=db.query(Warehouse).filter(Warehouse.code=="MAIN").first()

            ready=[]
            for x in block["items"]:
                if not x["date"]: blocked.append((x["row"],"DATE",x["name"])); continue
                if x["qty"] is None or x["qty"]<=0: blocked.append((x["row"],"QTY",x["name"])); continue
                if x["price"] is None or x["price"]<=0: blocked.append((x["row"],"PRICE",x["name"])); continue
                # Laundry is service expense and PC is a fixed asset; do not create stock GR for them.
                upper=(x["name"]+" "+x["description"]).upper()
                if "LAUNDRY" in upper or "PC RAKITAN" in upper or "INTEL I5-4590" in upper:
                    blocked.append((x["row"],"DIRECT_INVOICE_REQUIRED",x["name"])); continue
                p=resolve_product(db,x["name"],x["description"],x["uom"],occupied,product_cache,stats)
                ready.append((x,p))
            if not ready: continue
            if dry:
                stats["dry_blocks"]+=1; stats["dry_lines"]+=len(ready); continue
            receipt_date=min(x["date"] for x,_ in ready)
            ext=f"RESIPING-{block['row']}-{supplier.id}-{loc.id}"
            existing=db.query(GoodsReceipt).filter(GoodsReceipt.external_reference==ext).first()
            if existing:
                stats["skipped"]+=1; continue
            gr=GoodsReceiptService.create(db,data=GoodsReceiptCreate(
                supplier_id=supplier.id,business_unit_id=bu.id,location_id=loc.id,
                department_id=dept.id,received_at=datetime.combine(receipt_date,datetime.min.time(),tzinfo=timezone.utc),
                source_type="HISTORICAL_IMPORT",external_reference=ext,destination_type="WAREHOUSE",
                warehouse_id=warehouse.id if warehouse else None,
                notes=f"RESIPING historical import rows from {block['row']}",
                items=[GoodsReceiptItemCreate(product_id=p.id,quantity=x["qty"],unit_cost=x["price"],
                       is_taxable=False,tax_rate=ZERO) for x,p in ready]),user=user)
            gr=GoodsReceiptService.post(db,receipt_id=gr.id,user=user)
            if journals is not None:
                j=db.query(JournalEntry).filter(JournalEntry.reference_type=="GOODS_RECEIPT",
                    JournalEntry.reference_id==gr.id).first()
                if j and j.status=="DRAFT": journals.post(j.id,db,user)
            inv_date=block["invoice_date"] or receipt_date
            svc=SupplierInvoiceService(db)
            inv=svc.create(SupplierInvoiceInput(
                supplier_invoice_number=f"HIST-RESIPING-{block['row']}",supplier_id=supplier.id,
                invoice_date=inv_date,received_date=inv_date,due_date=inv_date+timedelta(days=30),
                goods_receipt_id=gr.id,business_unit_id=bu.id,department_id=dept.id,location_id=loc.id,
                currency="IDR",discount_amount=ZERO,tax_amount=ZERO,withholding_tax_amount=ZERO,
                notes=f"RESIPING historical import rows from {block['row']}",source_type="HISTORICAL_IMPORT",
                lines=[SupplierInvoiceLineInput(product_id=p.id,goods_receipt_item_id=gr.items[i].id,
                    description=x["description"] or x["name"],quantity=x["qty"],uom=p.uom or "PCS",
                    unit_price=x["price"],is_taxable=False,tax_rate=ZERO,tax_amount=ZERO,
                    account_id=None,department_id=dept.id) for i,(x,p) in enumerate(ready)]),user)
            inv=svc.verify(inv,user)
            if journals is not None:
                j=svc.generate_journal(inv,user)
                if j.status=="DRAFT": journals.post(j.id,db,user)
            stats["posted_blocks"]+=1; stats["posted_lines"]+=len(ready)
        if dry: db.rollback()
        else: db.commit()
        print("MODE:", "DRY RUN" if dry else "APPLIED")
        print("blocks:",len(blocks),"products_new:",stats["products"],"suppliers_new:",stats["suppliers"])
        print("ready_blocks:",stats["dry_blocks"] if dry else stats["posted_blocks"],
              "ready_lines:",stats["dry_lines"] if dry else stats["posted_lines"],"skipped:",stats["skipped"])
        print("BLOCKED:",len(blocked))
        for row,reason,value in blocked:
            print(f"  row {row}: {reason}: {value}")
        if blocked:
            print("Blocked rows were NOT posted. Fix evidence/classification before importing them.")
    except Exception:
        db.rollback(); raise
    finally:
        db.close(); wb.close()

if __name__=="__main__":
    main()
