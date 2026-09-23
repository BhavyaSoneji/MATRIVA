import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MATRIVA",
  description: "Holistic AI pregnancy guidance platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
