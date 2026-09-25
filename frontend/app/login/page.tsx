"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";

export default function LoginPage() {
  const { login, user } = useAuth();
  const router = useRouter();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    if (user) router.replace("/dashboard");
  }, [user, router]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="grid min-h-[calc(100vh-4rem)] lg:grid-cols-[minmax(0,42rem)_1fr]">
      {/* the plate */}
      <div className="relative hidden overflow-hidden bg-cream-200 lg:block">
        <div className="relative h-[52vh] w-full">
          <Image
            src="/plates/gestation.jpg"
            alt="Watercolour study of pregnancy from conception to birth"
            fill
            sizes="42rem"
            className="object-cover"
            priority
          />
          <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-cream-200 to-transparent" />
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_78%_18%,hsl(var(--sage-200)/0.34),transparent_58%)]" />
        </div>

        <div className="flex flex-col justify-between px-14 py-10" style={{ minHeight: "calc(100% - 52vh)" }}>
          <div>
            <div className="h-px w-10 bg-accent" />
            <blockquote className="display mt-7 text-[2.5rem] leading-[1.18]">
              Forty weeks is a long
              <br />
              <span className="italic text-accent">time to be guessing.</span>
            </blockquote>
          </div>
          <div className="eyebrow-sm flex justify-between border-t border-border pt-5 text-muted-foreground">
            <span>Plate I — Gestation</span>
            <span>Evidence first, always</span>
          </div>
        </div>
      </div>

      {/* the form */}
      <div className="relative flex items-center justify-center px-6 py-16">
        <p className="absolute right-8 top-8 text-xs text-muted-foreground">
          New here?{" "}
          <Link href="/signup" className="border-b border-foreground pb-0.5 font-semibold text-foreground">
            Create an account
          </Link>
        </p>

        <form onSubmit={onSubmit} className="w-full max-w-[25rem]">
          <p className="eyebrow text-accent">Sign in</p>
          <h1 className="display mt-4 text-[3rem] leading-[1]">Welcome back.</h1>
          <p className="mt-3.5 text-[15px] text-muted-foreground">Pick up where your week left off.</p>

          {error && (
            <Alert variant="destructive" className="mt-8">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="mt-11 flex flex-col gap-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="mt-7 flex flex-col gap-1.5">
            <div className="flex items-baseline justify-between">
              <Label htmlFor="password">Password</Label>
              <span className="text-[10.5px] font-semibold text-muted-foreground">Forgotten?</span>
            </div>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••••••"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <Button type="submit" disabled={loading} size="lg" className="mt-11 w-full justify-between">
            {loading ? "Signing in…" : "Continue"}
            <span aria-hidden="true">→</span>
          </Button>

          <p className="mt-10 text-[11px] leading-relaxed text-muted-foreground">
            Your pregnancy data stays yours. Export or delete it any time in Settings — it is never used to
            train anything.
          </p>
        </form>
      </div>
    </main>
  );
}
