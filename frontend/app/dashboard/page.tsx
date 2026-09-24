"use client";

import * as React from "react";
import Link from "next/link";
import { RequireAuth } from "@/components/require-auth";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { PregnancyResponse } from "@/lib/types";
import { NextVisitCard } from "@/components/next-visit-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { MessagesSquare, Apple, Sprout, BookOpen, Sparkles, Library, Settings } from "lucide-react";

const quickLinks = [
  { href: "/chat", label: "Chat with MATRIVA", icon: MessagesSquare },
  { href: "/recommendations", label: "Recommendations", icon: Sparkles },
  { href: "/nutrition", label: "Nutrition", icon: Apple },
  { href: "/ayurveda", label: "Ayurveda & traditional knowledge", icon: Sprout },
  { href: "/guidance", label: "Stage-wise guidance", icon: BookOpen },
  { href: "/sources", label: "Sources & evidence", icon: Library },
  { href: "/settings", label: "Settings", icon: Settings },
];

function DashboardContent() {
  const { user } = useAuth();
  const [pregnancy, setPregnancy] = React.useState<PregnancyResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    api
      .get<PregnancyResponse>("/pregnancy")
      .then((res) => {
        if (!cancelled) setPregnancy(res);
      })
      .catch((err) => {
        if (!cancelled) {
          if (err instanceof ApiError && err.status === 404) {
            setError("You haven't added your pregnancy details yet.");
          } else {
            setError(err instanceof ApiError ? err.message : "Could not load your pregnancy info.");
          }
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-10">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">
          Welcome{user?.full_name ? `, ${user.full_name}` : ""}
        </h1>
        <p className="text-muted-foreground">Here&apos;s your personalized pregnancy overview.</p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Your pregnancy stage</CardTitle>
          </CardHeader>
          <CardContent>
            {loading && <LoadingState label="Loading..." />}
            {!loading && error && (
              <Alert variant="warning">
                <AlertDescription>
                  {error}{" "}
                  <Link href="/onboarding" className="underline">
                    Complete onboarding
                  </Link>
                </AlertDescription>
              </Alert>
            )}
            {!loading && pregnancy && (
              <div className="flex flex-col gap-1">
                <p className="text-2xl font-semibold capitalize text-foreground">
                  {pregnancy.stage.replace(/_/g, " ")}
                </p>
                <p className="text-sm text-muted-foreground">
                  Week {pregnancy.current_week} · Trimester {pregnancy.trimester}
                </p>
                {pregnancy.due_date && (
                  <p className="text-sm text-muted-foreground">Due date: {pregnancy.due_date}</p>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <NextVisitCard />
      </div>

      <div>
        <h2 className="mb-4 text-lg font-semibold text-foreground">Quick links</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {quickLinks.map((link) => (
            <Link key={link.href} href={link.href}>
              <Card className="h-full transition-colors hover:border-primary">
                <CardContent className="flex items-center gap-3 p-5">
                  <link.icon className="h-5 w-5 text-primary" />
                  <span className="font-medium text-foreground">{link.label}</span>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardContent />
    </RequireAuth>
  );
}
