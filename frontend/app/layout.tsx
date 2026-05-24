import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "TuneSlice — Waveform Song Snippet Generator",
  description: "A professional, interactive waveform editor to visually slice, preview, and generate high-quality 30-second clips from your favorite songs.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased dark`}>
      <body className="min-h-full bg-zinc-950 text-zinc-50 font-sans selection:bg-emerald-500 selection:text-black">
        {children}
      </body>
    </html>
  );
}
