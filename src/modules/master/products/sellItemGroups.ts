const legacyCodes: Record<string, string> = {
  "S-FOOD": "5",
  "S-BEV": "6",
  "S-SERVICE": "7",
  "S-ROOM": "8",
};

export function sellItemGroupCode(code: string) {
  return legacyCodes[code.toUpperCase()] ?? code;
}
