// The AI extracts industry as free text ("Beauty & Personal Care Contract
// Manufacturing"), so the raw column has hundreds of unique strings. The
// filter groups them into a fixed set of sectors; each sector matches any
// stored industry containing one of its keywords (first match wins).
// NOTE: keywords must not contain commas (they go into a PostgREST or()).

export const SECTORS: Record<string, string[]> = {
  "AI & ML": ["artificial intelligence", " ai", "ai ", "machine learning", "genai", "llm"],
  Fintech: ["fintech", "financ", "payment", "lending", "insur", "wealth", "banking", "credit", "invest"],
  Healthcare: ["health", "medical", "pharma", "biotech", "wellness", "diagnost", "hospital"],
  "E-commerce & D2C": ["commerce", "d2c", "retail", "marketplace", "fashion", "beauty", "jewel", "apparel", "consumer"],
  Edtech: ["edtech", "education", "learning", "upskill", "tutor"],
  "Food & Agri": ["food", "agri", "beverage", "restaurant", "dairy", "nutrition", "grocery"],
  "Logistics & Supply Chain": ["logistic", "supply chain", "warehous", "freight", "delivery"],
  "Mobility & EV": ["mobility", "electric vehicle", " ev", "ev ", "automotive", "transport", "ride"],
  "Space & Deeptech": ["space", "deeptech", "deep tech", "semiconductor", "robot", "drone", "defence", "defense", "aerospace"],
  "Energy & Climate": ["energy", "solar", "climate", "clean", "sustainab", "battery", "renewable"],
  "Real Estate & Proptech": ["proptech", "real estate", "housing", "construction"],
  "Media & Gaming": ["gaming", "game", "media", "entertainment", "content", "creator", "sports", "music"],
  "Travel & Hospitality": ["travel", "hospitality", "hotel", "tourism", "coworking", "co-working"],
  "HR & Work": ["hr tech", "hrtech", "recruit", "staffing", "workforce"],
  "Manufacturing & Industrial": ["manufactur", "industrial", "packaging", "textile", "chemical", "hardware"],
  "SaaS & Software": ["saas", "software", "enterprise", "devtool", "cloud", "analytics", "cyber", "data"],
};

export function sectorPatterns(sector: string): string[] | null {
  return SECTORS[sector] ?? null;
}
