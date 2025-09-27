import type { Metadata } from "next";
import "./globals.css";
import { WalletProvider } from "./WalletProvider";
import "nes.css/css/nes.min.css";

export const metadata: Metadata = {
  title: "NakalTrade Agent",
  description: "AI-powered portfolio analysis and copy trading",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <WalletProvider>{children}</WalletProvider>
      </body>
    </html>
  );
}
