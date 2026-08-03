export function exportCsv(filename:string, headings:string[], rows:Array<Array<string|number|null|undefined>>) {
  const escape = (value:unknown) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const csv = [headings, ...rows].map((row) => row.map(escape).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([csv], {type:"text/csv;charset=utf-8"}));
  const link = document.createElement("a"); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url);
}
