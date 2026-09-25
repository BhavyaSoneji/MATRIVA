import type { Metadata, Viewport } from "next";
import { Instrument_Serif, Schibsted_Grotesk } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { NavBar } from "@/components/nav-bar";
import { Grain } from "@/components/grain";

const display = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-display",
  display: "swap",
});

const sans = Schibsted_Grotesk({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "MATRIVA",
    template: "%s · MATRIVA",
  },
  description: "AI pregnancy guidance grounded in evidence, modern medicine, and traditional knowledge.",
};

export const viewport: Viewport = {
  themeColor: "#F5F2EA",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable}`}>
      <body className="min-h-screen bg-background font-sans antialiased">
        <AuthProvider>
          <NavBar />
          <div className="min-h-[calc(100vh-4rem)]">{children}</div>
        </AuthProvider>
        <Grain />
      </body>
    </html>
  );
}
