"""Approved BUY catalog: four existing families, one requested new SYRUP subgroup."""
from types import SimpleNamespace
from prepare_resiping_item_seed import normalized

BUY_GROUPS={'FOOD','BEVERAGE','MATERIAL','ASSET'}
OBSOLETE={'PREPARED FOOD','PREPARED DRINK','BEVERAGE INGREDIENTS'}


def existing_subgroup(subgroups,group,label):
    labels={label}
    if label=='GROCERIES':labels.add('GRESORIS')
    matches=[s for s in subgroups if s.group_id==group.id and normalized(s.name) in labels and s.is_active]
    if len(matches)!=1:
        raise ValueError(f'Existing subgroup {group.name} / {label} not uniquely configured')
    return matches[0]


def plan_catalog_cleanup(db,groups,subgroups):
    from app.models.product import Product
    families={}
    for name in BUY_GROUPS:
        rows=[g for g in groups if normalized(g.name)==name and g.item_type in ('BUY','ITEM') and g.is_active]
        if len(rows)!=1:raise ValueError(f'Existing BUY family {name} not uniquely configured')
        families[name]=rows[0]
    unexpected=[g.code for g in groups if g.is_active and g.item_type in ('BUY','ITEM') and normalized(g.name) not in BUY_GROUPS and g.code!='BUYPEND']
    if unexpected:raise ValueError(f'Unexpected BUY groups need inspection: {unexpected}')
    oldgroups=[g for g in groups if g.code=='BUYPEND']
    if any(g.item_type!='BUY' for g in oldgroups):raise ValueError('BUYPEND is not a BUY group')
    changes=[];remove=[]
    for subgroup in subgroups:
        group=next((g for g in families.values() if g.id==subgroup.group_id),None)
        label=normalized(subgroup.name)
        if group is None or label not in OBSOLETE:continue
        products=db.query(Product).filter(Product.subgroup_code==subgroup.code).all()
        for p in products:
            if p.item_type!='BUY' or p.group_code!=group.code:
                raise ValueError(f'Obsolete subgroup {subgroup.code} is shared outside its BUY family')
            if label=='PREPARED FOOD':
                name=normalized(p.name)
                # Existing categories: fruit stays fruit; small cakes/snacks use SNACK;
                # complete dishes/ready meals use GROCERIES. Treatment is untouched.
                if name.startswith('IRISAN BUAH'):target='FRUIT'
                elif any(x in name for x in ('ROTI','TOAST','PISANG KIPAS','TEMPE MENDOAN','UBI GORENG','MARTABAK','RISOL','PASTEL','KLEPON','LEMPER','KUE')):target='SNACK'
                else:target='GROCERIES'
                family=families['FOOD']
            elif label=='PREPARED DRINK':target='SOFT DRINK';family=families['BEVERAGE']
            else:target='GROCERIES';family=families['FOOD']
            destination=existing_subgroup(subgroups,family,target)
            before={f:getattr(p,f) for f in ('group_code','group_name','subgroup_code','subgroup_name')}
            after={'group_code':family.code,'group_name':family.name,'subgroup_code':destination.code,'subgroup_name':destination.name}
            changes.append({'id':p.id,'name':p.name,'before':before,'after':after})
        remove.append(subgroup.id)
    return {'reclassifications':changes,'remove_subgroup_ids':remove,'remove_pending_group_ids':[g.id for g in oldgroups]}


def apply_catalog_cleanup(db,plan,user=None):
    from app.models.product import Product
    from app.models.item_group import ItemGroup
    from app.models.item_subgroup import ItemSubgroup
    from app.services.audit import record_audit
    for row in plan['reclassifications']:
        p=db.get(Product,row['id'])
        for k,v in row['after'].items():setattr(p,k,v)
        record_audit(db,user,'BUY_ITEM_SUBGROUP_RESTORED','PRODUCT',f'Restore original subgroup for {p.code}',entity_id=p.id,before_data=row['before'],after_data=row['after'],details={'accounting_changed':False,'tax_changed':False,'treatment_changed':False})
    db.flush()
    for sid in plan['remove_subgroup_ids']:
        s=db.get(ItemSubgroup,sid)
        if db.query(Product).filter(Product.subgroup_code==s.code).first():raise ValueError(f'Subgroup {s.code} still referenced')
        record_audit(db,user,'BUY_SUBGROUP_REMOVED','ITEM_SUBGROUP',f'Remove added subgroup {s.name}',entity_id=s.id,before_data={'code':s.code,'name':s.name,'group_id':s.group_id})
        db.delete(s)
    for gid in plan['remove_pending_group_ids']:
        g=db.get(ItemGroup,gid)
        children=db.query(ItemSubgroup).filter(ItemSubgroup.group_id==gid).all()
        codes=[s.code for s in children]
        if db.query(Product).filter((Product.group_code==g.code)|(Product.subgroup_code.in_(codes))).first():
            raise ValueError('BUYPEND still has items; refusing to remove referenced group')
        record_audit(db,user,'BUY_PENDING_GROUP_REMOVED','ITEM_GROUP','Remove empty BUYPEND group',entity_id=g.id,before_data={'code':g.code,'name':g.name,'subgroups':codes})
        db.delete(g)
    db.flush()
