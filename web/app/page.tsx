export const dynamic = "force-dynamic";

import Link from "next/link";
import { supabase } from "@/lib/supabase";
import Pager from "@/components/Pager";

type Row = {
  result_json: {
    what_happened?: string;
    one_minute_summary?: string;
    key_takeaways?: string[];
  };
  company_id: number | null;
  companies: { hq_city: string | null; industry: string | null } | null;
  created_at: string;
  articles: {
    id: number;
    title: string;
    url: string;
    source: string;
    published_at: string | null;
  } | null;
};

export default async function Briefing({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  const { page: pageRaw } = await searchParams;
  const page = Math.max(1, parseInt(pageRaw ?? "1", 10) || 1);
  const from = (page - 1) * 15;
  const { data, error } = await supabase()
    .from("analysis_results")
    .select(
      "result_json, company_id, created_at, articles(id, title, url, source, published_at), companies(hq_city, industry)"
    )
    .eq("layer_number", 2)
    .order("created_at", { ascending: false })
    .range(from, from + 15); // one extra row = "has more"

  if (error) {
    return <p className="text-red-700 text-sm">Could not load briefing: {error.message}</p>;
  }
  const all = (data ?? []) as unknown as Row[];
  const hasMore = all.length > 15;
  const rows = all.slice(0, 15);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-neutral-900">Briefing</h1>
        <p className="text-sm text-neutral-600">Latest analyzed funding stories, newest first.</p>
      </div>
      {rows.length === 0 && (
        <p className="text-sm text-neutral-600">No analyses yet — the pipeline runs every morning.</p>
      )}
      {rows.map((r, i) => (
        <article key={i} className="rounded-lg border border-neutral-200 bg-white p-5">
          <h2 className="text-lg font-semibold leading-snug text-neutral-900">
            {r.company_id ? (
              <Link href={`/companies/${r.company_id}`} className="hover:text-emerald-800 hover:underline">
                {r.articles?.title}
              </Link>
            ) : (
              r.articles?.title
            )}
          </h2>
          <p className="mt-1 text-xs text-neutral-600">
            {r.articles?.source}
            {r.articles?.published_at &&
              " · " +
                new Date(r.articles.published_at).toLocaleDateString("en-IN", {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })}
            {(r.companies?.hq_city || r.companies?.industry) && (
              <span className="font-semibold text-neutral-800">
                {" · "}
                {[r.companies?.hq_city, r.companies?.industry].filter(Boolean).join(" · ")}
              </span>
            )}
          </p>
          <p className="mt-3 text-sm leading-relaxed text-neutral-800">
            {r.result_json.one_minute_summary || r.result_json.what_happened}
          </p>
          {r.result_json.key_takeaways && r.result_json.key_takeaways.length > 0 && (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-neutral-700">
              {r.result_json.key_takeaways.slice(0, 4).map((t, n) => (
                <li key={n}>{t}</li>
              ))}
            </ul>
          )}
          <div className="mt-4 flex gap-4 text-xs font-medium">
            {r.company_id && (
              <Link
                href={`/companies/${r.company_id}`}
                className="rounded-md bg-emerald-700 px-2.5 py-1 text-white hover:bg-emerald-800"
              >
                Full 8-layer analysis →
              </Link>
            )}
            {r.articles?.url && (
              <Link
                href={r.articles.url}
                rel="noopener"
                target="_blank"
                className="py-1 text-emerald-700 hover:underline"
              >
                original article ↗
              </Link>
            )}
          </div>
        </article>
      ))}
      <Pager base="/" page={page} hasMore={hasMore} />
    </div>
  );
}
