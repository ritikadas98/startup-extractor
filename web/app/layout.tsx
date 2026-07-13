import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "startup_intel",
  description: "Indian startup funding intelligence & PM knowledge base",
};

const nav = [
  { href: "/", label: "Briefing" },
  { href: "/companies", label: "Companies" },
  { href: "/search", label: "Search" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-neutral-50 text-neutral-900">
        <header className="border-b border-neutral-200 bg-white">
          <div className="mx-auto max-w-4xl px-4 py-3 flex items-baseline gap-6">
            <Link href="/" className="font-bold text-emerald-800">
              startup_intel
            </Link>
            <nav className="flex gap-4 text-sm">
              {nav.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  className="text-neutral-600 hover:text-emerald-700"
                >
                  {n.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-8">{children}</main>
        <footer className="mx-auto w-full max-w-4xl px-4 py-8 text-xs text-neutral-400">
          AI-generated analyses for learning purposes — not investment advice. Summaries link
          to original articles; no article text is republished.
        </footer>
      </body>
    </html>
  );
}
