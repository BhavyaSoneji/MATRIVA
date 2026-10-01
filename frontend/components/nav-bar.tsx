"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";

const links = [{ href: "/chat", label: "Companion" }];

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
  const accountLinks = [{ href: "/settings", label: "Settings" }];

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1400px] items-center justify-between gap-8 px-6">
        <Link href="/" className="flex shrink-0 items-baseline gap-3">
          <span className="display text-[22px] tracking-[0.1em] text-foreground">MATRIVA</span>
          <span className="eyebrow hidden text-muted-foreground sm:inline">Est. 2026</span>
        </Link>

        {user && (
          <nav className="hidden flex-1 items-center justify-center gap-7 overflow-x-auto md:flex">
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
              {accountLinks.map((link) => (
                <Link key={link.href} href={link.href} className={navClass(pathname === link.href)}>
                  {link.label}
                </Link>
              ))}
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

    </header>
  );
}
