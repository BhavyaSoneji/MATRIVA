"use client";

import * as React from "react";
import { RequireAuth } from "@/components/require-auth";
import { api, ApiError } from "@/lib/api";
import type { RecommendationResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EvidenceBadge, SafetyBadge } from "@/components/evidence-badge";
import { Bookmark, BookmarkCheck, Sparkles } from "lucide-react";

function RecommendationsContent() {
  const [items, setItems] = React.useState<RecommendationResponse[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [generating, setGenerating] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(() => {
    setLoading(true);
    api
      .get<RecommendationResponse[]>("/recommendations")
      .then(setItems)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load recommendations."))
      .finally(() => setLoading(false));
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const generate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const res = await api.post<RecommendationResponse[]>("/recommendations/generate", { limit: 5 });
      setItems((prev) => {
        const existingIds = new Set(prev.map((p) => p.id));
        return [...res.filter((r) => !existingIds.has(r.id)), ...prev];
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not generate recommendations.");
    } finally {
      setGenerating(false);
    }
  };

  const toggleSave = async (item: RecommendationResponse) => {
    try {
      if (item.is_saved) {
        await api.delete(`/recommendations/${item.id}/save`);
      } else {
        await api.post(`/recommendations/${item.id}/save`);
      }
      setItems((prev) => prev.map((p) => (p.id === item.id ? { ...p, is_saved: !p.is_saved } : p)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update saved status.");
    }
  };

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Recommendations</h1>
          <p className="text-muted-foreground">Personalized suggestions based on your profile and pregnancy stage.</p>
        </div>
        <Button onClick={generate} disabled={generating}>
          <Sparkles className="mr-1.5 h-4 w-4" />
          {generating ? "Generating..." : "Generate new"}
        </Button>
      </div>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {loading && <LoadingState label="Loading recommendations..." />}
      {!loading && items.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No recommendations yet. Click &quot;Generate new&quot; to get personalized suggestions.
        </p>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {items.map((item) => (
          <Card key={item.id}>
            <CardHeader className="flex flex-row items-start justify-between space-y-0">
              <div>
                <CardTitle className="text-base">{item.title}</CardTitle>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">{item.domain}</p>
              </div>
              <button
                aria-label={item.is_saved ? "Unsave" : "Save"}
                onClick={() => toggleSave(item)}
                className="text-primary hover:opacity-70"
              >
                {item.is_saved ? <BookmarkCheck className="h-5 w-5" /> : <Bookmark className="h-5 w-5" />}
              </button>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              <p className="text-sm text-foreground/90">{item.description}</p>
              <p className="text-xs text-muted-foreground">Why: {item.reason}</p>
              <div className="flex flex-wrap gap-1.5">
                <EvidenceBadge level={item.evidence_level} />
                <SafetyBadge status={item.safety_status} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </main>
  );
}

export default function RecommendationsPage() {
  return (
    <RequireAuth>
      <RecommendationsContent />
    </RequireAuth>
  );
}
