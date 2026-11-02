import { accumulatedAccountCodes } from "./accountRules";
type Category={id:number; fiscal_group_code?:string|null; asset_account_id?:number|null; accumulated_depreciation_account_id?:number|null; depreciation_expense_account_id?:number|null; is_depreciable:boolean; default_useful_life_months?:number|null; disposal_gain_account_id?:number|null; disposal_loss_account_id?:number|null};
type Account={id:number;account_code:string};
export function groupAcceptsAccount(group:string|null|undefined,code:string) {
  if(!group||!code)return true;
  if(group==="LAND")return code==="100-600-100";
  if(group.startsWith("BUILDING_"))return code==="100-600-101";
  return code!=="100-600-100"&&code!=="100-600-101";
}
export function postingDefaults(accountId:number|string,depreciable:boolean,accounts:Account[]) {
  const code=accounts.find(a=>a.id===Number(accountId))?.account_code??"";
  return {asset_account_id:accountId,accumulated_depreciation_account_id:depreciable?(accounts.find(a=>a.account_code===accumulatedAccountCodes[code])?.id??""):"",
    depreciation_expense_account_id:depreciable?(accounts.find(a=>a.account_code==="700-500-133")?.id??""):""};
}
export function categoryDefaults(current:Record<string,any>,category:Category,accounts:Account[]) {
  let id:number|string=category.asset_account_id||current.asset_account_id||"";
  const code=accounts.find(a=>a.id===Number(id))?.account_code??"";
  if(!groupAcceptsAccount(category.fiscal_group_code,code))id="";
  if(!id&&category.fiscal_group_code==="LAND")id=accounts.find(a=>a.account_code==="100-600-100")?.id??"";
  if(!id&&category.fiscal_group_code?.startsWith("BUILDING_"))id=accounts.find(a=>a.account_code==="100-600-101")?.id??"";
  return {...current,...postingDefaults(id,category.is_depreciable,accounts),asset_category_id:category.id,
    depreciation_method:category.is_depreciable?"STRAIGHT_LINE":"NONE",useful_life_months:category.default_useful_life_months??"",
    ...(!category.fiscal_group_code?{accumulated_depreciation_account_id:category.accumulated_depreciation_account_id||"",depreciation_expense_account_id:category.depreciation_expense_account_id||""}:{}),
    disposal_gain_account_id:category.disposal_gain_account_id??null,disposal_loss_account_id:category.disposal_loss_account_id??null};
}
