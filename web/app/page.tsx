export const dynamic = "force-dynamic";

import Link from "next/link";
import { supabase } from "@/lib/supabase";

type Row = {
  result_json: {
    what_happened?: string;
    one_minute_summary?: string;
    key_takeaways?: string[];
  };
  created_at: string;
  articles: {
    id: number;
    title: string;
    url: string;
    source: string;
    published_at: string | null;
  } | null;
};

export default async function Briefing() {
  const { data, error } = await supabase()
    .from("analysis_results")
    .select(
      "result_json, created_at, articles(id, title, url, source, published_at)"
    )
    .eq("layer_number", 2)
    .order("created_at", { ascending: false })
    .limit(15);

  if (error) {
    return <p className="text-red-600 text-sm">Could not load briefing: {error.message}</p>;
  }
  const rows = (data ?? []) as unknown as Row[];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Briefing</h1>
        <p className="text-sm text-neutral-500">
          Latest analyzed funding stories, newest first.
        </p>
      </div>
      {rows.length === 0 && (
        <p className="text-sm text-neutral-500">No analyses yet — the pipeline runs every morning.</p>
      )}
      {rows.map((r, i) => (
        <article key={i} className="rounded-lg border border-neutral-200 bg-white p-5">
          <h2 className="font-semibold text-lg leading-snug">{r.articles?.title}</h2>
          <p className="mt-1 text-xs text-neutral-500">
            {r.articles?.source}
            {r.articles?.published_at &&
              " · " +
                new Date(r.articles.published_at).toLocaleDateString("en-IN", {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })}
          </p>
          <p className="mt-3 text-sm leading-relaxed">
            {r.result_json.one_minute_summary || r.result_json.what_happened}
          </p>
          {r.result_json.key_takeaways && r.result_json.key_takeaways.length > 0 && (
            <ul className="mt-3 list-disc pl-5 text-sm space-y-1 text-neutral-700">
              {r.result_json.key_takeaways.slice(0, 4).map((t, n) => (
                <li key={n}>{t}</li>
              ))}
            </ul>
          )}
          {r.articles?.url && (
            <Link
              href={r.articles.url}
              rel="noopener"
              target="_blank"
              className="mt-3 inline-block text-xs text-emerald-700 hover:underline"
            >
              original article ↗
            </Link>
          )}
        </article>
      ))}
    </div>
  );
}
