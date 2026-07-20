export const dynamic = "force-dynamic";

import Link from "next/link";
import { supabase } from "@/lib/supabase";
import Pager from "@/components/Pager";

const PER_PAGE = 50;

export default async function Archive({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  const { page: pageRaw } = await searchParams;
  const page = Math.max(1, parseInt(pageRaw ?? "1", 10) || 1);
  const from = (page - 1) * PER_PAGE;

  const { data, error } = await supabase()
    .from("articles")
    .select("id, title, url, source, published_at, processing_status")
    .in("processing_status", ["fetched", "pending", "reference"])
    .order("published_at", { ascending: false, nullsFirst: false })
    .range(from, from + PER_PAGE); // one extra row = "has more"

  if (error) {
    return <p className="text-sm text-red-700">Could not load archive: {error.message}</p>;
  }
  const rows = data ?? [];
  const hasMore = rows.length > PER_PAGE;
  const items = rows.slice(0, PER_PAGE);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-neutral-900">Archive</h1>
        <p className="text-sm text-neutral-600">
          Collected articles that haven&apos;t been AI-analyzed — the deferred pre-April
          history plus reading-list sources like TLDR Product. Links go to the originals.
        </p>
      </div>
      <ul className="divide-y divide-neutral-100 rounded-lg border border-neutral-200 bg-white">
        {items.map((a) => (
          <li key={a.id} className="px-4 py-3">
            <Link
              href={a.url}
              rel="noopener"
              target="_blank"
              className="text-sm font-medium text-neutral-900 hover:text-emerald-800 hover:underline"
            >
              {a.title || a.url}
            </Link>
            <div className="mt-0.5 text-xs text-neutral-600">
              {a.source}
              {a.processing_status === "reference" && (
                <span className="ml-2 rounded bg-sky-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-sky-800">
                  reading list
                </span>
              )}
              {a.published_at &&
                " · " +
                  new Date(a.published_at).toLocaleDateString("en-IN", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })}
            </div>
          </li>
        ))}
      </ul>
      <Pager base="/archive" page={page} hasMore={hasMore} />
    </div>
  );
}
