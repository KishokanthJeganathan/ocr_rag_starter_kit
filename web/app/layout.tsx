import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Document Review",
  description: "Extraction results and validation verdicts",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <Link href="/" className="topbar-title">
            Document Review
          </Link>
        </header>
        <main className="page">{children}</main>
      </body>
    </html>
  );
}
