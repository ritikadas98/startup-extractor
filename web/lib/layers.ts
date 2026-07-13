// Postgres JSONB does not preserve JSON key order (it sorts by key length),
// so every layer's fields must be rendered in this schema-defined order —
// mirrors analysis/schemas.py. Without this, "answer" renders before "question".

export const LAYER_TITLES: Record<number, string> = {
  1: "Extraction",
  2: "Executive summary",
  3: "Business analysis",
  4: "Product analysis",
  5: "Investment analysis",
  6: "PM lessons",
  7: "Interview prep",
  8: "Frameworks",
};

export const FIELD_ORDER: Record<number, string[]> = {
  1: [
    "is_funding_article", "company_name", "funding_date", "amount_raw",
    "amount_usd", "currency", "stage", "investors", "hq_city", "industry",
    "business_model", "website", "careers_url", "linkedin_url", "founders",
    "employee_estimate", "total_funding_to_date_usd", "hiring_signals",
    "confidence_score",
  ],
  2: ["what_happened", "why_it_matters", "key_takeaways", "one_minute_summary"],
  3: [
    "problem_solved", "customers", "pain_points", "alternatives",
    "why_customers_pay", "revenue_model", "competitive_advantage",
    "market_attractiveness",
  ],
  4: [
    "north_star_metric", "product_strategy", "growth_strategy", "monetization",
    "retention_mechanisms", "acquisition_channels", "expansion_opportunities",
    "scaling_risks", "roadmap_priorities", "technical_challenges",
  ],
  5: [
    "why_now", "milestone_that_unlocked_funding", "why_investors_participated",
    "risks_remaining", "next_round_expectations",
  ],
  6: [
    "product_lessons", "growth_lessons", "strategy_lessons", "execution_lessons",
    "pricing_lessons", "key_concepts",
  ],
  7: ["interview_questions", "example_answers"],
  8: ["frameworks"],
};

// nested object field orders (question before answer, metric before reasoning…)
export const NESTED_ORDER: Record<string, string[]> = {
  interview_questions: ["question", "type", "difficulty"],
  example_answers: ["question", "answer"],
  north_star_metric: ["metric", "reasoning"],
  key_concepts: ["term", "definition"],
  frameworks: ["name", "application", "insight"],
  investors: ["name", "is_lead", "type"],
  founders: ["name", "role"],
  hiring_signals: ["is_hiring", "roles_mentioned", "team_expansion_notes"],
};

export function humanize(key: string): string {
  const s = key.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function orderedEntries(
  obj: Record<string, unknown>,
  order?: string[]
): [string, unknown][] {
  if (!order) return Object.entries(obj);
  const seen = new Set(order);
  const head = order.filter((k) => k in obj).map((k) => [k, obj[k]] as [string, unknown]);
  const tail = Object.entries(obj).filter(([k]) => !seen.has(k));
  return [...head, ...tail];
}
