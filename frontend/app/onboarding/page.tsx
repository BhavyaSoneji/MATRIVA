"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/components/require-auth";
import { api, ApiError } from "@/lib/api";
import type { ProfileUpdateRequest, PregnancyUpdateRequest } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";

function StepDot({ n, active, done }: { n: number; active: boolean; done: boolean }) {
  return (
    <span
      className={`flex h-7 w-7 items-center justify-center text-[13px] font-bold ${
        active || done ? "bg-accent text-primary-foreground" : "bg-sage-100 text-accent"
      } ${active ? "animate-pulse-soft" : ""}`}
    >
      {n}
    </span>
  );
}

function OnboardingFlow() {
  const router = useRouter();
  const [step, setStep] = React.useState(1);
  const [region, setRegion] = React.useState("");
  const [dietType, setDietType] = React.useState("vegetarian");
  const [language, setLanguage] = React.useState("en");
  const [currentWeek, setCurrentWeek] = React.useState(8);
  const [dueDate, setDueDate] = React.useState("");
  const [firstPregnancy, setFirstPregnancy] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);

  const submitProfile = async () => {
    const payload: ProfileUpdateRequest = {
      consent: true,
      region: region || undefined,
      diet_type: dietType,
      language,
    };
    await api.put("/profile", payload);
  };

  const submitPregnancy = async () => {
    const payload: PregnancyUpdateRequest = {
      current_week: currentWeek,
      due_date: dueDate || undefined,
      first_pregnancy: firstPregnancy,
    };
    await api.put("/pregnancy", payload);
  };

  const handleNext = async () => {
    setError(null);
    if (step === 1) {
      setStep(2);
      return;
    }
    setLoading(true);
    try {
      await submitProfile();
      await submitPregnancy();
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong saving your details.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="relative flex min-h-[calc(100vh-4rem)] items-center justify-center overflow-hidden px-6 py-16">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-[-14rem] h-[44rem] w-[44rem] -translate-x-1/2 animate-breathe rounded-full bg-[radial-gradient(circle,hsl(var(--sage-200)/0.5),transparent_70%)]"
      />

      <div className="relative w-full max-w-[38rem] border border-border bg-card p-11 shadow-plate">
        <div className="flex items-center gap-2.5">
          <StepDot n={1} active={step === 1} done={step > 1} />
          <span className="h-px w-10 bg-border" />
          <StepDot n={2} active={step === 2} done={false} />
          <span className="eyebrow-sm ml-3 text-muted-foreground">
            {step === 1 ? "About you · 1 of 2" : "Your pregnancy · 2 of 2"}
          </span>
        </div>

        <h1 className="display mt-7 text-[1.9rem] leading-[1.1]">
          {step === 1 ? "A little about you" : "Where things stand"}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {step === 1
            ? "This shapes the guidance we show you — nothing here is shared without consent."
            : "So the dashboard can speak to exactly where you are."}
        </p>

        {error && (
          <Alert variant="destructive" className="mt-6">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="mt-9 grid gap-6 sm:grid-cols-2">
          {step === 1 ? (
            <>
              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <Label htmlFor="region">Region</Label>
                <Input
                  id="region"
                  placeholder="e.g. South India"
                  value={region}
                  onChange={(e) => setRegion(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="diet">Dietary preference</Label>
                <Select id="diet" value={dietType} onChange={(e) => setDietType(e.target.value)}>
                  <option value="vegetarian">Vegetarian</option>
                  <option value="vegan">Vegan</option>
                  <option value="non_vegetarian">Non-vegetarian</option>
                  <option value="eggetarian">Eggetarian</option>
                </Select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="language">Preferred language</Label>
                <Select id="language" value={language} onChange={(e) => setLanguage(e.target.value)}>
                  <option value="en">English</option>
                  <option value="hi">Hindi</option>
                  <option value="ta">Tamil</option>
                  <option value="te">Telugu</option>
                  <option value="bn">Bengali</option>
                </Select>
              </div>
            </>
          ) : (
            <>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="week">Current pregnancy week</Label>
                <Input
                  id="week"
                  type="number"
                  min={1}
                  max={42}
                  value={currentWeek}
                  onChange={(e) => setCurrentWeek(Number(e.target.value))}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="dueDate">Due date (optional)</Label>
                <Input id="dueDate" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <Label htmlFor="first">Is this your first pregnancy?</Label>
                <Select
                  id="first"
                  value={firstPregnancy ? "yes" : "no"}
                  onChange={(e) => setFirstPregnancy(e.target.value === "yes")}
                >
                  <option value="yes">Yes</option>
                  <option value="no">No</option>
                </Select>
              </div>
            </>
          )}
        </div>

        <div className="mt-11 flex items-center justify-between border-t border-border pt-7">
          {step === 2 ? (
            <button
              type="button"
              onClick={() => setStep(1)}
              disabled={loading}
              className="eyebrow-sm text-muted-foreground transition-colors hover:text-accent disabled:opacity-50"
            >
              ← Back
            </button>
          ) : (
            <span />
          )}
          <Button onClick={handleNext} disabled={loading}>
            {loading ? "Saving…" : step === 1 ? "Next" : "Finish"}
          </Button>
        </div>
      </div>
    </main>
  );
}

export default function OnboardingPage() {
  return (
    <RequireAuth>
      <OnboardingFlow />
    </RequireAuth>
  );
}
