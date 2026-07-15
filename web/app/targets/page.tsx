export const dynamic = "force-dynamic";

import Link from "next/link";
import { supabase } from "@/lib/supabase";

const PM_CLASSES = ["pm", "apm", "analyst", "adjacent"];
const NEW_DAYS = 3;

type Role = {
  id: number;
  title: string;
  location: string | null;
  url: string | null;
  role_class: string;
  first_seen: string;
  company_id: number;
};

function fmtUsd(n: number | null): string {
  if (!n) return "";
  return n >= 1_000_000 ? `$${(n / 1_000_000).toFixed(1)}M` : `$${Math.round(n / 1_000)}K`;
}

export default async function Targets() {
  const sb = supabase();

  const [{ data: rolesData }, { data: companiesData }] = await Promise.all([
    sb
      .from("job_roles")
      .select("id, title, location, url, role_class, first_seen, company_id")
      .in("role_class", PM_CLASSES)
      .eq("dismissed", false),
    sb
      .from("companies")
      .select("id, name, hq_city, job_target_score")
      .gt("job_target_score", 0)
      .order("job_target_score", { ascending: false })
      .limit(300),
  ]);

  const roles = (rolesData ?? []) as Role[];
  const companies = companiesData ?? [];
  const byCompany = new Map<number, Role[]>();
  for (const r of roles) {
    if (!byCompany.has(r.company_id)) byCompany.set(r.company_id, []);
    byCompany.get(r.company_id)!.push(r);
  }

  const withRoles = companies.filter((c) => byCompany.has(c.id));
  const idsWithRoles = withRoles.map((c) => c.id);

  // round context + one-line thesis for the companies we'll show
  const [{ data: ovData }, { data: thesisData }] = await Promise.all([
    idsWithRoles.length
      ? sb
          .from("companies_overview")
          .select("id, latest_stage, latest_amount_usd, latest_round_date")
          .in("id", idsWithRoles)
      : Promise.resolve({ data: [] as any[] }),
    idsWithRoles.length
      ? sb
          .from("analysis_results")
          .select("company_id, result_json")
          .in("company_id", idsWithRoles)
          .eq("layer_number", 3)
      : Promise.resolve({ data: [] as any[] }),
  ]);
  const ov = new Map((ovData ?? []).map((o: any) => [o.id, o]));
  const thesis = new Map(
    (thesisData ?? []).map((t: any) => [
      t.company_id,
      String(t.result_json?.problem_solved ?? "").split(". ")[0],
    ])
  );

  const watchlist = companies.filter((c) => !byCompany.has(c.id)).slice(0, 10);
  const newCutoff = Date.now() - NEW_DAYS * 86_400_000;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-neutral-900">Targets</h1>
        <p className="text-sm text-neutral-600">
          Companies ranked by job-fit score, with their live PM-class openings. Dismiss
          roles or rescore from the command line (<code className="rounded bg-neutral-100 px-1">find-roles</code>,{" "}
          <code className="rounded bg-neutral-100 px-1">dismiss-role</code>).
        </p>
      </div>

      {withRoles.length === 0 && (
        <p className="text-sm text-neutral-600">
          No PM-class openings stored yet — run{" "}
          <code className="rounded bg-neutral-100 px-1">find-roles --pm --deep</code> to hunt.
        </p>
      )}

      {withRoles.map((c) => {
        const o = ov.get(c.id);
        const roundBits = o
          ? [
              o.latest_stage && o.latest_stage !== "unknown" ? o.latest_stage : null,
              fmtUsd(o.latest_amount_usd) || null,
              o.latest_round_date
                ? new Date(o.latest_round_date).toLocaleDateString("en-IN", {
                    day: "numeric",
                    month: "short",
                  })
                : null,
            ].filter(Boolean)
          : [];
        return (
          <article key={c.id} className="rounded-lg border border-neutral-200 bg-white p-5">
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="text-lg font-semibold">
                <Link href={`/companies/${c.id}`} className="text-neutral-900 hover:text-emerald-800 hover:underline">
                  {c.name}
                </Link>
              </h2>
              <span className="rounded-full bg-emerald-700 px-2.5 py-0.5 text-xs font-bold text-white">
                {Number(c.job_target_score).toFixed(2)}
              </span>
            </div>
            <p className="mt-0.5 text-xs text-neutral-600">
              {[c.hq_city, roundBits.length ? "raised " + roundBits.join(" · ") : null]
                .filter(Boolean)
                .join(" · ")}
            </p>
            {thesis.get(c.id) && (
              <p className="mt-2 text-sm italic text-neutral-700">{thesis.get(c.id)}</p>
            )}
            <ul className="mt-3 space-y-1.5 text-sm">
              {byCompany.get(c.id)!.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center gap-2">
                  {r.url ? (
                    <a href={r.url} rel="noopener" target="_blank" className="font-medium text-emerald-800 hover:underline">
                      {r.title}
                    </a>
                  ) : (
                    <span className="font-medium">{r.title}</span>
                  )}
                  {r.location && <span className="text-neutral-500">— {r.location}</span>}
                  <span className="rounded bg-neutral-100 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-neutral-600">
                    {r.role_class}
                  </span>
                  {new Date(r.first_seen).getTime() > newCutoff && (
                    <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-amber-800">
                      new
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </article>
        );
      })}

      {watchlist.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-600">
            High-score companies with no known openings yet
          </h2>
          <p className="mb-3 text-xs text-neutral-500">
            Worth a manual careers-page check or a <code className="rounded bg-neutral-100 px-1">find-roles --deep</code> run.
          </p>
          <ul className="flex flex-wrap gap-2 text-sm">
            {watchlist.map((c) => (
              <li key={c.id}>
                <Link
                  href={`/companies/${c.id}`}
                  className="rounded-md border border-neutral-300 bg-white px-2.5 py-1 hover:border-emerald-700 hover:text-emerald-800"
                >
                  {c.name} · {Number(c.job_target_score).toFixed(2)}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
