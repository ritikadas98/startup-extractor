export const dynamic = "force-dynamic";

import Link from "next/link";
import { supabase } from "@/lib/supabase";
import { LAYER_TITLES } from "@/lib/layers";

type Hit = {
  layer_number: number;
  company_id: number | null;
  result_json: Record<string, unknown>;
  articles: { title: string; url: string; source: string } | null;
};

function snippet(json: Record<string, unknown>, q: string): string {
  const text = JSON.stringify(json);
  const idx = text.toLowerCase().indexOf(q.toLowerCase().split(" ")[0] ?? "");
  const raw = idx >= 0 ? text.slice(Math.max(0, idx - 80), idx + 200) : text.slice(0, 280);
  return raw.replace(/[{}"\[\]]/g, " ").replace(/\s+/g, " ").trim();
}

export default async function Search({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q } = await searchParams;
  let hits: Hit[] = [];
  let error: string | null = null;

  if (q) {
    const res = await supabase()
      .from("analysis_results")
      .select("layer_number, company_id, result_json, articles(title, url, source)")
      .textSearch("fts", q, { type: "websearch" })
      .limit(25);
    if (res.error) error = res.error.message;
    hits = (res.data ?? []) as unknown as Hit[];
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Search</h1>
        <p className="text-sm text-neutral-500">
          Full-text search across every analysis layer (e.g. “quick commerce”, “pricing moat”, “Peak XV”).
        </p>
      </div>
      <form className="flex gap-2" action="/search">
        <input
          name="q"
          defaultValue={q ?? ""}
          placeholder="Search the knowledge base…"
          className="w-full max-w-md rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm"
        />
        <button className="rounded-md bg-emerald-700 px-3 py-1.5 text-sm text-white">Search</button>
      </form>
      {error && <p className="text-sm text-red-600">Search failed: {error}</p>}
      {q && !error && hits.length === 0 && (
        <p className="text-sm text-neutral-500">No results for “{q}”.</p>
      )}
      <div className="space-y-4">
        {hits.map((h, i) => (
          <div key={i} className="rounded-lg border border-neutral-200 bg-white p-4">
            <div className="text-xs text-neutral-500">
              {LAYER_TITLES[h.layer_number]} · {h.articles?.source}
            </div>
            <div className="mt-0.5 font-medium">
              {h.company_id ? (
                <Link href={`/companies/${h.company_id}`} className="text-emerald-800 hover:underline">
                  {h.articles?.title}
                </Link>
              ) : (
                h.articles?.title
              )}
            </div>
            <p className="mt-2 text-sm text-neutral-600">{snippet(h.result_json, q ?? "")}…</p>
          </div>
        ))}
      </div>
    </div>
  );
}
