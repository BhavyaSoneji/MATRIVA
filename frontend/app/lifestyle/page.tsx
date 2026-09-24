"use client";

import * as React from "react";
import { RequireAuth } from "@/components/require-auth";
import { api, ApiError } from "@/lib/api";
import type { LifestyleItem } from "@/lib/types";
import { Select } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EvidenceBadge, SafetyBadge } from "@/components/evidence-badge";

function LifestyleContent() {
  const [items, setItems] = React.useState<LifestyleItem[]>([]);
  const [category, setCategory] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback((cat: string) => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (cat) params.set("category", cat);
    api
      .get<LifestyleItem[]>(`/knowledge/lifestyle?${params.toString()}`)
      .then(setItems)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load lifestyle guidance."))
      .finally(() => setLoading(false));
  }, []);

  React.useEffect(() => {
    load("");
  }, [load]);

  const categories = Array.from(new Set(items.map((i) => i.category)));

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-10">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Lifestyle guidance</h1>
        <p className="text-muted-foreground">Exercise and lifestyle recommendations for pregnancy.</p>
      </div>
      <Select
        className="max-w-xs"
        value={category}
        onChange={(e) => {
          setCategory(e.target.value);
          load(e.target.value);
        }}
      >
        <option value="">All categories</option>
        {categories.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </Select>
      {loading && <LoadingState label="Loading lifestyle guidance..." />}
      {!loading && error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {!loading && !error && items.length === 0 && (
        <p className="text-sm text-muted-foreground">No lifestyle guidance found.</p>
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => (
          <Card key={item.id}>
            <CardHeader>
              <CardTitle className="text-base">{item.title}</CardTitle>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">{item.category}</p>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              <p className="text-sm text-foreground/90">{item.description}</p>
              {item.restrictions.length > 0 && (
                <p className="text-xs text-muted-foreground">Restrictions: {item.restrictions.join(", ")}</p>
              )}
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

export default function LifestylePage() {
  return (
    <RequireAuth>
      <LifestyleContent />
    </RequireAuth>
  );
}
