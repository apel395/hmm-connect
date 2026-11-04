import type { PosPaymentMethod } from './api';
export type DiscountPreset={id:string;name:string;kind:'PERCENT'|'FIXED';value:string|number;enabled:boolean};
export type PaymentSetting={method:PosPaymentMethod;enabled:boolean;account_id:number|null};
export type CheckoutConfiguration={discount_presets:DiscountPreset[];payment_methods:PaymentSetting[]};
export type CheckoutOptions={configuration:CheckoutConfiguration;version:string;configured:boolean;accounts?:{id:number;code:string;name:string}[]};
// Round the decimal text in cents, avoiding binary floating-point half-cent errors.
const cents=(value:number|string):bigint=>{
  let text=String(value);
  if(/[eE]/.test(text))text=Number(value).toFixed(6);
  const [whole,fraction='']=text.split('.');
  return BigInt(whole||'0')*100n+BigInt((fraction+'00').slice(0,2))+(Number(fraction[2]||0)>=5?1n:0n);
};
export const discountFor=(subtotal:number,preset?:DiscountPreset)=>{
  if(!preset)return 0;
  const base=cents(subtotal),value=cents(preset.value);
  const amount=preset.kind==='PERCENT'?(base*value+5000n)/10000n:value;
  return Number(amount>base?base:amount)/100;
};
