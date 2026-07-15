import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import localFont from "next/font/local";

import { Providers } from "@/components/providers";
import { SkipLink } from "@/components/skip-link";
import "./globals.css";

/** Display / headings — Cal Sans (OFL), local static cuts for weight control. */
const calSans = localFont({
  src: [
    {
      path: "../fonts/CalSans-Regular.woff2",
      weight: "400",
      style: "normal",
    },
    {
      path: "../fonts/CalSans-Medium.woff2",
      weight: "500",
      style: "normal",
    },
    {
      path: "../fonts/CalSans-SemiBold.woff2",
      weight: "600",
      style: "normal",
    },
    {
      path: "../fonts/CalSans-Bold.woff2",
      weight: "700",
      style: "normal",
    },
  ],
  variable: "--font-cal-sans",
  display: "swap",
});

/** Body / UI chrome — Inter. */
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

/** Code / IDs on the dash — unchanged. */
const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Chime",
  description:
    "Telegram-first CSE alerting — manage watchlists and alert rules.",
  icons: {
    icon: [{ url: "/brand/chime-mark.svg", type: "image/svg+xml" }],
    apple: [{ url: "/brand/chime-mark.png" }],
  },
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
      className={`${calSans.variable} ${inter.variable} ${jetbrains.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col font-sans">
        <SkipLink />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
