"""Utensil classification policy, without rewriting existing asset accounting."""
import re
from fastapi import HTTPException

UTENSIL_CLASSES={'UTENSIL','UTENSILS','CUTLERY','CUTLERIES','CHINAWARE','SILVERWARE','GLASSWARE','CHINAWARE GLASSWARE CUTLERIES'}


def is_utensil(item):
    def get(key):return item.get(key,'') if isinstance(item,dict) else getattr(item,key,'')
    classification=re.sub(r'[^A-Z0-9]+',' ',str(get('subgroup_name') or '').upper()).strip()
    name=str(get('name') or '').upper()
    if re.search(r'\bFORK\s*LIFT\b',name):return classification in UTENSIL_CLASSES
    return classification in UTENSIL_CLASSES or bool(re.search(
        r'\b(?:UTENSILS?|CUTLER(?:Y|IES)|SENDOK|GARPU|SUMPIT|PIRING|CANGKIR|SPOONS?|TEASPOONS?|TABLESPOONS?|FORKS?|SAUCERS?|(?:STEAK|TABLE|DINNER) KNIFE|SOUP BOWL)\b',name))


def validate_asset_item(item):
    treatment=item.get('inventory_treatment') if isinstance(item,dict) else item.inventory_treatment
    if treatment=='FIXED_ASSET' and is_utensil(item):
        raise HTTPException(422,'Utensils are consumables, not fixed assets. Use MATERIAL with STOCK or DIRECT_USE and its inventory/expense account.')
