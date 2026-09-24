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
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";

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
    <main className="mx-auto flex max-w-lg flex-col justify-center px-4 py-16">
      <Card>
        <CardHeader>
          <CardTitle>Tell us about yourself ({step}/2)</CardTitle>
          <CardDescription>
            {step === 1 ? "A few quick details help us personalize your guidance." : "Now, your pregnancy details."}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {step === 1 ? (
            <>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="region">Region</Label>
                <Input id="region" placeholder="e.g. North India" value={region} onChange={(e) => setRegion(e.target.value)} />
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
              <div className="flex flex-col gap-1.5">
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
          <div className="flex justify-between">
            {step === 2 ? (
              <Button variant="outline" onClick={() => setStep(1)} disabled={loading}>
                Back
              </Button>
            ) : (
              <span />
            )}
            <Button onClick={handleNext} disabled={loading}>
              {loading ? "Saving..." : step === 1 ? "Next" : "Finish"}
            </Button>
          </div>
        </CardContent>
      </Card>
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
