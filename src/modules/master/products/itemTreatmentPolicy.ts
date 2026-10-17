export function foodTreatment(subgroup: string, name: string): "STOCK" | "DIRECT_USE" | undefined {
  if (!["VEGETABLES","FRUIT","HERB","FISH","POULTRY","MEAT","SNACK"].includes(subgroup.trim().toUpperCase())) return undefined;
  return /\b(FROZEN|BEKU|TENDERLOIN|SIRLOIN|IMPOR|IMPORTED)\b/i.test(name) ? "STOCK" : "DIRECT_USE";
}
