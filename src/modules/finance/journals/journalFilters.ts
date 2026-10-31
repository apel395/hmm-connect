export function unbalancedJournalPath(filters: Record<string, unknown>) {
  const query = new URLSearchParams({balance_state:"UNBALANCED",status:"POSTED",business_unit_id:"all",location_id:"all"});
  for (const key of ["date_from","date_to","business_unit_id","location_id","department_id","supplier_id","reference_type"]) {
    const value=filters[key];
    if(value!==undefined&&value!==null&&value!=="")query.set(key,String(value));
  }
  return `/journal?${query}`;
}

export function journalFilterParams(values: Record<string, unknown>) {
  return Object.fromEntries(Object.entries(values).filter(([,value])=>value!==undefined&&value!==null&&value!==""));
}
