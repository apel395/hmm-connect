from fastapi import HTTPException
from sqlalchemy import inspect
from app.models.department_outlet import DepartmentOutlet
from app.models.department import Department
from app.models.business_unit import BusinessUnit
from app.models.location_department import LocationDepartment


def available(db):
    if 'department_outlets_available' not in db.info:
        db.info['department_outlets_available']=inspect(db.connection()).has_table('department_outlets')
    return db.info['department_outlets_available']


def labels(db):
    if not available(db):return {}
    if 'department_outlet_labels' not in db.info:
        names={d.id:d.name for d in db.query(Department).all()}
        db.info['department_outlet_labels']={r.department_id:{'parent_department_id':r.parent_department_id,
            'parent_department_name':names[r.parent_department_id],
            'display_name':names[r.parent_department_id]+' / '+names[r.department_id]} for r in db.query(DepartmentOutlet).all()}
    return db.info['department_outlet_labels']


def payload(db,department):
    return labels(db).get(department.id,{'parent_department_id':None,'parent_department_name':None,'display_name':department.name})


def assign(db,department,parent_id):
    if not available(db):
        if parent_id is None:return
        raise HTTPException(503,'Run the Hotel outlet migration on EC2 first')
    link=db.get(DepartmentOutlet,department.id)
    if parent_id is None:
        if link:db.delete(link)
    else:
        parent=db.get(Department,parent_id)
        unit=db.get(BusinessUnit,department.business_unit_id) if department.business_unit_id else None
        if not parent or not parent.is_active or parent.id==department.id:
            raise HTTPException(422,'Choose another active parent department')
        if not unit or not unit.is_active or 'HOTEL' not in f'{unit.code} {unit.name}'.upper() or parent.business_unit_id!=unit.id:
            raise HTTPException(422,'Outlet and parent must belong to the same Hotel unit')
        if db.get(DepartmentOutlet,parent.id) or db.query(DepartmentOutlet).filter_by(parent_department_id=department.id).first():
            raise HTTPException(422,'Outlets support one parent level; nested outlets are not allowed')
        if link:link.parent_department_id=parent.id
        else:db.add(DepartmentOutlet(department_id=department.id,parent_department_id=parent.id))
        parent_locations={r.location_id for r in db.query(LocationDepartment).filter_by(department_id=parent.id)}
        existing={r.location_id for r in db.query(LocationDepartment).filter_by(department_id=department.id)}
        if existing-parent_locations:
            raise HTTPException(422,'Outlet locations must be assigned to its parent department first')
        for location_id in parent_locations-existing:
            db.add(LocationDepartment(location_id=location_id,department_id=department.id))
    db.info.pop('department_outlet_labels',None)


def validate_parent_change(db,department):
    if not available(db):return
    for child in db.query(Department).join(DepartmentOutlet,DepartmentOutlet.department_id==Department.id).filter(DepartmentOutlet.parent_department_id==department.id):
        if child.business_unit_id!=department.business_unit_id:
            raise HTTPException(422,'Move or unlink child outlets before changing the parent unit')
        if not department.is_active and child.is_active:
            raise HTTPException(409,'Deactivate child outlets before deactivating their parent')
    current=db.get(DepartmentOutlet,department.id)
    if current:assign(db,department,current.parent_department_id)
