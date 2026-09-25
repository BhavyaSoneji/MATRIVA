"use client";

import * as React from "react";
import Image from "next/image";
import { RequireAuth } from "@/components/require-auth";
import { api, ApiError } from "@/lib/api";
import type { FoodItem } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EvidenceBadge, SafetyBadge } from "@/components/evidence-badge";

function NutritionContent() {
  const [items, setItems] = React.useState<FoodItem[]>([]);
  const [query, setQuery] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback((q: string) => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (q) params.set("query", q);
    api
      .get<FoodItem[]>(`/knowledge/food?${params.toString()}`)
      .then(setItems)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load food items."))
      .finally(() => setLoading(false));
  }, []);

  React.useEffect(() => {
    load("");
  }, [load]);

  return (
    <main className="mx-auto w-full max-w-[1400px] px-6 py-10">
      <div className="flex flex-wrap items-end justify-between gap-8 border-b border-border pb-9">
        <div className="rise-in">
          <p className="eyebrow text-accent">Nutrition</p>
          <h1 className="display mt-3 max-w-lg text-[2.75rem] leading-[0.98]">
            Eat for the <span className="italic">blood you are making.</span>
          </h1>
        </div>
        <div className="hidden w-64 shrink-0 overflow-hidden border border-border sm:block">
          <Image
            src="/plates/nutrition.jpg"
            alt="Illustration of foods that support pregnancy nutrition"
            width={640}
            height={360}
            className="h-28 w-full object-cover"
          />
        </div>
      </div>

      <div className="mt-8 max-w-sm">
        <Input
          placeholder="Search foods — papaya, spinach, ragi…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load(query)}
        />
      </div>

      {loading && <LoadingState label="Loading food items..." />}
      {!loading && error && (
        <Alert variant="destructive" className="mt-8">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {!loading && !error && items.length === 0 && (
        <p className="mt-8 text-sm text-muted-foreground">No food items found.</p>
      )}

      {!loading && !error && items.length > 0 && (
        <div className="mt-4">
          <div className="eyebrow-sm hidden justify-between border-b border-foreground pb-3 text-foreground sm:flex">
            <span>Food</span>
            <span>Evidence</span>
          </div>
          {items.map((item, i) => (
            <article
              key={item.id}
              className="grid gap-2 border-b border-border py-6 transition-colors hover:bg-foreground/[0.02] sm:grid-cols-[2.5rem_1fr_2fr_auto] sm:items-baseline sm:gap-6"
            >
              <span className="eyebrow-sm hidden text-muted-foreground sm:block">
                {String(i + 1).padStart(2, "0")}
              </span>
              <div>
                <p className="display text-[1.5rem] leading-[1.1]">{item.name}</p>
                {item.region && <p className="eyebrow-sm mt-1.5 text-accent">{item.region}</p>}
              </div>
              {item.pregnancy_context && (
                <p className="text-sm leading-relaxed text-muted-foreground">{item.pregnancy_context}</p>
              )}
              <div className="flex flex-wrap gap-3 sm:flex-col sm:items-end sm:gap-1.5">
                <EvidenceBadge level={item.evidence_status} />
                <SafetyBadge status={item.safety_status} />
              </div>
            </article>
          ))}
        </div>
      )}
    </main>
  );
}

export default function NutritionPage() {
  return (
    <RequireAuth>
      <NutritionContent />
    </RequireAuth>
  );
}
