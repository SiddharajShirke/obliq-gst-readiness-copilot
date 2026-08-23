import type { Metadata } from "next";
import { Toaster } from "sonner";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import {ThemeProvider, THEME_INIT_SCRIPT} from "@/lib/theme";

export const metadata: Metadata = {
  title: "OBLIQ GST Readiness Copilot",
  description: "AI-powered GST document collection, extraction and reconciliation for Indian CA firms.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning data-scroll-behavior="smooth">
      <head><script dangerouslySetInnerHTML={{__html: THEME_INIT_SCRIPT}}/></head>
      <body>
        <ThemeProvider><AuthProvider>{children}</AuthProvider></ThemeProvider>
        <Toaster richColors position="top-right" />
      </body>
    </html>
  );
}
