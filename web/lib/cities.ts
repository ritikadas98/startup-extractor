// City alias handling: "Bangalore" and "Bengaluru" are the same place, and a
// company based in "Delhi and Mumbai" should appear under both cities.
// Mirrors jobs/roles_finder.py CITY_SYNONYMS on the pipeline side.

const ALIASES: Record<string, string[]> = {
  Bengaluru: ["bengaluru", "bangalore"],
  Gurugram: ["gurugram", "gurgaon"],
  Delhi: ["delhi", "new delhi", "delhi ncr", "ncr"],
  Mumbai: ["mumbai", "bombay", "navi mumbai"],
  Chennai: ["chennai", "madras"],
  Kolkata: ["kolkata", "calcutta"],
};

/** Split a stored hq_city like "Bengaluru and San Francisco" into parts. */
export function splitCities(raw: string): string[] {
  return raw
    .split(/,|\/|&|\band\b/i)
    .map((s) => s.trim())
    .filter((s) => s.length > 1);
}

/** Map any spelling variant to its canonical display name. */
export function canonicalCity(part: string): string {
  const lower = part.toLowerCase().replace(/\s+/g, " ").trim();
  for (const [canon, aliases] of Object.entries(ALIASES)) {
    if (aliases.some((a) => lower === a || lower.includes(a))) return canon;
  }
  // unknown city: tidy title-case of what was stored
  return part
    .trim()
    .split(" ")
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(" ");
}

/** All stored spellings that should match a canonical city (for the DB query). */
export function cityVariants(canon: string): string[] {
  return ALIASES[canon] ?? [canon.toLowerCase()];
}
