"use client";

import * as React from "react";
import Link from "next/link";
import { RequireAuth } from "@/components/require-auth";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { PregnancyResponse } from "@/lib/types";
import { NextVisitCard } from "@/components/next-visit-card";
import { PregnancyVisualization } from "@/components/pregnancy-visualization";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  MessagesSquare,
  Apple,
  Sprout,
  BookOpen,
  Sparkles,
  Library,
  Settings,
  Droplets,
  Moon,
  Activity,
  Pill,
  Stethoscope,
  CalendarClock,
} from "lucide-react";

const quickLinks = [
  { href: "/chat", label: "Chat with MATRIVA", icon: MessagesSquare },
  { href: "/recommendations", label: "Recommendations", icon: Sparkles },
  { href: "/nutrition", label: "Nutrition", icon: Apple },
  { href: "/ayurveda", label: "Ayurveda & traditional knowledge", icon: Sprout },
  { href: "/guidance", label: "Stage-wise guidance", icon: BookOpen },
  { href: "/sources", label: "Sources & evidence", icon: Library },
  { href: "/settings", label: "Settings", icon: Settings },
];

// Developmental milestones per trimester. This is general, widely-known
// pregnancy-education content (not user-specific medical advice) used only
// to give the dashboard's "baby development" section something concrete to
// show; the backend has no per-week milestone endpoint.
const TRIMESTER_MILESTONES: Record<number, { title: string; detail: string }[]> = {
  1: [
    { title: "Major organs begin forming", detail: "The heart, brain, and spinal cord start to develop." },
    { title: "Heartbeat may become detectable", detail: "Around week 6-8, on ultrasound." },
    { title: "Limb buds appear", detail: "Tiny arm and leg buds start to take shape." },
  ],
  2: [
    { title: "Movements may be felt", detail: "Many mothers begin feeling fluttering movements." },
    { title: "Sex may be visible on ultrasound", detail: "Typically around week 18-20." },
    { title: "Hearing develops", detail: "Baby can start responding to sounds and voices." },
  ],
  3: [
    { title: "Rapid weight gain", detail: "Baby gains most of their birth weight in this stage." },
    { title: "Lungs mature", detail: "Preparing for breathing outside the womb." },
    { title: "Head-down positioning", detail: "Baby typically settles head-down ahead of delivery." },
  ],
};

// Mock/static wellness data — the backend has no hydration, sleep, or
// activity-tracking endpoints, so these are clearly-labeled placeholder
// values for the wellness teaser section, not real tracked data.
const MOCK_WELLNESS = {
  hydrationCupsOfEight: 5,
  sleepHours: 7.2,
  activityMinutes: 22,
};

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

  const trimester = pregnancy?.trimester ?? 1;
  const week = pregnancy?.current_week ?? 8;
  const progressPct = Math.min(100, Math.round((week / 40) * 100));
  const milestones = TRIMESTER_MILESTONES[Math.min(3, Math.max(1, trimester))];

  return (
    <main className="flex flex-col">
      {/* ---------- Header ---------- */}
      <div className="border-b border-border bg-wellness-gradient">
        <div className="mx-auto flex max-w-6xl flex-col gap-1 px-4 py-8">
          <h1 className="text-2xl font-semibold text-foreground sm:text-3xl">
            Welcome{user?.full_name ? `, ${user.full_name}` : ""}
          </h1>
          <p className="text-muted-foreground">Here&apos;s your personalized pregnancy overview.</p>
        </div>
      </div>

      <div className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-4 py-10">
        {/* ---------- Main pregnancy progress section ---------- */}
        <section aria-labelledby="progress-heading">
          <h2 id="progress-heading" className="mb-4 text-lg font-semibold text-foreground">
            Your pregnancy progress
          </h2>
          <Card>
            <CardContent className="grid gap-8 p-6 md:grid-cols-[auto_1fr] md:p-8">
              <div className="flex justify-center md:justify-start">
                {loading ? (
                  <div className="flex h-60 w-60 items-center justify-center border border-border bg-card">
                    <LoadingState label="Loading..." />
                  </div>
                ) : (
                  <PregnancyVisualization trimester={trimester} currentWeek={week} variant="dashboard" />
                )}
              </div>

              <div className="flex flex-col justify-center gap-4">
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
                  <>
                    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                      <p className="text-3xl font-semibold capitalize text-foreground">
                        {pregnancy.stage.replace(/_/g, " ")}
                      </p>
                      <Badge variant="secondary">Trimester {pregnancy.trimester}</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Week {pregnancy.current_week} of 40
                      {pregnancy.due_date && <> · Due date: {pregnancy.due_date}</>}
                    </p>

                    {/* Pregnancy progress bar / timeline */}
                    <div className="flex flex-col gap-1.5">
                      <div className="h-2 w-full border border-border bg-muted">
                        <div
                          className="h-full bg-sky-panel-gradient"
                          style={{ width: `${progressPct}%` }}
                          role="progressbar"
                          aria-valuenow={progressPct}
                          aria-valuemin={0}
                          aria-valuemax={100}
                        />
                      </div>
                      <div className="flex justify-between text-[11px] uppercase tracking-wide text-muted-foreground">
                        <span>Trimester 1</span>
                        <span>Trimester 2</span>
                        <span>Trimester 3</span>
                        <span>Delivery</span>
                      </div>
                    </div>

                    <p className="text-sm text-muted-foreground">
                      {pregnancy.first_pregnancy ? "This is your first pregnancy." : "This is not your first pregnancy."}
                    </p>
                  </>
                )}

                {!loading && !error && !pregnancy && (
                  <p className="text-sm text-muted-foreground">Complete onboarding to see your progress here.</p>
                )}
              </div>
            </CardContent>
          </Card>
        </section>

        {/* ---------- Baby development ---------- */}
        <section aria-labelledby="development-heading">
          <div className="mb-4 flex items-center justify-between">
            <h2 id="development-heading" className="text-lg font-semibold text-foreground">
              Baby development
            </h2>
            <span className="text-xs text-muted-foreground">What&apos;s generally happening this trimester</span>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            {milestones.map((m) => (
              <Card key={m.title}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">{m.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">{m.detail}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        {/* ---------- Mother's wellness ---------- */}
        <section aria-labelledby="wellness-heading">
          <div className="mb-4 flex items-center justify-between">
            <h2 id="wellness-heading" className="text-lg font-semibold text-foreground">
              Mother&apos;s wellness
            </h2>
            <span className="text-xs text-muted-foreground">Illustrative — not connected to a tracker yet</span>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardContent className="flex flex-col gap-2 p-5">
                <div className="flex items-center gap-2 text-primary">
                  <Droplets className="h-5 w-5" />
                  <span className="text-sm font-medium text-foreground">Hydration</span>
                </div>
                <p className="text-2xl font-semibold text-foreground">
                  {MOCK_WELLNESS.hydrationCupsOfEight}
                  <span className="text-sm font-normal text-muted-foreground"> / 8 cups</span>
                </p>
                <div className="h-1.5 w-full bg-muted">
                  <div
                    className="h-full bg-primary"
                    style={{ width: `${(MOCK_WELLNESS.hydrationCupsOfEight / 8) * 100}%` }}
                  />
                </div>
                <Badge variant="outline" className="w-fit text-[10px]">Sample data</Badge>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="flex flex-col gap-2 p-5">
                <div className="flex items-center gap-2 text-primary">
                  <Moon className="h-5 w-5" />
                  <span className="text-sm font-medium text-foreground">Sleep</span>
                </div>
                <p className="text-2xl font-semibold text-foreground">
                  {MOCK_WELLNESS.sleepHours}
                  <span className="text-sm font-normal text-muted-foreground"> hrs last night</span>
                </p>
                <div className="h-1.5 w-full bg-muted">
                  <div className="h-full bg-primary" style={{ width: `${(MOCK_WELLNESS.sleepHours / 9) * 100}%` }} />
                </div>
                <Badge variant="outline" className="w-fit text-[10px]">Sample data</Badge>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="flex flex-col gap-2 p-5">
                <div className="flex items-center gap-2 text-primary">
                  <Activity className="h-5 w-5" />
                  <span className="text-sm font-medium text-foreground">Activity</span>
                </div>
                <p className="text-2xl font-semibold text-foreground">
                  {MOCK_WELLNESS.activityMinutes}
                  <span className="text-sm font-normal text-muted-foreground"> min today</span>
                </p>
                <div className="h-1.5 w-full bg-muted">
                  <div
                    className="h-full bg-primary"
                    style={{ width: `${Math.min(100, (MOCK_WELLNESS.activityMinutes / 30) * 100)}%` }}
                  />
                </div>
                <Badge variant="outline" className="w-fit text-[10px]">Sample data</Badge>
              </CardContent>
            </Card>

            <Link href="/nutrition">
              <Card className="h-full transition-colors hover:border-primary">
                <CardContent className="flex flex-col gap-2 p-5">
                  <div className="flex items-center gap-2 text-primary">
                    <Apple className="h-5 w-5" />
                    <span className="text-sm font-medium text-foreground">Nutrition</span>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Browse real, evidence-checked food guidance for your stage.
                  </p>
                  <Badge variant="secondary" className="w-fit text-[10px]">Live data</Badge>
                </CardContent>
              </Card>
            </Link>
          </div>
        </section>

        {/* ---------- Important information ---------- */}
        <section aria-labelledby="important-heading">
          <h2 id="important-heading" className="mb-4 text-lg font-semibold text-foreground">
            Important information
          </h2>
          <div className="grid gap-4 md:grid-cols-3">
            <NextVisitCard />

            <Card>
              <CardHeader className="flex flex-row items-center gap-2 space-y-0">
                <Pill className="h-5 w-5 text-primary" />
                <CardTitle className="text-base">Vitamin & medication reminder</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Remember your prenatal vitamin (e.g. folic acid, iron) as advised by your provider.
                </p>
                <Badge variant="outline" className="mt-3 text-[10px]">Sample reminder</Badge>
              </CardContent>
            </Card>

            <Card className="border-primary/40 bg-sky-50">
              <CardHeader className="flex flex-row items-center gap-2 space-y-0">
                <Stethoscope className="h-5 w-5 text-primary" />
                <CardTitle className="text-base">Talk to your doctor</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription>
                  MATRIVA provides general, evidence-informed guidance. Always confirm anything important — symptoms,
                  medication, or diet changes — with your own healthcare provider.
                </CardDescription>
              </CardContent>
            </Card>
          </div>
        </section>

        {/* ---------- Quick links ---------- */}
        <section aria-labelledby="quicklinks-heading">
          <div className="mb-4 flex items-center gap-2">
            <CalendarClock className="h-5 w-5 text-primary" />
            <h2 id="quicklinks-heading" className="text-lg font-semibold text-foreground">
              Quick links
            </h2>
          </div>
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
        </section>
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
