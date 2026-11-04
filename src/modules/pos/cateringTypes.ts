export type BillingDetails = {
  template: "phr" | "standard"; title: string; billing_name: string; billing_address: string;
  attention: string; contract_number: string; contract_date: string | null; company_address: string;
  payment_instructions: string; footer: string; signer_name: string; signer_position: string;
};
export const emptyBilling: BillingDetails = {template:"phr", title:"INVOICE", billing_name:"", billing_address:"", attention:"", contract_number:"", contract_date:null, company_address:"", payment_instructions:"", footer:"", signer_name:"", signer_position:""};
export type CateringSettings = {customer_id?:number|null; department_id?:number|null; revenue_account_id?:number|null; receivable_account_id?:number|null; payment_term_days?:number|null; service_product_ids:number[]; billing:BillingDetails};
export type Choice = {id:number;name:string;code?:string;address?:string};
export type CateringProfile = {configuration:CateringSettings; can_manage:boolean; service_choices:Choice[]};
export type ServiceDetails = {description?:string;registration_number?:string;service_period_from?:string|null;service_period_to?:string|null;uom?:string};
