import csv
import io
import re
from datetime import date
from math import ceil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import extract, func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.import_batch import ImportBatch, ImportRow
from app.schemas.historical_import import ConfirmImport, ImportBatchCreate
from app.services.activity_service import ActivityService
from app.services.document_number import next_document_number
from app.services.historical_import_service import DOC_SLUGS, HistoricalImportService, template_bytes

router = APIRouter(prefix="/historical-import", tags=["Historical Import"])


def access(user):
    if not {role.name for role in user.roles}.intersection({"FINANCE", "ADMIN"}):
        raise HTTPException(403, "Finance access required")


def get_batch(db, batch_id):
    batch = db.get(ImportBatch, batch_id)
    if not batch: raise HTTPException(404, "Import batch not found")
    return batch


def serialize(batch, detail=False):
    data = {"id":batch.id,"batch_number":batch.batch_number,"batch_name":batch.batch_name,"import_type":batch.import_type,"import_mode":batch.import_mode,"source_type":batch.source_type,"period_from":batch.period_from,"period_to":batch.period_to,"file_name":batch.file_name,"original_file_name":batch.original_file_name,"status":batch.status,"total_rows":batch.total_rows,"valid_rows":batch.valid_rows,"warning_rows":batch.warning_rows,"error_rows":batch.error_rows,"imported_rows":batch.imported_rows,"failed_rows":batch.failed_rows,"created_by_id":batch.created_by_id,"created_by_name":batch.created_by.full_name if batch.created_by else None,"created_at":batch.created_at,"validated_at":batch.validated_at,"imported_at":batch.imported_at,"notes":batch.notes}
    if detail:data["detected_documents"]=len({row.document_number for row in batch.rows if row.document_number});data["allowed_actions"]={"can_upload":batch.status in {"DRAFT","UPLOADED","VALIDATED","FAILED"},"can_validate":batch.status in {"UPLOADED","VALIDATED","FAILED"},"can_confirm":batch.status=="VALIDATED" and batch.import_mode!="DRY_RUN","can_cancel":batch.status not in {"IMPORTED","PARTIALLY_IMPORTED","CANCELLED"},"can_download_errors":bool(batch.error_rows or batch.failed_rows)}
    return data


def serialize_row(row):
    return {"id":row.id,"row_number":row.row_number,"sheet_name":row.sheet_name,"document_type":row.document_type,"normalized_data":row.normalized_data_json,"status":row.status,"entity_type":row.entity_type,"entity_id":row.entity_id,"document_number":row.document_number,"warnings":row.warning_messages_json or [],"errors":row.error_messages_json or [],"imported_at":row.imported_at}


@router.get("/templates")
def templates(user=Depends(get_current_user)):
    access(user);return [{"document_type":value,"slug":slug,"download_url":f"/historical-import/templates/{slug}"} for slug,value in DOC_SLUGS.items()]


@router.get("/templates/{document_type}")
def template(document_type:str,user=Depends(get_current_user)):
    access(user);kind=DOC_SLUGS.get(document_type)
    if not kind:raise HTTPException(404,"Unsupported template type")
    return Response(template_bytes(kind),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":f'attachment; filename="hmm-{document_type}-historical-import.xlsx"'})


@router.get("/batches")
def batches(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),document_type:str|None=None,status:str|None=None,period_year:int|None=None,period_month:int|None=None,created_by_id:int|None=None,date_from:date|None=None,date_to:date|None=None,search:str|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);q=db.query(ImportBatch)
    if document_type:q=q.filter(ImportBatch.import_type==document_type)
    if status:q=q.filter(ImportBatch.status==status)
    if period_year:q=q.filter(extract("year",ImportBatch.period_from)==period_year)
    if period_month:q=q.filter(extract("month",ImportBatch.period_from)==period_month)
    if created_by_id:q=q.filter(ImportBatch.created_by_id==created_by_id)
    if date_from:q=q.filter(func.date(ImportBatch.created_at)>=date_from)
    if date_to:q=q.filter(func.date(ImportBatch.created_at)<=date_to)
    if search:q=q.filter(or_(ImportBatch.batch_number.ilike(f"%{search}%"),ImportBatch.batch_name.ilike(f"%{search}%")))
    total=q.count();items=q.order_by(ImportBatch.id.desc()).offset((page-1)*page_size).limit(page_size).all();return {"items":[serialize(x) for x in items],"page":page,"page_size":page_size,"total_items":total,"total_pages":ceil(total/page_size) if total else 0,"has_next":page*page_size<total,"has_previous":page>1}


@router.post("/batches",status_code=201)
def create_batch(data:ImportBatchCreate,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);batch=ImportBatch(batch_number=next_document_number(db,"IMP"),batch_name=data.batch_name,import_type=data.import_type,import_mode=data.import_mode,source="ACCOUNTING_IMPORT",description=data.notes,period_from=data.period_from,period_to=data.period_to,status="DRAFT",notes=data.notes,created_by_id=user.id,imported_by_id=user.id,imported_at=None);db.add(batch);db.flush();ActivityService.log(db=db,user=user,action="IMPORT_BATCH_CREATED",entity_type="IMPORT_BATCH",entity_id=batch.id,summary=f"Created {batch.batch_number}",import_batch_id=batch.id);db.commit();db.refresh(batch);return serialize(batch,True)


@router.get("/batches/{batch_id}")
def detail(batch_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);return serialize(get_batch(db,batch_id),True)


@router.post("/batches/{batch_id}/upload")
def upload(batch_id:int,file:UploadFile=File(),db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);batch=get_batch(db,batch_id)
    if batch.status in {"IMPORTING","IMPORTED","PARTIALLY_IMPORTED","CANCELLED"}:raise HTTPException(409,"Batch no longer accepts uploads")
    original=Path(file.filename or "").name;extension=Path(original).suffix.lower()
    if extension not in {".xlsx",".csv"}:raise HTTPException(415,"Only XLSX and CSV files are supported")
    content=file.file.read((settings.MAX_DOCUMENT_SIZE_MB*1024*1024)+1)
    if not content:raise HTTPException(400,"Uploaded file is empty")
    if len(content)>settings.MAX_DOCUMENT_SIZE_MB*1024*1024:raise HTTPException(413,"Import file is too large")
    directory=Path(settings.DOCUMENT_STORAGE_PATH)/"historical-import";directory.mkdir(parents=True,exist_ok=True);stored=f"{uuid4()}{extension}";path=directory/stored;path.write_bytes(content)
    if batch.stored_file_path:
        old=Path(batch.stored_file_path)
        if old.exists() and old.parent==directory:old.unlink()
    batch.file_name=stored;batch.original_file_name=re.sub(r"[^A-Za-z0-9._ -]","_",original)[:255];batch.stored_file_path=str(path);batch.status="UPLOADED";batch.rows.clear();batch.total_rows=batch.valid_rows=batch.warning_rows=batch.error_rows=batch.imported_rows=batch.failed_rows=0;db.commit();db.refresh(batch);return serialize(batch,True)


@router.post("/batches/{batch_id}/validate")
def validate(batch_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);batch=get_batch(db,batch_id)
    if batch.status not in {"UPLOADED","VALIDATED","FAILED"}:raise HTTPException(409,"Upload a file before validation")
    batch.status="VALIDATING";db.commit()
    try:return serialize(HistoricalImportService(db,user).normalize_validate(batch),True)
    except Exception:
        db.rollback();batch=get_batch(db,batch_id);batch.status="FAILED";db.commit();raise


@router.get("/batches/{batch_id}/preview")
def preview(batch_id:int,status:str|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);batch=get_batch(db,batch_id);rows=batch.rows
    if status:rows=[row for row in rows if row.status==status]
    grouped={}
    for row in rows:grouped.setdefault(row.document_number or "(missing)",[]).append(serialize_row(row))
    return {"batch":serialize(batch,True),"documents":[{"document_number":number,"status":"ERROR" if any(r["status"] in {"ERROR","FAILED"} for r in values) else "WARNING" if any(r["status"]=="WARNING" for r in values) else values[0]["status"],"rows":values} for number,values in grouped.items()]}


@router.post("/batches/{batch_id}/confirm")
def confirm(batch_id:int,data:ConfirmImport,db:Session=Depends(get_db),user=Depends(get_current_user)):access(user);return serialize(HistoricalImportService(db,user).confirm(get_batch(db,batch_id),data.confirm_warnings),True)


@router.post("/batches/{batch_id}/cancel")
def cancel(batch_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);batch=get_batch(db,batch_id)
    if batch.status in {"IMPORTED","PARTIALLY_IMPORTED","CANCELLED"}:raise HTTPException(409,"Batch cannot be cancelled")
    batch.status="CANCELLED";ActivityService.log(db=db,user=user,action="IMPORT_BATCH_CANCELLED",entity_type="IMPORT_BATCH",entity_id=batch.id,summary=f"Cancelled {batch.batch_number}",import_batch_id=batch.id);db.commit();return serialize(batch,True)


@router.get("/batches/{batch_id}/rows")
def rows(batch_id:int,page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=200),status:str|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);get_batch(db,batch_id);q=db.query(ImportRow).filter_by(import_batch_id=batch_id)
    if status:q=q.filter(ImportRow.status==status)
    total=q.count();items=q.order_by(ImportRow.row_number).offset((page-1)*page_size).limit(page_size).all();return {"items":[serialize_row(x) for x in items],"total_items":total,"page":page,"page_size":page_size}


@router.get("/batches/{batch_id}/error-report")
def error_report(batch_id:int,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);batch=get_batch(db,batch_id);output=io.StringIO();writer=csv.writer(output);writer.writerow(["row_number","document_number","status","warnings","errors"])
    for row in batch.rows:
        if row.warning_messages_json or row.error_messages_json:writer.writerow([row.row_number,row.document_number,row.status," | ".join(row.warning_messages_json or [])," | ".join(row.error_messages_json or [])])
    return Response(output.getvalue(),media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="{batch.batch_number}-errors.csv"'})


@router.get("/progress")
def progress(year:int|None=None,db:Session=Depends(get_db),user=Depends(get_current_user)):
    access(user);q=db.query(extract("year",ImportBatch.period_from).label("year"),extract("month",ImportBatch.period_from).label("month"),ImportBatch.import_type,ImportBatch.status,func.count(ImportBatch.id),func.coalesce(func.sum(ImportBatch.imported_rows),0)).group_by("year","month",ImportBatch.import_type,ImportBatch.status)
    if year:q=q.filter(extract("year",ImportBatch.period_from)==year)
    rows=[{"year":int(y) if y else None,"month":int(m) if m else None,"document_type":kind,"status":status,"batch_count":count,"imported_rows":imported} for y,m,kind,status,count,imported in q.all()]
    totals=db.query(func.count(ImportBatch.id),func.count(ImportBatch.id).filter(ImportBatch.status=="VALIDATED"),func.count(ImportBatch.id).filter(ImportBatch.status=="IMPORTED"),func.count(ImportBatch.id).filter(ImportBatch.status=="PARTIALLY_IMPORTED"),func.count(ImportBatch.id).filter(ImportBatch.status=="FAILED"),func.coalesce(func.sum(ImportBatch.success_count),0)).one()
    return {"summary":{"total_batches":totals[0],"validated":totals[1],"imported":totals[2],"partially_imported":totals[3],"failed":totals[4],"total_documents_imported":totals[5]},"items":rows}
