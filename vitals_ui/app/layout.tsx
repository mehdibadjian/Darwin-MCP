import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Darwin-MCP Intelligence Dashboard",
  description: "Sovereign vitals interface for the Darwin-MCP organism",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-sovereign-bg font-mono text-sovereign-text">
        {children}
      </body>
    </html>
  );
}
