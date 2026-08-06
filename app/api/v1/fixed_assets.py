import csv, io
from datetime import date, datetime, timezone
from decimal import Decimal
from math import ceil
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from openpyxl import Workbook
from openpyxl.styles import Border, Side
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.fixed_asset import FixedAsset, FixedAssetCategory, FixedAssetDepreciationSchedule, FixedAssetDepreciationRun
from app.schemas.fixed_asset import CategoryInput, AssetInput, AssetUpdate, CapitalizeInput, TransferInput, DisposalInput, WriteOffInput, RunInput
from app.services.audit import record_audit
from app.services.document_number import next_document_number
from app.services.fixed_asset_service import FixedAssetService, DepreciationRunService, ZERO

router=APIRouter(prefix="/fixed-assets",tags=["Fixed Assets"]);reports=APIRouter(prefix="/reports",tags=["Fixed Asset Reports"])
def access(user):
    if not {r.name for r in user.roles}.intersection({"FINANCE","ADMIN"}):raise HTTPException(403,"Finance access required")
def audit(db,user,action,entity,number):record_audit(db,user,action,"FIXED_ASSET",f"{action.replace('_',' ').title()} {number}",entity_id=entity.id,reference_document=number)

@router.get("/categories")
def categories(db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);return db.query(FixedAssetCategory).order_by(FixedAssetCategory.code).all()
@router.get("/categories/{id}")
def category(id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);x=db.get(FixedAssetCategory,id);return x or (_ for _ in ()).throw(HTTPException(404,"Category not found"))
@router.post("/categories")
def create_category(data:CategoryInput,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);x=FixedAssetService(db).create_category(data);audit(db,user,"FIXED_ASSET_CATEGORY_CREATED",x,x.code);db.commit();db.refresh(x);return x
@router.patch("/categories/{id}")
def update_category(id:int,data:CategoryInput,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);x=category(id,db,user);FixedAssetService(db).validate_accounts(data);[setattr(x,k,v) for k,v in data.model_dump().items()];audit(db,user,"FIXED_ASSET_CATEGORY_UPDATED",x,x.code);db.commit();return x

@router.get("")
def listing(page:int=1,page_size:int=20,search:str|None=None,asset_category_id:int|None=None,status:str|None=None,business_unit_id:int|None=None,location_id:int|None=None,department_id:int|None=None,supplier_id:int|None=None,acquisition_from:date|None=None,acquisition_to:date|None=None,fully_depreciated:bool|None=None,source_type:str|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);q=db.query(FixedAsset)
    if search:q=q.filter(or_(FixedAsset.asset_number.ilike(f"%{search}%"),FixedAsset.asset_name.ilike(f"%{search}%"),FixedAsset.serial_number.ilike(f"%{search}%")))
    for column,value in ((FixedAsset.asset_category_id,asset_category_id),(FixedAsset.status,status),(FixedAsset.business_unit_id,business_unit_id),(FixedAsset.location_id,location_id),(FixedAsset.department_id,department_id),(FixedAsset.supplier_id,supplier_id),(FixedAsset.source_type,source_type)):
        if value is not None:q=q.filter(column==value)
    if acquisition_from:q=q.filter(FixedAsset.acquisition_date>=acquisition_from)
    if acquisition_to:q=q.filter(FixedAsset.acquisition_date<=acquisition_to)
    if fully_depreciated is True:q=q.filter(FixedAsset.status=="FULLY_DEPRECIATED")
    total=q.count();svc=FixedAssetService(db);return {"items":[svc.serialize(x) for x in q.order_by(FixedAsset.id.desc()).offset((page-1)*page_size).limit(page_size)],"page":page,"page_size":page_size,"total_items":total,"total_pages":ceil(total/page_size) if total else 0}
@router.post("")
def create(data:AssetInput,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);x=FixedAssetService(db).create_asset(data,user);audit(db,user,"FIXED_ASSET_CREATED",x,x.asset_number);db.commit();db.refresh(x);return FixedAssetService(db).serialize(x)
@router.get("/depreciation-runs")
def runs(db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);return db.query(FixedAssetDepreciationRun).order_by(FixedAssetDepreciationRun.id.desc()).all()
@router.post("/depreciation-runs")
def create_run(data:RunInput,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);x=FixedAssetDepreciationRun(run_number=next_document_number(db,"FADR"),created_by_id=user.id,**data.model_dump());db.add(x);db.flush();audit(db,user,"DEPRECIATION_RUN_CREATED",x,x.run_number);db.commit();db.refresh(x);return x
@router.get("/depreciation-runs/{id}")
def run_detail(id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);x=db.get(FixedAssetDepreciationRun,id);return x or (_ for _ in ()).throw(HTTPException(404,"Run not found"))
def run_action(id,action,db,user):
    x=run_detail(id,db,user);svc=DepreciationRunService(db)
    if action=="calculate":svc.calculate(x);event="DEPRECIATION_RUN_CALCULATED"
    elif action=="post":svc.post(x,user);event="DEPRECIATION_RUN_POSTED"
    elif action=="void":
        if x.status not in ("DRAFT","CALCULATED"):raise HTTPException(409,"Posted runs cannot be voided")
        x.status="VOID";event="DEPRECIATION_RUN_VOIDED"
    audit(db,user,event,x,x.run_number);db.commit();return x
@router.post("/depreciation-runs/{id}/calculate")
def calculate_run(id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):return run_action(id,"calculate",db,user)
@router.post("/depreciation-runs/{id}/post")
def post_run(id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):return run_action(id,"post",db,user)
@router.post("/depreciation-runs/{id}/void")
def void_run(id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):return run_action(id,"void",db,user)
@router.get("/depreciation-runs/{id}/print")
def print_run(id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):x=run_detail(id,db,user);return {"run":x,"printed_at":datetime.now(timezone.utc)}
@router.get("/{id}")
def detail(id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);return FixedAssetService(db).serialize(FixedAssetService(db).get(id))
@router.patch("/{id}")
def update(id:int,data:AssetUpdate,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);svc=FixedAssetService(db);x=svc.get(id)
    if x.status!="DRAFT":raise HTTPException(409,"Only draft assets can be edited")
    values=data.model_dump(exclude_unset=True);bu=values.get("business_unit_id",x.business_unit_id);loc=values.get("location_id",x.location_id);dep=values.get("department_id",x.department_id)
    from app.services.organization_dimensions import validate_dimensions;validate_dimensions(db,bu,loc,dep,required=True)
    [setattr(x,k,v) for k,v in values.items()];audit(db,user,"FIXED_ASSET_UPDATED",x,x.asset_number);db.commit();return svc.serialize(x)
@router.get("/{id}/allowed-actions")
def allowed(id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);return FixedAssetService.actions(FixedAssetService(db).get(id))
@router.post("/{id}/capitalize")
def capitalize(id:int,data:CapitalizeInput,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);svc=FixedAssetService(db);x=svc.capitalize(svc.get(id),data,user);audit(db,user,"FIXED_ASSET_CAPITALIZED",x,x.asset_number);db.commit();return svc.serialize(x)
@router.post("/{id}/generate-schedule")
def generate(id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);svc=FixedAssetService(db);x=svc.get(id);rows=svc.generate_schedule(x);audit(db,user,"FIXED_ASSET_SCHEDULE_GENERATED",x,x.asset_number);db.commit();return {"asset_id":id,"periods":len(rows)}
@router.post("/{id}/transfer")
def transfer(id:int,data:TransferInput,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);svc=FixedAssetService(db);x=svc.transfer(svc.get(id),data,user);audit(db,user,"FIXED_ASSET_TRANSFERRED",x,x.asset_number);db.commit();return svc.serialize(x)
@router.post("/{id}/dispose")
def dispose(id:int,data:DisposalInput,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);svc=FixedAssetService(db);r=svc.dispose(svc.get(id),data,user);audit(db,user,"FIXED_ASSET_DISPOSED",r["asset"],r["asset"].asset_number);db.commit();return {"asset":svc.serialize(r["asset"]),"journal_entry_id":r["journal"].id,"gain_loss":r["gain_loss"]}
@router.post("/{id}/write-off")
def write_off(id:int,data:WriteOffInput,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);svc=FixedAssetService(db);r=svc.dispose(svc.get(id),data,user,True);audit(db,user,"FIXED_ASSET_WRITTEN_OFF",r["asset"],r["asset"].asset_number);db.commit();return {"asset":svc.serialize(r["asset"]),"journal_entry_id":r["journal"].id}
@router.get("/{id}/print")
def printable(id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):return {**detail(id,db,user),"printed_at":datetime.now(timezone.utc)}

def asset_report(db,as_of_date=None,business_unit_id=None,location_id=None,department_id=None,category_id=None,status=None):
    q=db.query(FixedAsset)
    for col,val in ((FixedAsset.business_unit_id,business_unit_id),(FixedAsset.location_id,location_id),(FixedAsset.department_id,department_id),(FixedAsset.asset_category_id,category_id),(FixedAsset.status,status)):
        if val is not None:q=q.filter(col==val)
    if as_of_date:q=q.filter(FixedAsset.acquisition_date<=as_of_date)
    return [{"id":x.id,"asset_number":x.asset_number,"asset_name":x.asset_name,"category":x.category.name,"acquisition_date":x.acquisition_date,"capitalization_date":x.capitalization_date,"business_unit_id":x.business_unit_id,"location_id":x.location_id,"department_id":x.department_id,"acquisition_cost":x.acquisition_cost,"accumulated_depreciation":x.accumulated_depreciation,"net_book_value":x.net_book_value,"residual_value":x.residual_value,"status":x.status} for x in q.all()]
@reports.get("/fixed-assets")
def fixed_report(as_of_date:date|None=None,business_unit_id:int|None=None,location_id:int|None=None,department_id:int|None=None,category_id:int|None=None,status:str|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);items=asset_report(db,as_of_date,business_unit_id,location_id,department_id,category_id,status);return {"items":items,"totals":{"acquisition_cost":sum((x["acquisition_cost"] for x in items),ZERO),"accumulated_depreciation":sum((x["accumulated_depreciation"] for x in items),ZERO),"net_book_value":sum((x["net_book_value"] for x in items),ZERO)}}
@reports.get("/depreciation")
def depreciation_report(date_from:date|None=None,date_to:date|None=None,business_unit_id:int|None=None,location_id:int|None=None,department_id:int|None=None,category_id:int|None=None,status:str|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);q=db.query(FixedAssetDepreciationSchedule).join(FixedAsset)
    if date_from:q=q.filter(FixedAssetDepreciationSchedule.period_end>=date_from)
    if date_to:q=q.filter(FixedAssetDepreciationSchedule.period_start<=date_to)
    for col,val in ((FixedAsset.business_unit_id,business_unit_id),(FixedAsset.location_id,location_id),(FixedAsset.department_id,department_id),(FixedAsset.asset_category_id,category_id),(FixedAssetDepreciationSchedule.status,status)):
        if val is not None:q=q.filter(col==val)
    items=[{"asset_id":s.fixed_asset_id,"asset_number":s.asset.asset_number,"asset_name":s.asset.asset_name,"period":f"{s.period_year}-{s.period_month:02d}","opening_book_value":s.opening_book_value,"depreciation_amount":s.depreciation_amount,"accumulated_depreciation":s.accumulated_depreciation,"closing_book_value":s.closing_book_value,"journal_entry_id":s.journal_entry_id,"status":s.status} for s in q.all()];return {"items":items,"total_depreciation":sum((x["depreciation_amount"] for x in items),ZERO)}
def export_rows(items,heads,keys,format,name):
    matrix=[[x.get(k) for k in keys] for x in items]
    if format=="csv":out=io.StringIO();w=csv.writer(out);w.writerow(heads);w.writerows(matrix);return Response(out.getvalue(),media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="{name}.csv"'})
    wb=Workbook();ws=wb.active;ws.append(heads);[ws.append(row) for row in matrix];thin=Side(style="thin",color="B7B7B7");[setattr(cell,"border",Border(left=thin,right=thin,top=thin,bottom=thin)) for row in ws.iter_rows() for cell in row];out=io.BytesIO();wb.save(out);return Response(out.getvalue(),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":f'attachment; filename="{name}.xlsx"'})
@reports.get("/fixed-assets/export")
def fixed_export(format:str="xlsx",db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);keys=["asset_number","asset_name","category","acquisition_date","capitalization_date","acquisition_cost","accumulated_depreciation","net_book_value","residual_value","status"];return export_rows(asset_report(db),[x.replace("_"," ").title() for x in keys],keys,format,"fixed-assets")
@reports.get("/depreciation/export")
def depreciation_export(format:str="xlsx",db:Session=Depends(get_db),user=Depends(get_current_user)):r=depreciation_report(db=db,user=user);keys=["asset_number","asset_name","period","opening_book_value","depreciation_amount","accumulated_depreciation","closing_book_value","journal_entry_id","status"];return export_rows(r["items"],[x.replace("_"," ").title() for x in keys],keys,format,"depreciation")
