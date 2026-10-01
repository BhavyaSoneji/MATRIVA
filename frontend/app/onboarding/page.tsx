"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/components/require-auth";
import { api, ApiError } from "@/lib/api";
import type { ProfileUpdateRequest, PregnancyUpdateRequest } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";

const CONSENT_VERSION = "v1.0";

/** One screen, three questions. Everything else (region, conditions, allergies, due date) can be
 * added later in Settings or just mentioned in the chat. */
function OnboardingFlow() {
  const router = useRouter();
  const [currentWeek, setCurrentWeek] = React.useState(12);
  const [dietType, setDietType] = React.useState("vegetarian");
  const [language, setLanguage] = React.useState("en");
  const [how, setHow] = React.useState<"week" | "lmp" | "edd">("week");
  const [dateStr, setDateStr] = React.useState("");
  const [notFirst, setNotFirst] = React.useState(false);
  const [consent, setConsent] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);

  const weekValid = Number.isInteger(currentWeek) && currentWeek >= 1 && currentWeek <= 42;

  const datingValid = how === "week" ? weekValid : dateStr !== "";

  const handleFinish = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!consent || !datingValid) return;
    setError(null);
    setLoading(true);
    try {
      const profile: ProfileUpdateRequest = {
        consent: true,
        consent_version: CONSENT_VERSION,
        diet_type: dietType,
        language,
      };
      await api.put("/profile", profile);
      if (how === "week") {
        const pregnancy: PregnancyUpdateRequest = { current_week: currentWeek, first_pregnancy: !notFirst };
        await api.put("/pregnancy", pregnancy);
      } else {
        // exact dates give an exact week, visit calendar and reminders
        await api.put("/care/dating", { [how === "lmp" ? "lmp_date" : "edd_date"]: dateStr, first_pregnancy: !notFirst });
      }
      router.push("/chat");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong saving your details.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="relative flex min-h-[calc(100vh-4rem)] items-center justify-center overflow-hidden px-6 py-12">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-[-14rem] h-[44rem] w-[44rem] -translate-x-1/2 animate-breathe rounded-full bg-[radial-gradient(circle,hsl(var(--sage-200)/0.5),transparent_70%)]"
      />

      <form onSubmit={handleFinish} className="relative w-full max-w-[34rem] border border-border bg-card p-8 shadow-plate sm:p-11">
        <p className="eyebrow-sm text-accent">Three quick questions</p>
        <h1 className="display mt-3 text-[1.9rem] leading-[1.1]">Let&apos;s tailor MATRIVA to you</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          You can tell the companion anything else as you chat, or add it later in Settings.
        </p>

        {error && (
          <Alert variant="destructive" className="mt-6">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="mt-8 flex flex-col gap-6">
          <div className="flex flex-col gap-1.5">
            <div className="flex flex-wrap gap-2" role="group" aria-label="How do you want to tell us?">
              {([["week", "I know my week"], ["lmp", "Last period date"], ["edd", "Due date"]] as const).map(([k, l]) => (
                <button key={k} type="button" aria-pressed={how === k} onClick={() => setHow(k)}
                  className={`eyebrow-sm min-h-9 border px-3 ${how === k ? "border-accent text-accent" : "border-border text-muted-foreground"}`}>{l}</button>
              ))}
            </div>
            {how !== "week" && (
              <input type="date" aria-label={how === "lmp" ? "First day of your last period" : "Your due date"} value={dateStr} onChange={(e) => setDateStr(e.target.value)} className="h-11 border border-border bg-transparent px-3 text-base" />
            )}
          </div>

          <div className={`flex flex-col gap-1.5 ${how !== "week" ? "hidden" : ""}`}>
            <Label htmlFor="week">How many weeks pregnant are you?</Label>
            <div className="flex items-center gap-4">
              <input
                id="week-range"
                aria-label="Pregnancy week slider"
                type="range"
                min={1}
                max={42}
                value={weekValid ? currentWeek : 12}
                onChange={(e) => setCurrentWeek(Number(e.target.value))}
                className="h-2 flex-1 accent-[hsl(var(--accent))]"
              />
              <input
                id="week"
                type="number"
                min={1}
                max={42}
                inputMode="numeric"
                value={Number.isNaN(currentWeek) ? "" : currentWeek}
                onChange={(e) => setCurrentWeek(e.target.value === "" ? NaN : Number(e.target.value))}
                className="h-11 w-20 border border-border bg-transparent px-3 text-center text-base"
              />
            </div>
            {!weekValid && <p className="text-xs text-destructive">Enter a week between 1 and 42.</p>}
          </div>

          <div className="grid gap-6 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="diet">What do you eat?</Label>
              <Select id="diet" value={dietType} onChange={(e) => setDietType(e.target.value)}>
                <option value="vegetarian">Vegetarian</option>
                <option value="vegan">Vegan</option>
                <option value="non_vegetarian">Non-vegetarian</option>
                <option value="eggetarian">Eggetarian</option>
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="language">Answer me in</Label>
              <Select id="language" value={language} onChange={(e) => setLanguage(e.target.value)}>
                <option value="en">English</option>
                <option value="hi">हिन्दी (Hindi)</option>
                <option value="gu">ગુજરાતી (Gujarati)</option>
              </Select>
            </div>
          </div>

          <label className="flex items-center gap-3 text-sm text-muted-foreground">
            <input type="checkbox" checked={notFirst} onChange={(e) => setNotFirst(e.target.checked)} className="h-4 w-4" />
            This is not my first pregnancy
          </label>

          <label className="flex items-start gap-3 border-t border-border pt-5 text-[13px] leading-relaxed text-muted-foreground">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              className="mt-0.5 h-4 w-4 shrink-0"
              required
            />
            <span>
              I agree that MATRIVA stores these details to personalise guidance. They are only used to answer my
              questions, and I can export or delete them any time in Settings.
            </span>
          </label>
        </div>

        <div className="mt-8 flex justify-end">
          <Button type="submit" size="lg" disabled={loading || !consent || !datingValid}>
            {loading ? "Saving…" : "Start chatting"}
          </Button>
        </div>
      </form>
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
