export type ReceivingDestination = "WAREHOUSE" | "DIRECT_USE";
export interface LineRouting {
  inventory_treatment?: string;
  destination_type?: ReceivingDestination | null;
  destination_override_reason?: string | null;
  original_destination?: ReceivingDestination;
}
export function masterDestination(treatment?: string): ReceivingDestination | undefined {
  if (treatment === "STOCK") return "WAREHOUSE";
  if (["DIRECT_USE", "NON_STOCK", "FIXED_ASSET"].includes(treatment ?? "")) return "DIRECT_USE";
  return undefined;
}
export function destinationFor(line: LineRouting): ReceivingDestination | undefined {
  return line.destination_type ?? masterDestination(line.inventory_treatment);
}
export function destinationLabel(destination?: string, treatment?: string): string {
  if (treatment === "FIXED_ASSET" && destination === "DIRECT_USE") return "Fixed Asset";
  return destination === "WAREHOUSE" || destination === "INVENTORY" ? "Warehouse" : destination === "DIRECT_USE" ? "Direct Use" : destination === "MIXED" ? "Mixed" : "Item Master review";
}
export function destinationError(line: LineRouting): string | undefined {
  const current = destinationFor(line), original = line.original_destination;
  if (!current) return "Complete the item's inventory treatment in Item Master.";
  if (current !== masterDestination(line.inventory_treatment) && current !== original && (line.destination_override_reason ?? "").trim().length < 3) return "Enter a reason for the item destination exception.";
}
