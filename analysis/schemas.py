"""Per-layer JSON response schemas enforced via Gemini structured output."""

def _s(desc: str = "") -> dict:
    return {"type": "string"}

def _arr_s() -> dict:
    return {"type": "array", "items": {"type": "string"}}

def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or list(props)}


LAYER_SCHEMAS: dict[int, dict] = {
    1: _obj({
        "is_funding_article": {"type": "boolean"},
        "company_name": _s(),
        "funding_date": _s(),
        "amount_raw": _s(),
        "amount_usd": {"type": "number", "nullable": True},
        "currency": _s(),
        "stage": _s(),
        "investors": {"type": "array", "items": _obj({
            "name": _s(), "is_lead": {"type": "boolean"}, "type": _s(),
        })},
        "hq_city": _s(),
        "industry": _s(),
        "business_model": _s(),
        "website": {"type": "string", "nullable": True},
        "careers_url": {"type": "string", "nullable": True},
        "linkedin_url": {"type": "string", "nullable": True},
        "founders": {"type": "array", "items": _obj({"name": _s(), "role": _s()})},
        "employee_estimate": _s(),
        "total_funding_to_date_usd": {"type": "number", "nullable": True},
        "hiring_signals": _obj({
            "is_hiring": {"type": "boolean"},
            "roles_mentioned": _arr_s(),
            "team_expansion_notes": _s(),
        }),
        "confidence_score": {"type": "number"},
    }, required=["is_funding_article", "company_name", "confidence_score"]),

    2: _obj({
        "what_happened": _s(),
        "why_it_matters": _s(),
        "key_takeaways": _arr_s(),
        "one_minute_summary": _s(),
    }),

    3: _obj({
        "problem_solved": _s(),
        "customers": _s(),
        "pain_points": _arr_s(),
        "alternatives": _arr_s(),
        "why_customers_pay": _s(),
        "revenue_model": _s(),
        "competitive_advantage": _s(),
        "market_attractiveness": _s(),
    }),

    4: _obj({
        "north_star_metric": _obj({"metric": _s(), "reasoning": _s()}),
        "product_strategy": _s(),
        "growth_strategy": _s(),
        "monetization": _s(),
        "retention_mechanisms": _arr_s(),
        "acquisition_channels": _arr_s(),
        "expansion_opportunities": _arr_s(),
        "scaling_risks": _arr_s(),
        "roadmap_priorities": _arr_s(),
        "technical_challenges": _arr_s(),
    }),

    5: _obj({
        "why_now": _s(),
        "milestone_that_unlocked_funding": _s(),
        "why_investors_participated": _s(),
        "risks_remaining": _arr_s(),
        "next_round_expectations": _s(),
    }),

    6: _obj({
        "product_lessons": _arr_s(),
        "growth_lessons": _arr_s(),
        "strategy_lessons": _arr_s(),
        "execution_lessons": _arr_s(),
        "pricing_lessons": _arr_s(),
        "key_concepts": {"type": "array", "items": _obj({"term": _s(), "definition": _s()})},
    }),

    7: _obj({
        "interview_questions": {"type": "array", "items": _obj({
            "question": _s(), "type": _s(), "difficulty": _s(),
        })},
        "example_answers": {"type": "array", "items": _obj({
            "question": _s(), "answer": _s(),
        })},
    }),

    8: _obj({
        "frameworks": {"type": "array", "items": _obj({
            "name": _s(), "application": _s(), "insight": _s(),
        })},
    }),
}
