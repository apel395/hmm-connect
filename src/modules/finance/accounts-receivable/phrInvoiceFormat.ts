const units = [
  "Nol",
  "Satu",
  "Dua",
  "Tiga",
  "Empat",
  "Lima",
  "Enam",
  "Tujuh",
  "Delapan",
  "Sembilan",
  "Sepuluh",
  "Sebelas",
];
function spell(n: bigint): string {
  if (n < 12n) return units[Number(n)];
  if (n < 20n) return `${spell(n - 10n)} Belas`;
  if (n < 100n)
    return `${spell(n / 10n)} Puluh${n % 10n ? ` ${spell(n % 10n)}` : ""}`;
  if (n < 200n) return `Seratus${n > 100n ? ` ${spell(n - 100n)}` : ""}`;
  if (n < 1000n)
    return `${spell(n / 100n)} Ratus${n % 100n ? ` ${spell(n % 100n)}` : ""}`;
  if (n < 2000n) return `Seribu${n > 1000n ? ` ${spell(n - 1000n)}` : ""}`;
  for (const [scale, label] of [
    [1000000000000n, "Triliun"],
    [1000000000n, "Miliar"],
    [1000000n, "Juta"],
    [1000n, "Ribu"],
  ] as const) {
    if (n >= scale)
      return `${spell(n / scale)} ${label}${n % scale ? ` ${spell(n % scale)}` : ""}`;
  }
  return "";
}
export function rupiahWords(value: string): string {
  if (!/^\d+(\.\d{1,2})?$/.test(value)) return "";
  const [whole, fraction = ""] = value.split(".");
  const cents = BigInt(fraction.padEnd(2, "0"));
  return `${spell(BigInt(whole))} Rupiah${cents ? ` ${spell(cents)} Sen` : ""}`;
}
