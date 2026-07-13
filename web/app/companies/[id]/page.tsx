export const dynamic = "force-dynamic";

import Link from "next/link";
import { supabase } from "@/lib/supabase";
import JsonBlock from "@/components/JsonBlock";
import { FIELD_ORDER, LAYER_TITLES } from "@/lib/layers";

type Layer = {
  layer_number: number;
  result_json: Record<string, unknown>;
  article_id: number;
  articles: { title: string; url: string; published_at: string | null } | null;
};

export default async function CompanyDetail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const sb = supabase();

  const [{ data: company }, { data: rounds }, { data: layers }] = await Promise.all([
    sb.from("companies").select("*").eq("id", id).single(),
    sb
      .from("funding_rounds")
      .select("amount_raw, amount_usd, stage, announced_date, round_investors(is_lead, investors(name))")
      .eq("company_id", id),
    sb
      .from("analysis_results")
      .select("layer_number, result_json, article_id, articles(title, url, published_at)")
      .eq("company_id", id)
      .order("article_id", { ascending: false })
      .order("layer_number", { ascending: true }),
  ]);

  if (!company) {
    return <p className="text-sm text-neutral-600">Company not found.</p>;
  }

  // group layers by article (a company can have several analyzed articles)
  const byArticle = new Map<number, Layer[]>();
  for (const l of (layers ?? []) as unknown as Layer[]) {
    if (!byArticle.has(l.article_id)) byArticle.set(l.article_id, []);
    byArticle.get(l.article_id)!.push(l);
  }

  return (
    <div className="space-y-8">
      <div>
        <Link href="/companies" className="text-xs text-neutral-600 hover:underline">
          ← all companies
        </Link>
        <h1 className="mt-1 text-2xl font-bold">{company.name}</h1>
        <p className="text-sm text-neutral-600">
          {[company.hq_city, company.industry, company.business_model]
            .filter(Boolean)
            .join(" · ") || "—"}
        </p>
        {company.website && (
          <a
            href={company.website.startsWith("http") ? company.website : `https://${company.website}`}
            rel="noopener"
            target="_blank"
            className="text-xs text-emerald-700 hover:underline"
          >
            {company.website}
          </a>
        )}
      </div>

      <section className="rounded-lg border border-neutral-200 bg-white p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-neutral-600">
          Funding rounds
        </h2>
        {(rounds ?? []).length === 0 && <p className="text-sm text-neutral-600">None recorded.</p>}
        <ul className="space-y-2 text-sm">
          {(rounds ?? []).map((r: any, i: number) => (
            <li key={i}>
              <span className="font-medium">{r.stage ?? "round"}</span>
              {" — "}
              {r.amount_raw || (r.amount_usd ? `$${(r.amount_usd / 1_000_000).toFixed(1)}M` : "undisclosed")}
              {r.announced_date && ` · ${r.announced_date}`}
              {r.round_investors?.length > 0 && (
                <span className="text-neutral-600">
                  {" · "}
                  {r.round_investors
                    .map((ri: any) => ri.investors?.name + (ri.is_lead ? " (lead)" : ""))
                    .filter(Boolean)
                    .join(", ")}
                </span>
              )}
            </li>
          ))}
        </ul>
      </section>

      {[...byArticle.entries()].map(([articleId, ls]) => (
        <section key={articleId} className="space-y-3">
          <div className="border-b-2 border-emerald-700 pb-2">
            <h2 className="font-semibold">{ls[0].articles?.title}</h2>
            {ls[0].articles?.url && (
              <a
                href={ls[0].articles.url}
                rel="noopener"
                target="_blank"
                className="text-xs text-emerald-700 hover:underline"
              >
                original article ↗
              </a>
            )}
          </div>
          {ls.map((l) => (
            <details
              key={l.layer_number}
              open={[2, 3, 6].includes(l.layer_number)}
              className="rounded-lg border border-neutral-200 bg-white"
            >
              <summary className="cursor-pointer select-none px-4 py-2.5 text-sm font-semibold">
                <span className="text-emerald-700">L{l.layer_number}</span>{" "}
                {LAYER_TITLES[l.layer_number]}
              </summary>
              <div className="border-t border-neutral-100 px-4 py-3">
                <JsonBlock data={l.result_json} order={FIELD_ORDER[l.layer_number]} />
              </div>
            </details>
          ))}
        </section>
      ))}
    </div>
  );
}
