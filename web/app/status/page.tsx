export const dynamic = "force-dynamic";

import { supabase } from "@/lib/supabase";

const LABELS: Record<string, string> = {
  complete: "Analyzed",
  duplicate: "Duplicates (same story, other outlet)",
  fetched: "Text downloaded, analysis pending/deferred",
  pending: "Awaiting text download",
  processing: "Being analyzed right now",
  failed: "Failed (will retry)",
};

export default async function Status() {
  const sb = supabase();
  const [statuses, spendRows, latest] = await Promise.all([
    sb.from("articles").select("processing_status").limit(10000),
    sb
      .from("analysis_results")
      .select("cost_usd, created_at")
      .gte("created_at", new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString())
      .limit(10000),
    sb
      .from("analysis_results")
      .select("created_at")
      .order("created_at", { ascending: false })
      .limit(1),
  ]);

  const counts = new Map<string, number>();
  for (const r of statuses.data ?? []) {
    counts.set(r.processing_status, (counts.get(r.processing_status) ?? 0) + 1);
  }
  const monthUsd = (spendRows.data ?? []).reduce((s, r) => s + (r.cost_usd ?? 0), 0);
  const lastRun = latest.data?.[0]?.created_at;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-neutral-900">Pipeline status</h1>
        <p className="text-sm text-neutral-600">
          Read-only view. The pipeline is controlled from the command line
          (<code className="rounded bg-neutral-100 px-1">pause</code>,{" "}
          <code className="rounded bg-neutral-100 px-1">resume</code>,{" "}
          <code className="rounded bg-neutral-100 px-1">set-budget</code>) — never from
          this public page.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-neutral-200 bg-white p-5">
          <div className="text-xs font-semibold uppercase tracking-wide text-neutral-600">
            AI spend this month
          </div>
          <div className="mt-1 text-2xl font-bold tabular-nums text-neutral-900">
            ${monthUsd.toFixed(2)}
            <span className="ml-2 text-sm font-normal text-neutral-600">
              (~₹{Math.round(monthUsd * 85).toLocaleString("en-IN")})
            </span>
          </div>
        </div>
        <div className="rounded-lg border border-neutral-200 bg-white p-5">
          <div className="text-xs font-semibold uppercase tracking-wide text-neutral-600">
            Last analysis written
          </div>
          <div className="mt-1 text-lg font-semibold text-neutral-900">
            {lastRun
              ? new Date(lastRun).toLocaleString("en-IN", {
                  day: "numeric",
                  month: "short",
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : "—"}
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-neutral-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-neutral-100 text-left text-xs uppercase tracking-wide text-neutral-600">
            <tr>
              <th className="px-4 py-2">Articles</th>
              <th className="px-4 py-2 text-right">Count</th>
            </tr>
          </thead>
          <tbody>
            {[...counts.entries()]
              .sort((a, b) => b[1] - a[1])
              .map(([k, v]) => (
                <tr key={k} className="border-t border-neutral-100">
                  <td className="px-4 py-2 text-neutral-800">{LABELS[k] ?? k}</td>
                  <td className="px-4 py-2 text-right tabular-nums text-neutral-800">{v}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
