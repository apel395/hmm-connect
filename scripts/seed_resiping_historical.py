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

# Source-proven corrections where a workbook cell contains a line total in the
# unit-price column. Keep these explicit and auditable rather than guessing.
SOURCE_UNIT_PRICE_OVERRIDES = {
    # MINERAL WATER: qty 16, H=128,000 while block subtotal L=1,463,000;
    # the same item is 8,000/bottle immediately above. 16 x 8,000 = 128,000.
    858: Decimal("8000"),
}

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
    p.add_argument("--start-row", type=int, default=2,
                   help="Ignore source item rows before this Excel row while retaining header/invoice context.")
    return p.parse_args()

def text(v): return re.sub(r"\s+", " ", str(v or "").strip())

def dec(v):
    if v in (None, ""):
        return None
    if isinstance(v, Decimal):
        return v
    if isinstance(v, (int, float)):
        return Decimal(str(v))
    raw=str(v).strip().replace(" ", "")
    # Workbook uses both 28,000.00 and 3,566,400,00.  The latter means
    # 3,566,400.00, not 356,640,000.
    if re.fullmatch(r"-?\d+,\d{1,2}", raw):
        # Decimal-comma quantities such as 1,5 / 124,74.
        raw=raw.replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(?:,\d{3})+,\d{1,2}", raw):
        # Thousands groups plus a 1-2 digit decimal tail, e.g. 39,000,0.
        left,right=raw.rsplit(",",1)
        raw=left.replace(",", "")+"."+right
    elif re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+\.\d{1,2}", raw):
        left,right=raw.rsplit(".",1)
        raw=left.replace(".", "")+"."+right
    else:
        raw=raw.replace(",", "")
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None

def tax_dec(v):
    value=dec(v)
    if value is None:
        return ZERO
    raw=text(v)
    # Historical tax cells such as 262 and 333.896 mean 262,000 and
    # 333,896 rupiah.  Keep ordinary values >= 1,000 unchanged.
    if value > ZERO and value < Decimal("1000"):
        if "." in raw or value == value.to_integral():
            return (value*Decimal("1000")).quantize(Decimal("1"))
    return value

def as_date(v):
    if isinstance(v, datetime): return v.date()
    if isinstance(v, date): return v
    return None

SUPPLIER_ALIASES={
    "IBU ERMY":"IBU ERNY",
    "PEMPEKL WENNY":"PEMPEK WENNY",
    "ROTI JALA DAN REMPEYELK":"ROTI JALA DAN REMPEYEK",
}

ITEM_ALIASES={
    "BAKSO IKAN 1 KG":"FISH BALL",
    "BEEF SAUSAGE 1KG":"BEEF SAUSAGE",
    "CHICKEN SAUSAGE 1 KG":"CHICKEN SAUSAGE",
    "CHEESE MOZARELLA {250GR]":"MOZZARELLA CHEESE",
    "CORN KERNEL 1 KG":"CORN KERNEL",
    "FRENCH FRIES CRINKLE CUT 1 KG":"FRENCH FRIES CRINKLE CUT",
    "FRENCH FRIES SHOESTRING 1 GR":"FRENCH FRIES SHOESTRING",
    "ICE CREAM VANILLA 8 L":"VANILLA ICE CREAM",
    "ICE CREAM REG. CUP VANILLA 75 ML @24":"VANILLA ICE CREAM CUP",
    "ICE CREAM REG. CUP VANILLA 75 ML @25":"VANILLA ICE CREAM CUP",
    "ICE CREAM REG. CUP VANILLA 75 ML @26":"VANILLA ICE CREAM CUP",
    "MIX VEGETABLE FROZEN 1 KG":"MIXED VEGETABLES FROZEN",
    "PUFF PASTRY SHEET 750 GR":"PUFF PASTRY SHEET",
    "BAKSO SAPI HALUS":"BEEF BALL",
    "BUTTER UNSALTED 200 GR":"UNSALTED BUTTER",
    "GREEN PEAS 1 KG":"GREEN PEAS",
    "MAYONNAISE 4L":"MAYONNAISE",
    "SUSU FULLCREAM 1 LITER @12":"FULL CREAM MILK",
    "BEEF MINCED":"MINCED BEEF",
    "ICE CREAM 3 RASA 8 L":"ICE CREAM 3 FLAVORS",
    "BEEF BALL 1 KG":"BEEF BALL",
    "DC AIR GALON":"DC AIR GALON",
    "DC AIR MINERAL 600 ML":"DC AIR MINERAL",
}

def canonical_item_name(name):
    key=text(name).upper()
    return ITEM_ALIASES.get(key,key)

def supplier_key(name):
    n=SUPPLIER_ALIASES.get(text(name).upper(), text(name).upper())
    for prefix in ("PT. ","PT ","CV. ","CV ","UD. ","UD ","TOKO "):
        if n.startswith(prefix):
            return n[len(prefix):]
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
        "RUMBAI MINAS": ("code", "005"),# Rumin
        "RUMBAI MINUS": ("code", "005"),# source typo for Rumbai/Minas
        "HEAD OFFICE": ("code", "002"), # Pekanbaru
        "BSP PEDADA": ("code", "003"),  # Zamped / Zamrud
        "PEDADA": ("code", "003"),      # historical source-label mistake
        "DURI": ("code", "006"),        # Duri
        "NKL": ("code", "007"),         # Kalimantan / Sanga-sanga
        "SANGASANGA": ("code", "007"),  # Kalimantan
        "SANGGASANGA": ("code", "007"), # source typo
        "SANGASANGA0": ("code", "007"), # source typo
        "SANGA-SANGA": ("code", "007"), # Kalimantan
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

def historical_inventory_override(db, key):
    upper=text(key).upper()
    # Boss-approved historical classification:
    # drinking water gallons/mineral water -> Inv Minuman; the remaining
    # historical food items (including Roti Jalah/Rempeyek) -> Inv Makanan.
    if "AIR GALON" in upper or "AIR MINERAL" in upper:
        return {
            "group_code":"2","group_name":"BEVERAGE",
            "subgroup_code":"2-1","subgroup_name":"MINERAL WATER",
            "inventory_account_id":coa_id(db,"100-300-500"),
        }
    if upper in {"ROTI JALAH","ROTI JALA","REMPEYEK"}:
        return {
            "group_code":"1","group_name":"FOOD",
            "subgroup_code":"1-9","subgroup_name":"SNACK",
            "inventory_account_id":coa_id(db,"100-300-100"),
        }
    return None


def resolve_product(db, name, description, uom, occupied, cache, stats, *, historical_stock=False):
    key=canonical_item_name(name)
    if key in cache:
        p=cache[key]
    else:
        p=db.query(Product).filter(func.upper(Product.name)==key).first()
        if not p:
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
                tax_category="NON_TAXABLE",is_taxable=False,tax_rate=ZERO,
                inventory_treatment="STOCK" if historical_stock else "REVIEW_REQUIRED",
                is_active=True)
            db.add(p); db.flush(); stats["products"]+=1
        cache[key]=p

    # The receiving workbook is source evidence that these positive qty/price
    # goods were physically received into site inventory.  Promote only unresolved
    # Item Master fields; never overwrite an explicit non-stock treatment or COA.
    if historical_stock:
        cls=infer_class(key)
        inv,pur,cogs=product_accounts(db,cls)
        override=historical_inventory_override(db,key)
        if override:
            p.group_code=override["group_code"]
            p.group_name=override["group_name"]
            p.subgroup_code=override["subgroup_code"]
            p.subgroup_name=override["subgroup_name"]
            p.inventory_account_id=override["inventory_account_id"]
            # Purchase/COGS follow the approved food/beverage group mapping.
            override_cls=infer_class("AIR MINERAL" if override["group_code"]=="2" else "ROTI")
            _,pur,cogs=product_accounts(db,override_cls)
            p.purchase_account_id=pur
            p.cogs_account_id=cogs
            stats["inventory_overrides"]+=1
        if str(getattr(p,"inventory_treatment","REVIEW_REQUIRED") or "REVIEW_REQUIRED").upper()=="REVIEW_REQUIRED":
            p.inventory_treatment="STOCK"
            stats["stock_classified"]+=1
        if not p.inventory_account_id:
            p.inventory_account_id=inv
        if not p.purchase_account_id:
            p.purchase_account_id=pur
        if not p.cogs_account_id:
            p.cogs_account_id=cogs
        if str(getattr(p,"tax_category","REVIEW_REQUIRED") or "REVIEW_REQUIRED").upper()=="REVIEW_REQUIRED":
            p.tax_category="NON_TAXABLE"
            p.is_taxable=False
            p.tax_rate=ZERO
            stats["tax_classified"]+=1
        db.flush()
    return p

def parse_source_date(v):
    d=as_date(v)
    if d:
        return d
    raw=text(v).upper()
    if not raw:
        return None
    months={
        "JANUARY":1,"JANUARI":1,"JAN":1,
        "FEBRUARY":2,"FEBRUARI":2,"FEB":2,
        "MARCH":3,"MARET":3,"MAR":3,
        "APRIL":4,"APR":4,
        "MAY":5,"MEI":5,
        "JUNE":6,"JUNI":6,"JUN":6,
        "JULY":7,"JULI":7,"JUL":7,
        "AUGUST":8,"AGUSTUS":8,"AUG":8,"AGU":8,
        "SEPTEMBER":9,"SEP":9,
        "OCTOBER":10,"OKTOBER":10,"OCT":10,"OKT":10,
        "NOVEMBER":11,"NOV":11,
        "DECEMBER":12,"DESEMBER":12,"DEC":12,"DES":12,
    }
    m=re.search(r"(\d{1,2})(?:\s*-\s*\d{1,2})?\s+([A-Z]+)\s+(20\d{2}|\d{2})(?!\d)",raw)
    if not m:
        return None
    day=int(m.group(1))
    month=months.get(m.group(2))
    year=int(m.group(3))
    if year < 100:
        year += 2000
    if not month:
        return None
    try:
        # For a historical range such as 15-21 DES 25, use the first day
        # (2025-12-15) as the receiving-history date for the block.
        return date(year,month,day)
    except ValueError:
        return None

def source_location_key(raw):
    key=text(raw).upper()
    aliases={
        "MINAS":"RUMIN",
        "RUMBAI":"RUMIN",
        "RUMBAI MINAS":"RUMIN",
        "RUMBAI MINUS":"RUMIN",
        "SANGASANGA":"KALIMANTAN",
        "SANGGASANGA":"KALIMANTAN",
        "SANGASANGA0":"KALIMANTAN",
        "SANGA-SANGA":"KALIMANTAN",
        "NKL":"KALIMANTAN",
        "HEAD OFFICE":"PEKANBARU",
        "BSP PEDADA":"ZAMPED",
        "PEDADA":"ZAMPED",
    }
    return aliases.get(key,key)

def parse(ws):
    """Parse source blocks and preserve TOTAL INVOICE as the invoice boundary.

    A non-empty column M starts one invoice.  Later header rows with the same
    supplier/location and blank column M are additional receiving blocks for
    that same invoice.  A supplier change without TOTAL INVOICE is deliberately
    left ungrouped and is not attached to the previous invoice.
    """
    blocks=[]
    current=None
    active_invoice=None
    invoice_seq=0
    for row_no,row in enumerate(ws.iter_rows(min_row=2,values_only=True),start=2):
        values=list(row)+[None]*13
        a,b,c,d,e,f,g,h,i,_,tax,total,total_invoice=values[:13]
        source_date=parse_source_date(a)
        if not source_date and isinstance(b,(date,datetime)):
            source_date=as_date(b)

        supplier_header=bool(b and not isinstance(b,(date,datetime)) and text(b))
        if supplier_header:
            block_supplier=text(b)
            block_location=text(c)
            invoice_total=dec(total_invoice)
            if invoice_total is not None:
                invoice_seq+=1
                active_invoice={
                    "id":invoice_seq,
                    "supplier_key":supplier_key(block_supplier),
                    "location":source_location_key(block_location),
                    "total":invoice_total,
                    "start_row":row_no,
                }
            elif not (
                active_invoice
                and supplier_key(block_supplier)==active_invoice["supplier_key"]
                and source_location_key(block_location)==active_invoice["location"]
            ):
                active_invoice=None

            current={
                "row":row_no,
                "supplier":block_supplier,
                "location":block_location,
                "header_date":source_date,
                "period_date":source_date,
                "invoice_date":as_date(i),
                "invoice_group_id":active_invoice["id"] if active_invoice else None,
                "invoice_total":active_invoice["total"] if active_invoice else None,
                "invoice_start_row":active_invoice["start_row"] if active_invoice else None,
                "declared_block_total":dec(total),
                "tax_raw":tax,
                "items":[],
            }
            blocks.append(current)

        if current is None:
            continue
        if source_date:
            period_date=current.get("period_date")
            # Correct an obvious source-year typo only when month/day are in the
            # header period's month (e.g. Suharti Dec-2026 rows under a Dec-2025
            # period header).  Cross-month anomalies are never guessed.
            if (
                period_date
                and source_date.year != period_date.year
                and source_date.month == period_date.month
                and abs(source_date.year-period_date.year) == 1
            ):
                source_date=source_date.replace(year=period_date.year)
            current["header_date"]=source_date

        d_text=text(d)
        e_text=text(e)
        category_headers={"FOOD","DRY GOODS","MONOUSE","BAVERAGE","BEVERAGE","VEGETABLE","FRUITS","FRESH/FROZEN"}
        if supplier_header and d_text and d_text.upper() not in category_headers and (dec(g) is not None or dec(h) is not None):
            item_name=d_text
        else:
            item_name=e_text or d_text
        description=e_text
        qty=dec(g)
        price=dec(h)
        if row_no in SOURCE_UNIT_PRICE_OVERRIDES:
            price=SOURCE_UNIT_PRICE_OVERRIDES[row_no]
        if item_name and (qty is not None or price is not None):
            current["items"].append({
                "row":row_no,
                "date":source_date or current["header_date"],
                "name":item_name,
                "description":description,
                "uom":text(f),
                "qty":qty,
                "price":price,
                "tax_raw":tax,
                "declared_total":dec(total),
            })
            if dec(total) is not None:
                current["declared_block_total"]=dec(total)
            if tax not in (None,""):
                current["tax_raw"]=tax
    return blocks

def invoice_group_key(block, supplier):
    group_id=block.get("invoice_group_id")
    return ("TOTAL_INVOICE", supplier.id, group_id) if group_id else None


DIRECT_INVOICE_KEYWORDS=("LAUNDRY","PC RAKITAN","INTEL I5-4590","GOJEK","UANG SAMPAH","BIAYA ADMIN")

# Historical direct-cost lines do not create stock receiving.  These mappings
# point to existing posting COAs in production and are snapshotted onto SI lines.
DIRECT_INVOICE_COA_RULES=(
    (("LAUNDRY",), "700-500-123"),                 # Laundry dan Dry Cleaning
    (("PC RAKITAN","INTEL I5-4590"), "700-500-121"), # Perangkat Lunak/Keras Komputer
    (("GOJEK",), "700-500-100"),                   # Transportasi dan Perjalanan Dinas
    (("UANG SAMPAH",), "750-100-999"),             # Beban Admin lainnya
    (("BIAYA ADMIN",), "700-500-122"),             # Biaya Admin Bank
)

def direct_invoice_account(db, item):
    upper=(item["name"]+" "+item["description"]).upper()
    for keywords,number in DIRECT_INVOICE_COA_RULES:
        if any(keyword in upper for keyword in keywords):
            account=db.query(ChartOfAccount).filter(
                ChartOfAccount.account_number==number,
                ChartOfAccount.is_active.is_(True),
                ChartOfAccount.is_posting.is_(True),
            ).first()
            if account and account.account_type=="EXPENSE" and account.normal_balance=="DEBIT":
                return account
            return None
    return None

def item_value(item):
    if item.get("qty") is None or item.get("price") is None:
        return None
    return Decimal(item["qty"])*Decimal(item["price"])

def exact_invoice_exclusion_rows(block):
    """Find a single received line explicitly outside the block invoice total.

    Used only when the source block total + tax proves that one line is not
    part of that invoice (Sukanda row 94 is the known case).
    """
    declared=block.get("declared_block_total")
    if declared is None:
        return set()
    tax=tax_dec(block.get("tax_raw"))
    valid=[item for item in block["items"] if item_value(item) is not None and item["qty"] > 0 and item["price"] > 0]
    received=sum((item_value(item) for item in valid),ZERO)
    target_subtotal=Decimal(declared)-Decimal(tax)
    excess=received-target_subtotal
    if excess <= ZERO:
        return set()
    matches=[item["row"] for item in valid if item_value(item)==excess]
    return {matches[0]} if len(matches)==1 else set()

def is_direct_invoice_item(item):
    upper=(item["name"]+" "+item["description"]).upper()
    return any(keyword in upper for keyword in DIRECT_INVOICE_KEYWORDS)

def main():
    a=args()
    dry=not a.apply
    wb=load_workbook(a.workbook,read_only=True,data_only=True)
    ws=wb[wb.sheetnames[0]]
    blocks=parse(ws)
    db=SessionLocal()
    stats=defaultdict(int)
    blocked=[]
    deferred=[]
    supplier_cache={}
    product_cache={}
    occupied={str(x[0]).upper() for x in db.query(Product.code).all() if x[0]}

    # TOTAL INVOICE is the source-of-truth invoice boundary.
    grouped_blocks=defaultdict(list)
    for block in blocks:
        group_id=block.get("invoice_group_id")
        if group_id is None:
            stats["without_total_invoice"]+=1
            deferred.append((block["row"],"NO_TOTAL_INVOICE",f"{block['supplier']} / {block['location']}"))
            continue
        grouped_blocks[group_id].append(block)

    # Start-row is a hard continuation boundary. Historical invoice groups that
    # end before it are ignored entirely. If the boundary cuts through an invoice
    # group, defer that group instead of creating a partial invoice.
    eligible_grouped_blocks={}
    for group_id,source_blocks in grouped_blocks.items():
        item_rows=[
            item["row"]
            for block in source_blocks
            for item in block["items"]
        ]
        group_start=int(source_blocks[0].get("invoice_start_row") or source_blocks[0]["row"])
        group_end=max(item_rows) if item_rows else group_start
        if group_end < a.start_row:
            stats["before_start_groups"]+=1
            continue
        if group_start < a.start_row <= group_end:
            stats["partial_start_groups"]+=1
            deferred.append((
                group_start,
                "PARTIAL_START_GROUP",
                f"source rows {group_start}-{group_end}; start-row={a.start_row}",
            ))
            continue
        eligible_grouped_blocks[group_id]=source_blocks
    grouped_blocks=eligible_grouped_blocks

    try:
        user=db.query(User).filter(User.username==a.user).first()
        if not user:
            raise RuntimeError(f"user {a.user!r} not found")

        variance_account=db.query(ChartOfAccount).filter(
            ChartOfAccount.account_number=="500-100-999",
            ChartOfAccount.is_active.is_(True),
        ).first()
        if not variance_account:
            raise RuntimeError("Historical invoice reconciliation requires active COA 500-100-999")

        svc=SupplierInvoiceService(db)
        preview_rows=[]

        for group_id in sorted(grouped_blocks):
            source_blocks=grouped_blocks[group_id]
            first=source_blocks[0]
            source_row=int(first["invoice_start_row"] or first["row"])
            raw_location=text(first["location"]).upper()

            if raw_location=="OPERATIONAL":
                stats["skipped_operational"]+=1
                deferred.append((source_row,"SKIP_OPERATIONAL",first["supplier"]))
                continue

            if not text(first["location"]):
                stats["skipped_empty_location"]+=1
                deferred.append((source_row,"SKIP_EMPTY_LOCATION",first["supplier"]))
                continue
            loc=resolve_location(db,first["location"])
            if not loc:
                blocked.append((source_row,"LOCATION",first["location"]))
                continue
            bu=db.get(BusinessUnit,loc.business_unit_id) if loc.business_unit_id else None
            if not bu:
                blocked.append((source_row,"BUSINESS_UNIT",first["location"]))
                continue
            dept=resolve_department(db,loc,a.department_code)
            if not dept:
                blocked.append((source_row,"DEPARTMENT",f"{first['location']} / location_id={loc.id}"))
                continue

            supplier=resolve_supplier(db,first["supplier"],supplier_cache,stats)
            key=invoice_group_key(first,supplier)
            invoice_total=Decimal(first["invoice_total"] or ZERO)

            warehouse=None
            if a.warehouse_code:
                warehouse=db.query(Warehouse).filter(
                    Warehouse.code==a.warehouse_code,
                    Warehouse.location_id==loc.id,
                    Warehouse.is_active.is_(True),
                ).first()
            else:
                warehouse=db.query(Warehouse).filter(
                    Warehouse.location_id==loc.id,
                    Warehouse.is_active.is_(True),
                ).order_by(Warehouse.id).first()
            if not warehouse:
                blocked.append((source_row,"WAREHOUSE",first["location"]))
                continue

            # Detect legacy split invoices before touching this group. TOTAL
            # INVOICE now means one SI, so old per-block SIs must not survive.
            canonical_invoice_number=(
                "HIST-INVOICE-SUHARTI"
                if supplier_key(first["supplier"])=="SUHARTI" and source_row==14
                else f"HIST-INVOICE-{source_row}"
            )
            legacy_numbers={f"HIST-INVOICE-{b['row']}" for b in source_blocks}
            legacy_numbers.add(canonical_invoice_number)
            existing_rows=db.query(SupplierInvoice).filter(
                SupplierInvoice.supplier_id==supplier.id,
                SupplierInvoice.supplier_invoice_number.in_(sorted(legacy_numbers)),
            ).all()
            existing_numbers=sorted({row.supplier_invoice_number for row in existing_rows})
            if len(existing_numbers)>1:
                blocked.append((
                    source_row,
                    "LEGACY_SPLIT_INVOICES",
                    f"{first['supplier']}: {', '.join(existing_numbers)}",
                ))
                continue

            group_blocked=False
            invoice_tax=ZERO
            projected_invoice_subtotal=ZERO
            source_invoice_subtotal=ZERO
            excluded_rows=set()
            block_ready=[]
            direct_invoice_lines=[]
            group_receipt_dates=[]

            for block in source_blocks:
                invoice_tax += tax_dec(block.get("tax_raw"))
                block_exclusions=exact_invoice_exclusion_rows(block)
                excluded_rows.update(block_exclusions)
                ready=[]

                for x in block["items"]:
                    # Missing quantity or price means the item was not received.
                    if x["qty"] is None or x["price"] is None or x["qty"]<=0 or x["price"]<=0:
                        stats["not_received"]+=1
                        deferred.append((x["row"],"NOT_RECEIVED",x["name"]))
                        continue

                    if x["row"] not in excluded_rows:
                        source_invoice_subtotal += item_value(x)
                    else:
                        stats["received_not_invoiced"]+=1

                    if is_direct_invoice_item(x):
                        stats["direct_invoice"]+=1
                        account=direct_invoice_account(db,x)
                        if not account:
                            blocked.append((x["row"],"DIRECT_INVOICE_ACCOUNT_REQUIRED",x["name"]))
                            group_blocked=True
                            continue
                        direct_invoice_lines.append((x,account))
                        if x["row"] not in excluded_rows:
                            projected_invoice_subtotal += item_value(x)
                        continue

                    period_date=first.get("period_date")
                    fallback_date=(
                        block.get("invoice_date")
                        or first.get("invoice_date")
                        or block.get("period_date")
                        or period_date
                    )
                    if not x["date"]:
                        if not fallback_date:
                            blocked.append((x["row"],"DATE",x["name"]))
                            group_blocked=True
                            continue
                        x["date"]=fallback_date
                        stats["date_fallbacks"]+=1
                    elif period_date and abs((x["date"]-period_date).days)>120:
                        if not fallback_date:
                            blocked.append((x["row"],"DATE_OUTLIER",f"{x['name']} / {x['date']}"))
                            group_blocked=True
                            continue
                        x["date"]=fallback_date
                        stats["date_fallbacks"]+=1

                    p=resolve_product(
                        db,x["name"],x["description"],x["uom"],
                        occupied,product_cache,stats,
                        historical_stock=True,
                    )
                    treatment=getattr(p,"inventory_treatment","REVIEW_REQUIRED") or "REVIEW_REQUIRED"
                    if treatment!="STOCK":
                        blocked.append((
                            x["row"],
                            "TREATMENT_REVIEW",
                            f"{p.code} {p.name} / {treatment}",
                        ))
                        group_blocked=True
                        continue
                    if not p.inventory_account_id:
                        blocked.append((x["row"],"INVENTORY_ACCOUNT",f"{p.code} {p.name}"))
                        group_blocked=True
                        continue

                    ready.append((x,p))
                    if x["row"] not in excluded_rows:
                        projected_invoice_subtotal += item_value(x)

                if ready:
                    block_ready.append((block,ready))
                    group_receipt_dates.extend(x["date"] for x,_ in ready)

            projected_total=source_invoice_subtotal+invoice_tax
            variance=invoice_total-projected_total
            if variance < ZERO:
                blocked.append((
                    source_row,
                    "INVOICE_BELOW_RECEIVING",
                    f"invoice={invoice_total} projected={projected_total} difference={variance}",
                ))
                group_blocked=True
            elif variance > ZERO:
                variance_ratio=(variance/invoice_total) if invoice_total > ZERO else Decimal("1")
                if variance > Decimal("100000") or variance_ratio > Decimal("0.01"):
                    blocked.append((
                        source_row,
                        "INVOICE_VARIANCE_REVIEW",
                        f"invoice={invoice_total} projected={projected_total} "
                        f"difference={variance} ratio={variance_ratio:.4%}",
                    ))
                    group_blocked=True

            preview_rows.append({
                "row":source_row,
                "supplier":supplier.name,
                "location":loc.name,
                "invoice_total":invoice_total,
                "receiving_subtotal":source_invoice_subtotal,
                "tax":invoice_tax,
                "variance":variance,
                "excluded_rows":sorted(excluded_rows),
                "status":"BLOCKED" if group_blocked else "READY",
            })

            if dry or group_blocked:
                if group_blocked:
                    stats["blocked_groups"]+=1
                else:
                    stats["ready_groups"]+=1
                continue

            invoice_lines=[
                SupplierInvoiceLineInput(
                    product_id=None,
                    goods_receipt_item_id=None,
                    description=x["description"] or x["name"],
                    quantity=x["qty"],
                    uom=x["uom"] or "LOT",
                    unit_price=x["price"],
                    is_taxable=False,
                    tax_rate=ZERO,
                    tax_amount=ZERO,
                    account_id=account.id,
                    department_id=dept.id,
                    notes=f"Historical direct invoice source row {x['row']}",
                )
                for x,account in direct_invoice_lines
                if x["row"] not in excluded_rows
            ]
            receipt_dates=[]
            for block,ready in block_ready:
                # Historical receipts are date-based.  Consolidate all
                # workbook rows for the same product/date/cost into one GR line.
                # Do not let cosmetic UOM spelling/case split a receipt that was
                # already posted historically (e.g. Suharti 30 + 20 portions on
                # 2025-12-01 = the preserved 50-portion GR line).
                consolidated={}
                for x,p in ready:
                    item_key=(p.id,x["date"],x["price"])
                    if item_key not in consolidated:
                        consolidated[item_key]=(dict(x),p)
                    else:
                        gx,_=consolidated[item_key]
                        gx["qty"] += x["qty"]
                        gx["description"] = gx["description"] or x["description"]
                ready=list(consolidated.values())

                # Build one receipt group per receiving date where possible.
                # If a product occurs more than once on the same date at
                # different costs, split only that cost occurrence because a
                # direct GR can contain a product only once.
                receipt_groups=[]
                by_date={}
                for x,p in sorted(ready,key=lambda xp:(xp[0]["date"],xp[0]["row"])):
                    by_date.setdefault(x["date"],[]).append((x,p))
                for receiving_date,date_lines in sorted(by_date.items()):
                    current=[]
                    seen=set()
                    for x,p in date_lines:
                        if p.id in seen:
                            receipt_groups.append(current)
                            current=[]
                            seen=set()
                        current.append((x,p))
                        seen.add(p.id)
                    if current:
                        receipt_groups.append(current)

                for group_no,ready_group in enumerate(receipt_groups,1):
                    receipt_date=min(x["date"] for x,_ in ready_group)
                    ext=f"HIST-RECEIVING-{block['row']}-{supplier.id}-{loc.id}-{group_no}"
                    gr=db.query(GoodsReceipt).filter(GoodsReceipt.external_reference==ext).first()
                    if not gr:
                        gr=GoodsReceiptService.create(
                            db,
                            data=GoodsReceiptCreate(
                                supplier_id=supplier.id,
                                business_unit_id=bu.id,
                                location_id=loc.id,
                                department_id=dept.id,
                                received_at=datetime.combine(
                                    receipt_date,datetime.min.time(),tzinfo=timezone.utc,
                                ),
                                source_type="HISTORICAL_IMPORT",
                                external_reference=ext,
                                destination_type="WAREHOUSE",
                                warehouse_id=warehouse.id,
                                notes=f"Historical receiving import invoice row {source_row}; source block {block['row']}",
                                items=[
                                    GoodsReceiptItemCreate(
                                        product_id=p.id,
                                        quantity=x["qty"],
                                        unit_cost=x["price"],
                                        is_taxable=False,
                                        tax_rate=ZERO,
                                    )
                                    for x,p in ready_group
                                ],
                            ),
                            user=user,
                        )
                        gr=GoodsReceiptService.post(db,receipt_id=gr.id,user=user)
                        if journals is not None:
                            journal=db.query(JournalEntry).filter(
                                JournalEntry.reference_type=="GOODS_RECEIPT",
                                JournalEntry.reference_id==gr.id,
                            ).first()
                            if journal and journal.status=="DRAFT":
                                journals.post(journal.id,db,user)
                    else:
                        stats["existing_receipts"]+=1

                    receipt_dates.append(receipt_date)
                    gr_items_by_product={item.product_id:item for item in gr.items}
                    shortages=[]

                    for x,p in ready_group:
                        gri=gr_items_by_product.get(p.id)
                        if not gri:
                            raise RuntimeError(
                                f"Existing receipt {gr.external_reference} does not contain "
                                f"current workbook product {p.code} {p.name} (source row {x['row']}). "
                                "Historical receipt must be reconciled before invoice seeding."
                            )

                        existing_qty=Decimal(gri.quantity or 0)
                        source_qty=Decimal(x["qty"])
                        existing_cost=Decimal(gri.unit_cost or 0)
                        source_cost=Decimal(x["price"])

                        if existing_cost != source_cost:
                            raise RuntimeError(
                                f"Existing receipt {gr.external_reference} differs from current workbook "
                                f"for {p.code} {p.name}: existing cost={existing_cost}, source cost={source_cost}."
                            )
                        if existing_qty > source_qty:
                            raise RuntimeError(
                                f"Existing receipt {gr.external_reference} exceeds current workbook "
                                f"for {p.code} {p.name}: existing qty={existing_qty}, source qty={source_qty}."
                            )

                        # Keep the already-posted historical receiving and create
                        # only the proven missing quantity as a separate
                        # historical adjustment receipt.  Example: Suharti
                        # 2025-12-01 source=80 while preserved GR=50, so only
                        # the missing 30 is added.
                        if existing_qty < source_qty:
                            shortages.append((x,p,source_qty-existing_qty))

                        # The source can prove a received item is outside the
                        # supplier invoice (known example: Sukanda source row 94).
                        if x["row"] in excluded_rows:
                            stats["received_not_invoiced"]+=1
                            continue

                        invoice_lines.append(SupplierInvoiceLineInput(
                            product_id=p.id,
                            goods_receipt_item_id=gri.id,
                            description=x["description"] or x["name"],
                            quantity=existing_qty,
                            uom=p.uom or "PCS",
                            unit_price=x["price"],
                            is_taxable=False,
                            tax_rate=ZERO,
                            tax_amount=ZERO,
                            account_id=None,
                            department_id=dept.id,
                        ))

                    if shortages:
                        adj_ext=f"{ext}-ADJ"
                        adj=db.query(GoodsReceipt).filter(
                            GoodsReceipt.external_reference==adj_ext
                        ).first()
                        if not adj:
                            adj=GoodsReceiptService.create(
                                db,
                                data=GoodsReceiptCreate(
                                    supplier_id=supplier.id,
                                    business_unit_id=bu.id,
                                    location_id=loc.id,
                                    department_id=dept.id,
                                    received_at=datetime.combine(
                                        receipt_date,datetime.min.time(),tzinfo=timezone.utc,
                                    ),
                                    source_type="HISTORICAL_IMPORT",
                                    external_reference=adj_ext,
                                    destination_type="WAREHOUSE",
                                    warehouse_id=warehouse.id,
                                    notes=(
                                        f"Historical receiving reconciliation for {ext}; "
                                        "source workbook proves quantity omitted from preserved receipt"
                                    ),
                                    items=[
                                        GoodsReceiptItemCreate(
                                            product_id=p.id,
                                            quantity=missing_qty,
                                            unit_cost=x["price"],
                                            is_taxable=False,
                                            tax_rate=ZERO,
                                        )
                                        for x,p,missing_qty in shortages
                                    ],
                                ),
                                user=user,
                            )
                            adj=GoodsReceiptService.post(db,receipt_id=adj.id,user=user)
                            if journals is not None:
                                journal=db.query(JournalEntry).filter(
                                    JournalEntry.reference_type=="GOODS_RECEIPT",
                                    JournalEntry.reference_id==adj.id,
                                ).first()
                                if journal and journal.status=="DRAFT":
                                    journals.post(journal.id,db,user)
                            stats["receiving_adjustments"]+=1
                        else:
                            stats["existing_receipts"]+=1

                        adj_items={item.product_id:item for item in adj.items}
                        for x,p,missing_qty in shortages:
                            agri=adj_items.get(p.id)
                            if not agri:
                                raise RuntimeError(
                                    f"Historical adjustment receipt {adj_ext} is missing "
                                    f"{p.code} {p.name}."
                                )
                            if (
                                Decimal(agri.quantity or 0) != missing_qty
                                or Decimal(agri.unit_cost or 0) != Decimal(x["price"])
                            ):
                                raise RuntimeError(
                                    f"Historical adjustment receipt {adj_ext} differs from "
                                    f"required reconciliation for {p.code} {p.name}."
                                )
                            if x["row"] in excluded_rows:
                                continue
                            invoice_lines.append(SupplierInvoiceLineInput(
                                product_id=p.id,
                                goods_receipt_item_id=agri.id,
                                description=x["description"] or x["name"],
                                quantity=missing_qty,
                                uom=p.uom or "PCS",
                                unit_price=x["price"],
                                is_taxable=False,
                                tax_rate=ZERO,
                                tax_amount=ZERO,
                                account_id=None,
                                department_id=dept.id,
                            ))

            if existing_rows:
                stats["existing_invoices"]+=1
                continue

            subtotal=sum(
                (Decimal(line.quantity)*Decimal(line.unit_price) for line in invoice_lines),
                ZERO,
            )
            reconciliation=invoice_total-(subtotal+invoice_tax)
            if reconciliation < ZERO:
                raise RuntimeError(
                    f"Invoice row {source_row} total is below linked receiving by {-reconciliation}"
                )
            if reconciliation > ZERO:
                invoice_lines.append(SupplierInvoiceLineInput(
                    product_id=None,
                    goods_receipt_item_id=None,
                    description="Historical source invoice reconciliation",
                    quantity=Decimal("1"),
                    uom="LOT",
                    unit_price=reconciliation,
                    is_taxable=False,
                    tax_rate=ZERO,
                    tax_amount=ZERO,
                    account_id=variance_account.id,
                    department_id=dept.id,
                    notes=f"TOTAL INVOICE {invoice_total}; receiving/tax evidence {subtotal+invoice_tax}",
                ))
                subtotal += reconciliation
                stats["invoice_variances"]+=1

            inv_date=(
                next((b["invoice_date"] for b in source_blocks if b["invoice_date"]),None)
                or (min(receipt_dates) if receipt_dates else first.get("period_date"))
            )
            if not inv_date:
                raise RuntimeError(f"Invoice row {source_row} has no usable date")

            if invoice_tax>ZERO:
                supplier.is_pkp=True

            inv=svc.create(
                SupplierInvoiceInput(
                    supplier_invoice_number=canonical_invoice_number,
                    supplier_id=supplier.id,
                    invoice_date=inv_date,
                    received_date=inv_date,
                    due_date=inv_date+timedelta(days=30),
                    goods_receipt_id=None,
                    business_unit_id=bu.id,
                    department_id=dept.id,
                    location_id=loc.id,
                    currency="IDR",
                    discount_amount=ZERO,
                    tax_amount=invoice_tax,
                    withholding_tax_amount=ZERO,
                    total_amount=invoice_total,
                    notes="Historical receiving import; TOTAL INVOICE row "
                          f"{source_row}; source blocks "
                          + ",".join(str(b["row"]) for b in source_blocks),
                    source_type="HISTORICAL_IMPORT",
                    lines=invoice_lines,
                ),
                user,
            )
            inv=svc.verify(inv,user)
            if journals is not None:
                journal=svc.generate_journal(inv,user)
                if journal.status=="DRAFT":
                    journals.post(journal.id,db,user)
            stats["posted_invoices"]+=1

        if dry:
            db.rollback()
        else:
            db.commit()

        print("MODE:", "DRY RUN" if dry else "APPLIED")
        print(
            "invoice_groups:",len(grouped_blocks),
            "ready_groups:",stats["ready_groups"],
            "blocked_groups:",stats["blocked_groups"],
            "skipped_operational:",stats["skipped_operational"],
            "without_total_invoice:",stats["without_total_invoice"],
        )
        print(
            "products_new:",stats["products"],
            "stock_classified:",stats["stock_classified"],
            "tax_classified:",stats["tax_classified"],
            "inventory_overrides:",stats["inventory_overrides"],
            "date_fallbacks:",stats["date_fallbacks"],
            "receiving_adjustments:",stats["receiving_adjustments"],
            "skipped_empty_location:",stats["skipped_empty_location"],
            "suppliers_new:",stats["suppliers"],
            "not_received:",stats["not_received"],
            "received_not_invoiced:",stats["received_not_invoiced"],
            "before_start_groups:",stats["before_start_groups"],
            "partial_start_groups:",stats["partial_start_groups"],
        )
        print("\n=== INVOICE CONTROL ===")
        for row in preview_rows:
            print(
                f"row {row['row']:>3} | {row['status']:<7} | "
                f"{row['supplier'][:28]:<28} | {row['location'][:12]:<12} | "
                f"invoice={row['invoice_total']} receiving={row['receiving_subtotal']} "
                f"tax={row['tax']} variance={row['variance']} "
                f"excluded={row['excluded_rows']}"
            )

        print("\n=== DEFERRED / SKIPPED ===")
        for row,reason,value in deferred:
            print(f"  row {row}: {reason}: {value}")

        print("\n=== BLOCKED ===",len(blocked))
        for row,reason,value in blocked:
            print(f"  row {row}: {reason}: {value}")
        if blocked:
            print("Blocked groups are not safe to apply yet. Resolve Item Master/account/date conflicts first.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
        wb.close()

if __name__=="__main__":
    main()
