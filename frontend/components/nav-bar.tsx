"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";

const links = [
  { href: "/dashboard", label: "Overview" },
  { href: "/nutrition", label: "Nutrition" },
  { href: "/ayurveda", label: "Ayurveda" },
  { href: "/lifestyle", label: "Lifestyle" },
  { href: "/recommendations", label: "For you" },
  { href: "/chat", label: "Companion" },
  { href: "/guidance", label: "Guidance" },
  { href: "/sources", label: "Evidence" },
  { href: "/settings", label: "Settings" },
];

const adminLinks = [
  { href: "/admin/documents", label: "Documents" },
  { href: "/admin/evaluation", label: "Evaluation" },
];

function navClass(active: boolean) {
  return [
    "eyebrow whitespace-nowrap py-1 transition-colors",
    active ? "text-accent" : "text-muted-foreground hover:text-foreground",
  ].join(" ");
}

export function NavBar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push("/");
  };

  const allLinks = user?.role === "admin" ? [...links, ...adminLinks] : links;

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1400px] items-center justify-between gap-8 px-6">
        <Link href="/" className="flex shrink-0 items-baseline gap-3">
          <span className="display text-[22px] tracking-[0.1em] text-foreground">MATRIVA</span>
          <span className="eyebrow hidden text-muted-foreground sm:inline">Est. 2026</span>
        </Link>

        {user && (
          <nav className="hidden flex-1 items-center justify-center gap-7 overflow-x-auto xl:flex">
            {allLinks.map((link) => (
              <Link key={link.href} href={link.href} className={navClass(pathname === link.href)}>
                {link.label}
              </Link>
            ))}
          </nav>
        )}

        <div className="flex shrink-0 items-center gap-5">
          {user ? (
            <>
              <span className="hidden text-xs text-muted-foreground lg:inline">{user.email}</span>
              <button
                type="button"
                onClick={handleLogout}
                className="eyebrow border-b border-border pb-0.5 text-foreground transition-colors hover:border-accent hover:text-accent"
              >
                Sign out
              </button>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className="eyebrow border-b border-border pb-0.5 text-foreground transition-colors hover:border-accent hover:text-accent"
              >
                Sign in
              </Link>
              <Link href="/signup">
                <Button size="sm">Get started</Button>
              </Link>
            </>
          )}
        </div>
      </div>

      {user && (
        <nav className="flex gap-6 overflow-x-auto border-t border-border px-6 py-2.5 xl:hidden">
          {allLinks.map((link) => (
            <Link key={link.href} href={link.href} className={navClass(pathname === link.href)}>
              {link.label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}
