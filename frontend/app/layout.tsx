import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { NavBar } from "@/components/nav-bar";

export const metadata: Metadata = {
  title: "MATRIVA",
  description: "AI pregnancy guidance grounded in evidence, modern medicine, and traditional knowledge.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background font-sans antialiased">
        <AuthProvider>
          <NavBar />
          <div className="min-h-[calc(100vh-4rem)]">{children}</div>
        </AuthProvider>
      </body>
    </html>
  );
}
