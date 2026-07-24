import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/shared/Sidebar";

export const metadata: Metadata = {
  title: "FinHub — Equity Research Terminal",
  description: "Plataforma personal de análisis de inversiones",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className="bg-bg text-gray-200 antialiased">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 p-6 overflow-x-auto">{children}</main>
        </div>
      </body>
    </html>
  );
}

