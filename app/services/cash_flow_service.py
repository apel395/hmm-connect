from collections import defaultdict
from datetime import date
from decimal import Decimal
from math import ceil
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload
from app.models.bank_account import BankAccount
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.payment import Payment
from app.models.bank_transfer import BankTransfer
from app.services.opening_snapshot import opening_snapshot

ZERO=Decimal("0");CASH_TYPES={"CASH","BANK","PETTY_CASH"};CATEGORIES={"OPERATING","INVESTING","FINANCING","UNCLASSIFIED"}

class CashFlowService:
    def __init__(self,db:Session):
        self.db=db
        self._linked_bank_account_ids=None

    def linked_bank_account_ids(self):
        if self._linked_bank_account_ids is None:
            self._linked_bank_account_ids={
                row[0] for row in self.db.query(BankAccount.coa_account_id).filter(
                    BankAccount.is_active.is_(True)
                ).all()
            }
        return self._linked_bank_account_ids

    def is_cash_account(self,account):
        return bool(
            account
            and (
                account.account_subtype in CASH_TYPES
                or account.id in self.linked_bank_account_ids()
            )
        )

    def cash_accounts(self,subtypes=None,active_only=True):
        requested=set(subtypes or CASH_TYPES)
        filters=[ChartOfAccount.account_subtype.in_(requested)]
        if "BANK" in requested:
            filters.append(ChartOfAccount.id.in_(self.linked_bank_account_ids()))
        q=self.db.query(ChartOfAccount).filter(or_(*filters))
        if active_only:q=q.filter(ChartOfAccount.is_active.is_(True),ChartOfAccount.is_posting.is_(True),ChartOfAccount.account_type=="ASSET")
        return q.order_by(ChartOfAccount.account_number).all()
    def journals(self,date_from=None,date_to=None,account_id=None,subtypes=None,location_id=None,department_id=None,business_unit_id=None):
        q=self.db.query(JournalEntry).options(joinedload(JournalEntry.lines).joinedload(JournalLine.account),joinedload(JournalEntry.lines).joinedload(JournalLine.supplier)).filter(JournalEntry.status=="POSTED",JournalEntry.reference_type.notin_(("OPENING_BALANCE","OPENING_BALANCE_ADJUSTMENT")))
        if date_from:q=q.filter(JournalEntry.posting_date>=date_from)
        if date_to:q=q.filter(JournalEntry.posting_date<=date_to)
        if account_id:q=q.filter(JournalEntry.lines.any(JournalLine.account_id==account_id))
        if subtypes:q=q.filter(JournalEntry.lines.any(JournalLine.account.has(ChartOfAccount.account_subtype.in_(subtypes))))
        if location_id:q=q.filter(JournalEntry.lines.any(func.coalesce(JournalLine.location_id,JournalEntry.location_id)==location_id))
        if department_id:q=q.filter(JournalEntry.lines.any(func.coalesce(JournalLine.department_id,JournalEntry.department_id)==department_id))
        if business_unit_id:
            from app.services.organization_access import effective_business_unit
            q=q.filter(JournalEntry.lines.any(effective_business_unit(func.coalesce(JournalLine.business_unit_id,JournalEntry.business_unit_id),func.coalesce(JournalLine.location_id,JournalEntry.location_id))==business_unit_id))
        return q.order_by(JournalEntry.posting_date,JournalEntry.posted_at,JournalEntry.id).all()
    def cash_lines(self,journal):
        lines=[line for line in journal.lines if self.is_cash_account(line.account)]
        return sorted(lines,key=lambda line:(line.line_number is None,line.line_number or 0,line.id or 0))
    def is_transfer(self,journal):
        lines=self.cash_lines(journal);return len({line.account_id for line in lines})>=2 and sum((Decimal(line.debit)-Decimal(line.credit) for line in lines),ZERO)==ZERO
    def category(self,journal,cash_line):
        if self.is_transfer(journal):return "NON_CASH"
        if cash_line.cash_flow_category in CATEGORIES:return cash_line.cash_flow_category
        values=set()
        for line in journal.lines:
            if line.account_id==cash_line.account_id:continue
            category=line.cash_flow_category or line.account.cash_flow_category
            if category in CATEGORIES:values.add(category)
        return next(iter(values)) if len(values)==1 else "UNCLASSIFIED"
    def movements(self,date_from=None,date_to=None,account_id=None,subtypes=None,location_id=None,department_id=None,business_unit_id=None):
        result=[]
        for journal in self.journals(date_from,date_to,account_id,subtypes,location_id,department_id,business_unit_id):
            transfer=self.is_transfer(journal)
            for line in self.cash_lines(journal):
                from app.models.location import Location
                loc_id=line.location_id or journal.location_id
                loc=self.db.get(Location,loc_id) if loc_id else None
                uid=line.business_unit_id or journal.business_unit_id or (loc.business_unit_id if loc else None)
                if location_id is not None and loc_id!=location_id:continue
                if business_unit_id is not None and uid!=business_unit_id:continue
                if department_id is not None and (line.department_id or journal.department_id)!=department_id:continue
                if account_id and line.account_id!=account_id:continue
                if subtypes and line.account.account_subtype not in subtypes:continue
                debit=Decimal(line.debit);credit=Decimal(line.credit);delta=debit-credit
                if delta==ZERO:continue
                direction="TRANSFER" if transfer else "INFLOW" if delta>0 else "OUTFLOW"
                supplier=next((x.supplier for x in journal.lines if x.supplier),None)
                result.append({"journal":journal,"line":line,"account":line.account,"date":journal.posting_date,"direction":direction,"category":self.category(journal,line),"debit":debit,"credit":credit,"inflow":delta if delta>0 else ZERO,"outflow":-delta if delta<0 else ZERO,"delta":delta,"counterparty":supplier.name if supplier else None})
        return result
    def opening(self,date_from,account_id=None,subtypes=None,location_id=None,department_id=None,business_unit_id=None):
        if not date_from:return ZERO
        snapshot_date,snapshot=opening_snapshot(self.db,as_of=date_from,location_id=location_id,department_id=department_id,business_unit_id=business_unit_id)
        cash_accounts={account.id for account in self.cash_accounts(subtypes=subtypes)}
        if account_id is not None:cash_accounts &= {account_id}
        starting=sum((debit-credit for aid,(debit,credit) in snapshot.items() if aid in cash_accounts),ZERO)
        prior=sum((m["delta"] for m in self.movements(date_from=snapshot_date,date_to=date_from,account_id=account_id,subtypes=subtypes,location_id=location_id,department_id=department_id,business_unit_id=business_unit_id) if m["date"]<date_from),ZERO)
        return starting+prior
    def summary(self,date_from=None,date_to=None,account_id=None,subtypes=None,location_id=None,department_id=None,business_unit_id=None):
        opening=self.opening(date_from,account_id,subtypes,location_id,department_id,business_unit_id);items=self.movements(date_from,date_to,account_id,subtypes,location_id,department_id,business_unit_id);totals={category:{"inflow":ZERO,"outflow":ZERO} for category in CATEGORIES};inflow=outflow=transfers=ZERO
        seen_transfers=set()
        for m in items:
            if m["direction"]=="TRANSFER":
                if m["journal"].id not in seen_transfers:transfers+=m["inflow"] or m["outflow"];seen_transfers.add(m["journal"].id)
                continue
            inflow+=m["inflow"];outflow+=m["outflow"];totals[m["category"]]["inflow"]+=m["inflow"];totals[m["category"]]["outflow"]+=m["outflow"]
        net=inflow-outflow
        accounts=[self.db.get(ChartOfAccount,account_id)] if account_id else self.cash_accounts(subtypes=subtypes)
        accounts=[account for account in accounts if account]
        data={"opening_cash_balance":opening,"total_cash_inflow":inflow,"total_cash_outflow":outflow,"net_cash_flow":net,"closing_cash_balance":opening+net,"internal_transfer_total":transfers,"cash_account_count":len(accounts)}
        for key,label in (("OPERATING","operating"),("INVESTING","investing"),("FINANCING","financing"),("UNCLASSIFIED","unclassified")):
            data[f"{label}_inflow"]=totals[key]["inflow"];data[f"{label}_outflow"]=totals[key]["outflow"];data[f"{label}_net"]=totals[key]["inflow"]-totals[key]["outflow"]
        data["unclassified_count"]=sum(m["category"]=="UNCLASSIFIED" and m["direction"]!="TRANSFER" for m in items);return data
    def accounts_summary(self,date_from=None,date_to=None,location_id=None,business_unit_id=None,department_id=None):
        result=[]
        for account in self.cash_accounts():
            opening=self.opening(date_from,account.id,location_id=location_id,business_unit_id=business_unit_id,department_id=department_id);items=self.movements(date_from,date_to,account.id,location_id=location_id,business_unit_id=business_unit_id,department_id=department_id);inflow=sum((m["inflow"] for m in items),ZERO);outflow=sum((m["outflow"] for m in items),ZERO)
            result.append({"account_id":account.id,"account_code":account.account_number,"account_name":account.account_name,"account_subtype":account.account_subtype,"opening_balance":opening,"total_inflow":inflow,"total_outflow":outflow,"closing_balance":opening+inflow-outflow,"last_transaction_date":max((m["date"] for m in items),default=None)})
        return result
    def activity(self,account_id,page=1,page_size=20,date_from=None,date_to=None,search=None,direction=None,reference_type=None,category=None,location_id=None,department_id=None,business_unit_id=None):
        account=self.db.get(ChartOfAccount,account_id)
        if not self.is_cash_account(account):raise ValueError("Cash account not found")
        opening=self.opening(date_from,account_id,location_id=location_id,department_id=department_id,business_unit_id=business_unit_id);items=self.movements(date_from,date_to,account_id,location_id=location_id,department_id=department_id,business_unit_id=business_unit_id);balance=opening;rows=[]
        for m in items:
            j=m["journal"];balance+=m["delta"]
            row={"journal_line_id":m["line"].id,"date":m["date"],"journal_id":j.id,"journal_number":j.journal_number,"transaction_type":j.reference_type,"reference_type":j.reference_type,"reference_id":j.reference_id,"reference_number":j.document_number,"description":m["line"].description or j.description,"counterparty":m["counterparty"],"debit":m["debit"],"credit":m["credit"],"cash_inflow":m["inflow"],"cash_outflow":m["outflow"],"running_balance":balance,"direction":m["direction"],"cash_flow_category":m["category"],"source_route":self.source_route(j)}
            if search and search.lower() not in " ".join(str(row.get(k) or "") for k in ("journal_number","reference_number","description","counterparty")).lower():continue
            if direction and row["direction"]!=direction:continue
            if reference_type and row["reference_type"]!=reference_type:continue
            if category and row["cash_flow_category"]!=category:continue
            rows.append(row)
        total=len(rows);return {"account":{"id":account.id,"account_code":account.account_number,"account_name":account.account_name,"account_subtype":account.account_subtype},"opening_balance":opening,"items":rows[(page-1)*page_size:page*page_size],"page":page,"page_size":page_size,"total_items":total,"total_pages":ceil(total/page_size) if total else 0,"has_next":page*page_size<total,"has_previous":page>1}
    @staticmethod
    def source_route(journal):
        routes={"SUPPLIER_PAYMENT":"/payments/","BANK_TRANSFER":"/bank-transfers/","SUPPLIER_INVOICE":"/supplier-invoices/"}
        prefix=routes.get(journal.reference_type);return f"{prefix}{journal.reference_id}" if prefix else f"/journal-entries/{journal.id}"
    def trace(self,line_id):
        line=self.db.get(JournalLine,line_id)
        if not line or line.account.account_subtype not in CASH_TYPES:raise ValueError("Cash movement not found")
        j=line.journal_entry;links=[{"entity_type":"JOURNAL_ENTRY","entity_id":j.id,"document_number":j.journal_number,"route":f"/journal-entries/{j.id}"}]
        if j.reference_type=="BANK_TRANSFER":
            x=self.db.get(BankTransfer,j.reference_id)
            if x:links.append({"entity_type":"BANK_TRANSFER","entity_id":x.id,"document_number":x.transfer_number,"route":f"/bank-transfers/{x.id}"})
        if j.reference_type=="SUPPLIER_PAYMENT":
            x=self.db.get(Payment,j.reference_id)
            if x:
                links.append({"entity_type":"PAYMENT","entity_id":x.id,"document_number":x.payment_number,"route":f"/payments/{x.id}"})
                for allocation in x.allocations:
                    inv=allocation.supplier_invoice;links.append({"entity_type":"SUPPLIER_INVOICE","entity_id":inv.id,"document_number":inv.internal_invoice_number,"route":f"/supplier-invoices/{inv.id}"})
                    if inv.goods_receipt:links.append({"entity_type":"GOODS_RECEIPT","entity_id":inv.goods_receipt.id,"document_number":inv.goods_receipt.receipt_number,"route":f"/receiving/{inv.goods_receipt.id}"})
                    if inv.purchase_order:
                        po=inv.purchase_order;links.append({"entity_type":"PURCHASE_ORDER","entity_id":po.id,"document_number":po.po_number,"route":f"/purchase-orders/{po.id}"})
                        for pr in po.source_purchase_requisitions:links.append({"entity_type":"PURCHASE_REQUISITION","entity_id":pr.id,"document_number":pr.pr_number,"route":f"/purchase-requisitions/{pr.id}"})
        unique=[];seen=set()
        for link in links:
            key=(link["entity_type"],link["entity_id"])
            if key not in seen:seen.add(key);unique.append(link)
        return {"journal_line_id":line.id,"links":unique}
