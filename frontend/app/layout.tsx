import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "Wavora — Waveform Song Snippet Generator",
  description: "A professional, interactive waveform editor to visually slice, preview, and generate high-quality 30-second clips from your favorite songs.",
};

import { Toaster } from "react-hot-toast";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased dark`}>
      <body className="min-h-full bg-background text-foreground font-sans selection:bg-primary selection:text-black">
        {children}
        <Toaster 
          position="bottom-right"
          toastOptions={{
            style: {
              background: '#1c1c1e',
              color: '#fff',
              border: '1px solid rgba(255, 255, 255, 0.15)',
            },
            success: {
              iconTheme: {
                primary: '#14b861',
                secondary: '#fff',
              },
            },
          }}
        />
      </body>
    </html>
  );
}
