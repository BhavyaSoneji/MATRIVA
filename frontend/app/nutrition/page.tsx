"use client";

import * as React from "react";
import { RequireAuth } from "@/components/require-auth";
import { api, ApiError } from "@/lib/api";
import type { FoodItem } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-10">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Nutrition guidance</h1>
        <p className="text-muted-foreground">Foods and their pregnancy-safety context, filtered by search.</p>
      </div>
      <Input
        placeholder="Search foods (e.g. papaya, spinach)..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && load(query)}
      />
      {loading && <LoadingState label="Loading food items..." />}
      {!loading && error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {!loading && !error && items.length === 0 && (
        <p className="text-sm text-muted-foreground">No food items found.</p>
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => (
          <Card key={item.id}>
            <CardHeader>
              <CardTitle className="text-base">{item.name}</CardTitle>
              {item.region && <p className="text-xs text-muted-foreground">{item.region}</p>}
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {item.pregnancy_context && <p className="text-sm text-foreground/90">{item.pregnancy_context}</p>}
              <div className="flex flex-wrap gap-1.5">
                <EvidenceBadge level={item.evidence_status} />
                <SafetyBadge status={item.safety_status} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
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
