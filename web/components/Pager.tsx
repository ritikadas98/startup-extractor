import Link from "next/link";

export default function Pager({
  base,
  page,
  hasMore,
  extra = "",
}: {
  base: string;
  page: number;
  hasMore: boolean;
  extra?: string; // extra querystring, e.g. "&q=fintech"
}) {
  return (
    <div className="flex items-center justify-between pt-2 text-sm">
      {page > 1 ? (
        <Link
          href={`${base}?page=${page - 1}${extra}`}
          className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 hover:border-emerald-700 hover:text-emerald-800"
        >
          ← Newer
        </Link>
      ) : (
        <span />
      )}
      <span className="text-xs text-neutral-500">page {page}</span>
      {hasMore ? (
        <Link
          href={`${base}?page=${page + 1}${extra}`}
          className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 hover:border-emerald-700 hover:text-emerald-800"
        >
          Older →
        </Link>
      ) : (
        <span />
      )}
    </div>
  );
}
