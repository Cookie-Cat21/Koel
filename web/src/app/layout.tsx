import type { Metadata, Viewport } from "next";
import { Fraunces, Sora, JetBrains_Mono } from "next/font/google";

import { Providers } from "@/components/providers";
import { SkipLink } from "@/components/skip-link";
import "./globals.css";

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  display: "swap",
});

const sora = Sora({
  variable: "--font-sora",
  subsets: ["latin"],
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Chime",
  description:
    "Telegram-first CSE alerting — manage watchlists and alert rules.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${fraunces.variable} ${sora.variable} ${jetbrains.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col font-sans">
        <SkipLink />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
