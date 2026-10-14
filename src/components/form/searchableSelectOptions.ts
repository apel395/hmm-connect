export interface SearchableSelectOption<T extends string | number = number> {
  id: T;
  label?: string;
  code?: string;
  name?: string;
  keywords?: string[];
}


export function optionLabel<T extends string | number>(option: SearchableSelectOption<T>): string {
  if (option.label?.trim()) return option.label.trim();
  const code = option.code?.trim() ?? "";
  const name = option.name?.trim() ?? "";
  if (code && name) return `${code} - ${name}`;
  return name || code || String(option.id);
}

function searchableText<T extends string | number>(option: SearchableSelectOption<T>): string {
  return [optionLabel(option), option.code, option.name, ...(option.keywords ?? [])]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

export function matchingSelectOptions<T extends string | number>(options:SearchableSelectOption<T>[],query:string,maxOptions=50):SearchableSelectOption<T>[] {
  const text=query.trim().toLowerCase();
  return (text?options.filter(option=>searchableText(option).includes(text)):options).slice(0,maxOptions);
}

