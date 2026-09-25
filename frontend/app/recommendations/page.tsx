"use client";

import * as React from "react";
import { RequireAuth } from "@/components/require-auth";
import { api, ApiError } from "@/lib/api";
import type { RecommendationResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
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
    <main className="mx-auto w-full max-w-[1400px] px-6 py-10">
      <div className="rise-in flex flex-wrap items-end justify-between gap-6 border-b border-border pb-9">
        <div>
          <p className="eyebrow text-accent">For you</p>
          <h1 className="display mt-3 text-[2.5rem] leading-none">Recommendations</h1>
          <p className="mt-3 max-w-md text-sm text-muted-foreground">
            Personalized suggestions based on your profile and pregnancy stage.
          </p>
        </div>
        <Button onClick={generate} disabled={generating}>
          <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
          {generating ? "Generating…" : "Generate new"}
        </Button>
      </div>

      {error && (
        <Alert variant="destructive" className="mt-8">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {loading && <LoadingState label="Loading recommendations..." />}
      {!loading && items.length === 0 && (
        <p className="mt-8 text-sm text-muted-foreground">
          No recommendations yet. Click &quot;Generate new&quot; to get personalized suggestions.
        </p>
      )}

      <div className="mt-8 grid gap-px bg-border sm:grid-cols-2">
        {items.map((item) => (
          <div key={item.id} className="bg-background p-7">
            <div className="flex items-start justify-between gap-4">
              <p className="eyebrow-sm text-accent">{item.domain}</p>
              <button
                type="button"
                aria-label={item.is_saved ? "Unsave" : "Save"}
                onClick={() => toggleSave(item)}
                className="shrink-0 text-accent transition-opacity hover:opacity-70"
              >
                {item.is_saved ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
              </button>
            </div>
            <h2 className="display mt-2.5 text-2xl leading-[1.15]">{item.title}</h2>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{item.description}</p>
            <p className="eyebrow-sm mt-4 text-accent">Why: {item.reason}</p>
            <div className="mt-5 flex flex-wrap gap-4 border-t border-border pt-4">
              <EvidenceBadge level={item.evidence_level} />
              <SafetyBadge status={item.safety_status} />
            </div>
          </div>
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
