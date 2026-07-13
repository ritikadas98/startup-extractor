import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import Nav from "@/components/Nav";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "startup_intel",
  description: "Indian startup funding intelligence & PM knowledge base",
  // disables the Dark Reader browser extension on this site (it was inverting
  // our light theme into unreadable grey-on-black)
  other: { "darkreader-lock": "true" },
};

export const viewport = { colorScheme: "light" as const };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-neutral-50 text-neutral-900">
        <header className="border-b border-neutral-200 bg-white">
          <div className="mx-auto flex max-w-4xl items-center gap-6 px-4 py-3">
            <Link href="/" className="font-bold text-emerald-800">
              startup_intel
            </Link>
            <Nav />
          </div>
        </header>
        <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-8">{children}</main>
        <footer className="mx-auto w-full max-w-4xl px-4 py-8 text-xs text-neutral-500">
          AI-generated analyses for learning purposes — not investment advice. Summaries link
          to original articles; no article text is republished.
        </footer>
      </body>
    </html>
  );
}
