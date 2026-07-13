import { humanize, orderedEntries, NESTED_ORDER } from "@/lib/layers";

function isNullish(v: unknown): boolean {
  if (v === null || v === undefined || v === "") return true;
  if (typeof v === "string" && ["null", "none", "unknown", "n/a"].includes(v.trim().toLowerCase()))
    return true;
  if (Array.isArray(v) && v.length === 0) return true;
  return false;
}

function Value({ v, keyName }: { v: unknown; keyName?: string }) {
  if (isNullish(v)) return <span className="text-neutral-400">—</span>;
  if (typeof v === "boolean") return <span>{v ? "yes" : "no"}</span>;
  if (typeof v === "number")
    return <span className="tabular-nums">{v.toLocaleString("en-IN")}</span>;
  if (typeof v === "string") return <p className="whitespace-pre-wrap">{v}</p>;
  if (Array.isArray(v)) {
    if (v.every((i) => typeof i === "string"))
      return (
        <ul className="list-disc pl-5 space-y-1">
          {v.map((i, n) => (
            <li key={n}>{i as string}</li>
          ))}
        </ul>
      );
    return (
      <div className="space-y-3">
        {v.map((i, n) => (
          <div key={n} className="border-l-2 border-emerald-200 pl-3">
            <Value v={i} keyName={keyName} />
          </div>
        ))}
      </div>
    );
  }
  if (typeof v === "object") {
    const entries = orderedEntries(
      v as Record<string, unknown>,
      keyName ? NESTED_ORDER[keyName] : undefined
    );
    return (
      <div className="space-y-1">
        {entries.map(([k, val]) => (
          <div key={k} className="grid grid-cols-[9rem_1fr] gap-2">
            <span className="text-xs font-medium text-neutral-600 pt-0.5">{humanize(k)}</span>
            <Value v={val} keyName={k} />
          </div>
        ))}
      </div>
    );
  }
  return <span>{String(v)}</span>;
}

export default function JsonBlock({
  data,
  order,
}: {
  data: Record<string, unknown>;
  order?: string[];
}) {
  return (
    <div className="space-y-3 text-sm leading-relaxed">
      {orderedEntries(data, order).map(([k, v]) =>
        isNullish(v) ? null : (
          <div key={k}>
            <div className="text-xs font-semibold uppercase tracking-wide text-neutral-600 mb-1">
              {humanize(k)}
            </div>
            <Value v={v} keyName={k} />
          </div>
        )
      )}
    </div>
  );
}
