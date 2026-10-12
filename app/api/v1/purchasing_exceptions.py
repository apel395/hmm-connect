from datetime import date
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.services.purchasing_exceptions import unfinished_documents, archive_document
router=APIRouter(prefix='/purchasing-exceptions',tags=['Purchasing'])

class Reason(BaseModel):
    reason:str=Field(min_length=3,max_length=500)

@router.get('')
def listing(date_from:date|None=None,date_to:date|None=None,archived:bool=False,db:Session=Depends(get_db),user=Depends(get_current_user)):
    if date_from and date_to and date_from>date_to:
        raise HTTPException(422,'From date must not exceed To date')
    return {'items':unfinished_documents(db,user,date_from,date_to,archived)}

@router.post('/{kind}/{document_id}/archive')
def archive(kind:str,document_id:int,data:Reason,db:Session=Depends(get_db),user=Depends(get_current_user)):
    return archive_document(db,user,kind,document_id,data.reason)

@router.post('/{kind}/{document_id}/restore')
def restore(kind:str,document_id:int,data:Reason,db:Session=Depends(get_db),user=Depends(get_current_user)):
    return archive_document(db,user,kind,document_id,data.reason,restore=True)
