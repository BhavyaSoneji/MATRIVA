"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Leaf } from "lucide-react";

const links = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/chat", label: "Chat" },
  { href: "/nutrition", label: "Nutrition" },
  { href: "/lifestyle", label: "Lifestyle" },
  { href: "/ayurveda", label: "Ayurveda" },
  { href: "/guidance", label: "Guidance" },
  { href: "/recommendations", label: "Recommendations" },
  { href: "/sources", label: "Sources" },
  { href: "/settings", label: "Settings" },
];

const adminLinks = [
  { href: "/admin/documents", label: "Admin: Documents" },
  { href: "/admin/evaluation", label: "Admin: Evaluation" },
];

export function NavBar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push("/");
  };

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold text-primary">
          <Leaf className="h-5 w-5" />
          MATRIVA
        </Link>
        {user && (
          <nav className="hidden flex-1 flex-wrap items-center gap-1 overflow-x-auto lg:flex">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-md px-2.5 py-1.5 text-sm transition-colors hover:bg-muted ${
                  pathname === link.href ? "bg-muted font-medium text-primary" : "text-foreground/80"
                }`}
              >
                {link.label}
              </Link>
            ))}
            {user.role === "admin" &&
              adminLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-md px-2.5 py-1.5 text-sm transition-colors hover:bg-muted ${
                    pathname === link.href ? "bg-muted font-medium text-primary" : "text-foreground/80"
                  }`}
                >
                  {link.label}
                </Link>
              ))}
          </nav>
        )}
        <div className="flex items-center gap-2">
          {user ? (
            <>
              <span className="hidden text-sm text-muted-foreground sm:inline">{user.email}</span>
              <Button variant="outline" size="sm" onClick={handleLogout}>
                Log out
              </Button>
            </>
          ) : (
            <>
              <Link href="/login">
                <Button variant="ghost" size="sm">
                  Log in
                </Button>
              </Link>
              <Link href="/signup">
                <Button size="sm">Sign up</Button>
              </Link>
            </>
          )}
        </div>
      </div>
      {user && (
        <nav className="flex flex-wrap gap-1 border-t border-border px-4 py-1.5 lg:hidden">
          {[...links, ...(user.role === "admin" ? adminLinks : [])].map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`rounded-md px-2 py-1 text-xs ${
                pathname === link.href ? "bg-muted font-medium text-primary" : "text-foreground/70"
              }`}
            >
              {link.label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}
