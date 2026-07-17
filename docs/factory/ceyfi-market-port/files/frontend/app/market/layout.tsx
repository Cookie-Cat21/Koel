import type { Metadata } from "next";
import { createPageMetadata } from "@/lib/seo";

export const metadata: Metadata = createPageMetadata({
  title: "Market",
  description:
    "CSE watchlist and Chime alerts inside Ceyfi — cash context beside market pings. Not a stockbroker.",
  path: "/market",
});

export default function MarketLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
