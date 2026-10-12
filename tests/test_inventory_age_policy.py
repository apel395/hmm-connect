from datetime import date
from decimal import Decimal
from app.services.stock_aging_service import six_month_cutoff,age_remaining_stock

def test_calendar_six_month_boundary_and_remaining_old_stock():
    assert six_month_cutoff(date(2026,8,31))==date(2026,2,28)
    assert age_remaining_stock(Decimal(1),[(date(2026,4,12),Decimal(1))],date(2026,10,12))['movement_class']=='SLOW'
    assert age_remaining_stock(Decimal(1),[(date(2026,4,11),Decimal(1))],date(2026,10,12))['movement_class']=='DEAD'
    data=age_remaining_stock(Decimal(3),[(date(2026,4,11),Decimal(2)),(date(2026,10,11),Decimal(1))],date(2026,10,12))
    assert data['movement_class']=='DEAD'
    assert data['aging_quantities']['DEAD']==2
    assert data['aging_quantities']['FAST']==1
