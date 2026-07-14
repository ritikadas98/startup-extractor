export const dynamic = "force-dynamic";

import Link from "next/link";
import { supabase } from "@/lib/supabase";
import { splitCities, canonicalCity, cityVariants } from "@/lib/cities";

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

function distinct(values: (string | null)[]): string[] {
  const cleaned = values
    .filter((v): v is string => !!v && v.trim() !== "" && v.toLowerCase() !== "unknown")
    .map((v) => v.trim());
  return [...new Set(cleaned)].sort((a, b) => a.localeCompare(b));
}

export default async function Companies({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; city?: string; industry?: string; stage?: string }>;
}) {
  const { q, city, industry, stage } = await searchParams;
  const sb = supabase();

  // filter option lists (deduplicated in code — small tables)
  const [cities, industries, stages] = await Promise.all([
    sb.from("companies").select("hq_city").limit(2000),
    sb.from("companies").select("industry").limit(2000),
    sb.from("funding_rounds").select("stage").limit(3000),
  ]);
  const cityOpts = [
    ...new Set(
      (cities.data ?? [])
        .flatMap((r) => (r.hq_city ? splitCities(r.hq_city) : []))
        .filter((c) => c.toLowerCase() !== "unknown")
        .map(canonicalCity)
    ),
  ].sort((a, b) => a.localeCompare(b));
  const industryOpts = distinct((industries.data ?? []).map((r) => r.industry));
  const stageOpts = distinct((stages.data ?? []).map((r) => r.stage));

  // stage filter needs an inner join so only companies WITH that round stage match
  const roundsSel = stage
    ? "funding_rounds!inner(amount_usd, stage, announced_date)"
    : "funding_rounds(amount_usd, stage, announced_date)";
  let query = sb
    .from("companies")
    .select(`id, name, hq_city, industry, business_model, ${roundsSel}`)
    .order("id", { ascending: false })
    .limit(200);
  if (q) query = query.ilike("name", `%${q}%`);
  if (city) {
    const ors = cityVariants(city)
      .map((v) => `hq_city.ilike.%${v}%`)
      .join(",");
    query = query.or(ors);
  }
  if (industry) query = query.ilike("industry", `%${industry}%`);
  if (stage) query = query.eq("funding_rounds.stage", stage);
  const { data, error } = await query;

  if (error) {
    return <p className="text-sm text-red-700">Could not load companies: {error.message}</p>;
  }
  const companies = (data ?? []) as unknown as Company[];

  const selectCls =
    "rounded-md border border-neutral-300 bg-white px-2 py-1.5 text-sm text-neutral-800";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-neutral-900">Companies</h1>
        <p className="text-sm text-neutral-600">
          Every company the pipeline has analyzed, most recently added first.
        </p>
      </div>

      <form className="flex flex-wrap items-center gap-2" action="/companies">
        <input
          name="q"
          defaultValue={q ?? ""}
          placeholder="Company name…"
          className="w-44 rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm"
        />
        <select name="city" defaultValue={city ?? ""} className={selectCls}>
          <option value="">All cities</option>
          {cityOpts.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select name="industry" defaultValue={industry ?? ""} className={selectCls}>
          <option value="">All industries</option>
          {industryOpts.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select name="stage" defaultValue={stage ?? ""} className={selectCls}>
          <option value="">All rounds</option>
          {stageOpts.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <button className="rounded-md bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-800">
          Apply
        </button>
        {(q || city || industry || stage) && (
          <Link href="/companies" className="text-sm text-neutral-600 hover:underline">
            clear
          </Link>
        )}
      </form>

      <p className="text-xs text-neutral-500">{companies.length} companies shown</p>

      <div className="overflow-x-auto rounded-lg border border-neutral-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-neutral-100 text-left text-xs uppercase tracking-wide text-neutral-600">
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
                  <td className="px-4 py-2 text-neutral-700">{c.hq_city ?? "—"}</td>
                  <td className="px-4 py-2 text-neutral-700">{c.industry ?? "—"}</td>
                  <td className="px-4 py-2 text-neutral-700">{latest?.stage ?? "—"}</td>
                  <td className="px-4 py-2 tabular-nums text-neutral-700">
                    {fmtUsd(latest?.amount_usd ?? null)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
