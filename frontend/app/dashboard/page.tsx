"use client";

import * as React from "react";
import Link from "next/link";
import { RequireAuth } from "@/components/require-auth";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import type { PregnancyResponse } from "@/lib/types";
import { NextVisitCard } from "@/components/next-visit-card";
import { PregnancyVisualization } from "@/components/pregnancy-visualization";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
} from "lucide-react";

const quickLinks = [
  { index: "01", href: "/chat", label: "Chat with MATRIVA", icon: MessagesSquare },
  { index: "02", href: "/recommendations", label: "Recommendations", icon: Sparkles },
  { index: "03", href: "/nutrition", label: "Nutrition", icon: Apple },
  { index: "04", href: "/ayurveda", label: "Ayurveda & traditional knowledge", icon: Sprout },
  { index: "05", href: "/guidance", label: "Stage-wise guidance", icon: BookOpen },
  { index: "06", href: "/sources", label: "Sources & evidence", icon: Library },
  { index: "07", href: "/settings", label: "Settings", icon: Settings },
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
const MOCK_WELLNESS = [
  { label: "Hydration", value: 5, max: 8, unit: "/ 8 cups", icon: Droplets },
  { label: "Sleep", value: 7.2, max: 9, unit: "hrs last night", icon: Moon },
  { label: "Activity", value: 22, max: 30, unit: "min today", icon: Activity },
];

const TRIMESTER_LABEL: Record<number, string> = { 1: "First", 2: "Second", 3: "Third" };

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
    <main className="mx-auto w-full max-w-[1400px] px-6 py-10">
      {/* ---------- header ---------- */}
      <div className="rise-in flex flex-wrap items-start justify-between gap-6 border-b border-border pb-9">
        <div>
          <p className="eyebrow text-muted-foreground">
            {new Date().toLocaleDateString("en-US", { weekday: "long", day: "numeric", month: "long" })}
          </p>
          <h1 className="display mt-3 text-[2.25rem] leading-[1.02]">
            Good day{user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}.
          </h1>
        </div>
        {!loading && pregnancy && (
          <div className="mark border border-border px-4 py-2.5 text-foreground">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
            Week {pregnancy.current_week} of 40
          </div>
        )}
      </div>

      {/* ---------- the week ---------- */}
      <section aria-labelledby="progress-heading" className="border-b border-border py-10">
        <h2 id="progress-heading" className="sr-only">
          Your pregnancy progress
        </h2>

        {!loading && error && (
          <Alert variant="warning" className="mb-8">
            <AlertDescription>
              {error}{" "}
              <Link href="/onboarding" className="underline">
                Complete onboarding
              </Link>
            </AlertDescription>
          </Alert>
        )}

        <div className="grid gap-12 lg:grid-cols-[auto_1fr] lg:items-center">
          <div className="flex justify-center lg:justify-start">
            {loading ? (
              <div className="flex h-60 w-60 items-center justify-center border border-border bg-card">
                <LoadingState label="Loading..." />
              </div>
            ) : (
              <PregnancyVisualization trimester={trimester} currentWeek={week} variant="dashboard" />
            )}
          </div>

          {!loading && pregnancy && (
            <div>
              <p className="eyebrow text-accent">{TRIMESTER_LABEL[Math.min(3, Math.max(1, trimester))]} trimester</p>
              <p className="display mt-3 text-[2rem] capitalize leading-[1.1]">
                {pregnancy.stage.replace(/_/g, " ")}
              </p>
              <p className="mt-2 text-sm text-muted-foreground">
                {pregnancy.due_date ? `Due ${pregnancy.due_date}` : "Due date not yet set"} ·{" "}
                {pregnancy.first_pregnancy ? "first pregnancy" : "not the first pregnancy"}
              </p>

              <div className="mt-7 flex items-center gap-1.5">
                {Array.from({ length: 40 }).map((_, i) => (
                  <span
                    key={i}
                    className={`h-6 w-1 shrink-0 ${i < week ? "bg-accent" : "bg-sage-100"}`}
                  />
                ))}
              </div>
              <div className="eyebrow-sm mt-3 flex justify-between text-muted-foreground">
                <span>Trimester 1</span>
                <span>Trimester 2</span>
                <span>Trimester 3</span>
                <span>Delivery</span>
              </div>

              <p className="mt-6 text-sm text-muted-foreground">
                {progressPct}% of the way — {40 - week} weeks remaining.
              </p>
            </div>
          )}

          {!loading && !error && !pregnancy && (
            <p className="text-sm text-muted-foreground">Complete onboarding to see your progress here.</p>
          )}
        </div>
      </section>

      {/* ---------- baby development ---------- */}
      <section aria-labelledby="development-heading" className="border-b border-border py-10">
        <div className="mb-7 flex items-baseline justify-between">
          <h2 id="development-heading" className="eyebrow text-accent">
            Baby development
          </h2>
          <span className="eyebrow-sm text-muted-foreground">What&apos;s generally happening this trimester</span>
        </div>
        <div className="grid gap-px bg-border sm:grid-cols-3">
          {milestones.map((m, i) => (
            <div key={m.title} className="bg-background p-6">
              <span className="eyebrow-sm text-muted-foreground">{`0${i + 1}`}</span>
              <p className="display mt-3 text-xl leading-[1.2]">{m.title}</p>
              <p className="mt-2.5 text-sm leading-relaxed text-muted-foreground">{m.detail}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ---------- wellness ---------- */}
      <section aria-labelledby="wellness-heading" className="border-b border-border py-10">
        <div className="mb-7 flex items-baseline justify-between">
          <h2 id="wellness-heading" className="eyebrow text-accent">
            Mother&apos;s wellness
          </h2>
          <span className="eyebrow-sm text-muted-foreground">Illustrative — not connected to a tracker yet</span>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {MOCK_WELLNESS.map((w) => (
            <div key={w.label} className="border border-border p-5">
              <div className="flex items-center justify-between">
                <w.icon className="h-4 w-4 text-accent" aria-hidden="true" />
                <span className="eyebrow-sm text-muted-foreground">Sample</span>
              </div>
              <p className="eyebrow-sm mt-4 text-muted-foreground">{w.label}</p>
              <p className="display tabular mt-1 text-3xl">
                {w.value}
                <span className="text-xs font-sans font-normal text-muted-foreground"> {w.unit}</span>
              </p>
              <div className="mt-3 h-[3px] w-full bg-sage-100">
                <div
                  className="h-full bg-accent"
                  style={{ width: `${Math.min(100, (w.value / w.max) * 100)}%` }}
                />
              </div>
            </div>
          ))}

          <Link href="/nutrition" className="lift block border border-border p-5">
            <div className="flex items-center justify-between">
              <Apple className="h-4 w-4 text-accent" aria-hidden="true" />
              <span className="eyebrow-sm text-accent">Live</span>
            </div>
            <p className="display mt-4 text-xl leading-[1.2]">Nutrition</p>
            <p className="mt-2 text-sm text-muted-foreground">Evidence-checked food guidance for your stage →</p>
          </Link>
        </div>
      </section>

      {/* ---------- important information ---------- */}
      <section aria-labelledby="important-heading" className="border-b border-border py-10">
        <h2 id="important-heading" className="eyebrow mb-7 text-accent">
          Important information
        </h2>
        <div className="grid gap-4 md:grid-cols-3">
          <NextVisitCard />

          <Card>
            <CardHeader className="flex-row items-center gap-3 space-y-0 pb-0">
              <Pill className="h-4 w-4 text-accent" aria-hidden="true" />
              <CardEyebrowInline>Reminder</CardEyebrowInline>
            </CardHeader>
            <CardContent className="pt-3">
              <CardTitle className="text-lg">Vitamin & medication</CardTitle>
              <p className="mt-2 text-sm text-muted-foreground">
                Remember your prenatal vitamin (e.g. folic acid, iron) as advised by your provider.
              </p>
              <Badge variant="outline" className="mt-4">
                Sample reminder
              </Badge>
            </CardContent>
          </Card>

          <Card className="bg-ink text-cream-100">
            <CardHeader className="flex-row items-center gap-3 space-y-0 pb-0">
              <Stethoscope className="h-4 w-4 text-sage-300" aria-hidden="true" />
              <span className="eyebrow-sm text-sage-300">Always confirm</span>
            </CardHeader>
            <CardContent className="pt-3">
              <CardTitle className="text-lg text-cream-100">Talk to your doctor</CardTitle>
              <p className="mt-2 text-sm leading-relaxed text-cream-100/70">
                MATRIVA provides general, evidence-informed guidance. Always confirm anything important —
                symptoms, medication, or diet changes — with your own healthcare provider.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* ---------- quick links ---------- */}
      <section aria-labelledby="quicklinks-heading" className="py-10">
        <h2 id="quicklinks-heading" className="eyebrow mb-4 text-accent">
          Quick links
        </h2>
        <div>
          {quickLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="group flex items-center gap-5 border-b border-border py-4 transition-colors hover:bg-foreground/[0.02]"
            >
              <span className="eyebrow-sm w-6 text-accent">{link.index}</span>
              <link.icon className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              <span className="flex-1 text-[15px] font-medium">{link.label}</span>
              <span className="text-muted-foreground transition-transform group-hover:translate-x-1">→</span>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}

function CardEyebrowInline({ children }: { children: React.ReactNode }) {
  return <span className="eyebrow-sm text-muted-foreground">{children}</span>;
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardContent />
    </RequireAuth>
  );
}
