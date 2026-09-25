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

export default function SignupPage() {
  const { register, user } = useAuth();
  const router = useRouter();
  const [fullName, setFullName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    if (user) router.replace("/onboarding");
  }, [user, router]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register(email, password, fullName || undefined);
      router.push("/onboarding");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="grid min-h-[calc(100vh-4rem)] lg:grid-cols-[1fr_minmax(0,42rem)]">
      {/* the form */}
      <div className="relative order-2 flex items-center justify-center px-6 py-16 lg:order-1">
        <p className="absolute left-8 top-8 text-xs text-muted-foreground">
          Already have an account?{" "}
          <Link href="/login" className="border-b border-foreground pb-0.5 font-semibold text-foreground">
            Sign in
          </Link>
        </p>

        <form onSubmit={onSubmit} className="w-full max-w-[25rem]">
          <p className="eyebrow text-accent">Create an account</p>
          <h1 className="display mt-4 text-[3rem] leading-[1]">Begin here.</h1>
          <p className="mt-3.5 text-[15px] text-muted-foreground">
            Two minutes, and a dashboard built around your week.
          </p>

          {error && (
            <Alert variant="destructive" className="mt-8">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="mt-11 flex flex-col gap-1.5">
            <Label htmlFor="fullName">
              Full name <span className="normal-case font-normal tracking-normal">(optional)</span>
            </Label>
            <Input
              id="fullName"
              placeholder="Ananya Rao"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>

          <div className="mt-7 flex flex-col gap-1.5">
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
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              placeholder="••••••••••••"
              required
              minLength={12}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <p className="mt-1 text-xs text-muted-foreground">At least 12 characters, with a letter and a number.</p>
          </div>

          <Button type="submit" disabled={loading} size="lg" className="mt-11 w-full justify-between">
            {loading ? "Creating account…" : "Sign up"}
            <span aria-hidden="true">→</span>
          </Button>
        </form>
      </div>

      {/* the plate */}
      <div className="relative order-1 hidden overflow-hidden bg-cream-200 lg:order-2 lg:block">
        <div className="relative h-[52vh] w-full">
          <Image
            src="/plates/nutrition.jpg"
            alt="Illustration of a pregnant woman surrounded by nourishing foods"
            fill
            sizes="42rem"
            className="object-cover"
            priority
          />
          <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-cream-200 to-transparent" />
        </div>

        <div className="flex flex-col justify-between px-14 py-10" style={{ minHeight: "calc(100% - 52vh)" }}>
          <div>
            <div className="h-px w-10 bg-accent" />
            <blockquote className="display mt-7 text-[2.5rem] leading-[1.18]">
              Evidence-based,
              <br />
              <span className="italic text-accent">warmly delivered.</span>
            </blockquote>
          </div>
          <div className="eyebrow-sm flex justify-between border-t border-border pt-5 text-muted-foreground">
            <span>Plate II — Nutrition</span>
            <span>Clinical + Ayurvedic</span>
          </div>
        </div>
      </div>
    </main>
  );
}
