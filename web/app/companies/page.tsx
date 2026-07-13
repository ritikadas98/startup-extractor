export const dynamic = "force-dynamic";

import Link from "next/link";
import { supabase } from "@/lib/supabase";

type Company = {
  id: number;
  name: string;
  hq_city: string | null;
  industry: string | null;
  business_model: string | null;
  funding_rounds: {
    amount_usd: number | null;
    stage: string | null;
    announced_date: string | null;
  }[];
};

function fmtUsd(n: number | null): string {
  if (!n) return "—";
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${Math.round(n / 1_000)}K`;
  return `$${n}`;
}

export default async function Companies({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q } = await searchParams;
  let query = supabase()
    .from("companies")
    .select("id, name, hq_city, industry, business_model, funding_rounds(amount_usd, stage, announced_date)")
    .order("id", { ascending: false })
    .limit(200);
  if (q) query = query.ilike("name", `%${q}%`);
  const { data, error } = await query;

  if (error) {
    return <p className="text-red-600 text-sm">Could not load companies: {error.message}</p>;
  }
  const companies = (data ?? []) as unknown as Company[];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Companies</h1>
        <p className="text-sm text-neutral-500">
          Every company the pipeline has analyzed, most recently added first.
        </p>
      </div>
      <form className="flex gap-2" action="/companies">
        <input
          name="q"
          defaultValue={q ?? ""}
          placeholder="Filter by name…"
          className="w-64 rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm"
        />
        <button className="rounded-md bg-emerald-700 px-3 py-1.5 text-sm text-white">
          Filter
        </button>
      </form>
      <div className="overflow-x-auto rounded-lg border border-neutral-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-neutral-100 text-left text-xs uppercase tracking-wide text-neutral-500">
            <tr>
              <th className="px-4 py-2">Company</th>
              <th className="px-4 py-2">City</th>
              <th className="px-4 py-2">Industry</th>
              <th className="px-4 py-2">Latest round</th>
              <th className="px-4 py-2">Amount</th>
            </tr>
          </thead>
          <tbody>
            {companies.map((c) => {
              const latest = [...(c.funding_rounds ?? [])].sort((a, b) =>
                (b.announced_date ?? "").localeCompare(a.announced_date ?? "")
              )[0];
              return (
                <tr key={c.id} className="border-t border-neutral-100 hover:bg-emerald-50/40">
                  <td className="px-4 py-2 font-medium">
                    <Link href={`/companies/${c.id}`} className="text-emerald-800 hover:underline">
                      {c.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2">{c.hq_city ?? "—"}</td>
                  <td className="px-4 py-2">{c.industry ?? "—"}</td>
                  <td className="px-4 py-2">{latest?.stage ?? "—"}</td>
                  <td className="px-4 py-2 tabular-nums">{fmtUsd(latest?.amount_usd ?? null)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
