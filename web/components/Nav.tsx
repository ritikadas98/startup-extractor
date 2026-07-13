"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/", label: "Briefing" },
  { href: "/companies", label: "Companies" },
  { href: "/search", label: "Search" },
  { href: "/archive", label: "Archive" },
  { href: "/status", label: "Status" },
];

export default function Nav() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-1 text-sm">
      {items.map((n) => {
        const active =
          n.href === "/" ? pathname === "/" : pathname.startsWith(n.href);
        return (
          <Link
            key={n.href}
            href={n.href}
            className={
              "rounded-md px-3 py-1.5 " +
              (active
                ? "bg-emerald-700 font-semibold text-white"
                : "text-neutral-600 hover:bg-neutral-100 hover:text-emerald-800")
            }
          >
            {n.label}
          </Link>
        );
      })}
    </nav>
  );
}
