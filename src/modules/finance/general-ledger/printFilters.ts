export function ledgerPrintParams(searchParams: URLSearchParams) {
  return Object.fromEntries(
    Object.entries({
      search: searchParams.get("search") || "",
      account_ids: searchParams.get("account_ids") || "",
      account_from_id: searchParams.get("account_from_id") || "",
      account_to_id: searchParams.get("account_to_id") || "",
      search_type: searchParams.get("search_type") || "ALL",
      account_id: searchParams.get("account_id") || "",
      date_from: searchParams.get("date_from") || "",
      date_to: searchParams.get("date_to") || "",
      reference_type: searchParams.get("reference_type") || "",
      supplier_id: searchParams.get("supplier_id") || "",
      department_id: searchParams.get("department_id") || "",
      location_id: searchParams.get("location_id") || "",
      business_unit_id: searchParams.get("business_unit_id") || "",
    }).filter(([, value]) => value !== ""),
  );
}

