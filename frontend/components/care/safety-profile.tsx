"use client";

import * as React from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  BLOOD_GROUPS,
  CONDITION_OPTIONS,
  RISK_FACTOR_OPTIONS,
  type SafetyProfileState,
} from "@/lib/safety-profile";

function Checks({
  options,
  value,
  onChange,
  name,
}: {
  options: { value: string; label: string }[];
  value: string[];
  onChange: (next: string[]) => void;
  name: string;
}) {
  const toggle = (v: string) => onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v]);
  return (
    <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
      {options.map((o) => (
        <label key={o.value} className="flex min-h-9 cursor-pointer items-center gap-2.5 text-sm">
          <input
            type="checkbox"
            name={name}
            checked={value.includes(o.value)}
            onChange={() => toggle(o.value)}
            className="h-4 w-4 accent-[hsl(var(--accent))]"
          />
          {o.label}
        </label>
      ))}
    </div>
  );
}

/** The details the safety checks use. Everything here is optional, stays on the account, and can be deleted. */
export function SafetyProfileFields({
  value,
  onChange,
}: {
  value: SafetyProfileState;
  onChange: (next: SafetyProfileState) => void;
}) {
  const set = <K extends keyof SafetyProfileState>(key: K, v: SafetyProfileState[K]) => onChange({ ...value, [key]: v });
  return (
    <section className="border border-border p-8" aria-labelledby="safety-profile-heading">
      <p id="safety-profile-heading" className="eyebrow-sm text-accent">
        Safety profile
      </p>
      <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
        The more MATRIVA knows, the better it can warn you: about a medicine that does not suit pregnancy, or a symptom that matters because of
        your condition. Every field is optional, only you can see it, and it is removed if you delete your profile or withdraw consent.
      </p>

      <div className="mt-7 grid gap-7">
        <fieldset className="grid gap-3">
          <legend className="text-sm font-semibold">Health conditions</legend>
          <Checks name="condition" options={CONDITION_OPTIONS} value={value.conditions} onChange={(v) => set("conditions", v)} />
          <div className="mt-1 flex flex-col gap-1.5">
            <Label htmlFor="otherConditions">Anything else (separate with commas)</Label>
            <Input id="otherConditions" value={value.otherConditions} onChange={(e) => set("otherConditions", e.target.value)} />
          </div>
        </fieldset>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="medications">Medicines, tablets, injections and supplements you take now (one per line)</Label>
          <textarea
            id="medications"
            rows={4}
            value={value.medications}
            onChange={(e) => set("medications", e.target.value)}
            placeholder={"Thyronorm 50 mcg\nIron and folic acid tablet"}
            className="min-h-24 w-full border border-border bg-background px-3 py-2.5 text-sm leading-relaxed focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          />
          <p className="text-xs text-muted-foreground">
            Include herbal and Ayurvedic products. MATRIVA never tells you to start, stop or change a medicine; it uses this list only to warn you.
          </p>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="allergies">Allergies, to food or medicine (separate with commas)</Label>
          <Input
            id="allergies"
            value={value.allergies}
            onChange={(e) => set("allergies", e.target.value)}
            placeholder="penicillin, peanuts"
          />
        </div>

        <fieldset className="grid gap-3">
          <legend className="text-sm font-semibold">Pregnancy history and risks</legend>
          <Checks name="risk" options={RISK_FACTOR_OPTIONS} value={value.riskFactors} onChange={(v) => set("riskFactors", v)} />
        </fieldset>

        <div className="grid gap-6 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="age">Your age</Label>
            <Input id="age" type="number" min={10} max={60} value={value.age} onChange={(e) => set("age", e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="bloodGroup">Blood group</Label>
            <Select id="bloodGroup" value={value.bloodGroup} onChange={(e) => set("bloodGroup", e.target.value)}>
              <option value="">I do not know</option>
              {BLOOD_GROUPS.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </Select>
          </div>
        </div>
      </div>
    </section>
  );
}
