"use client";

import * as React from "react";
import { RequireAuth } from "@/components/require-auth";
import { api, ApiError } from "@/lib/api";
import type { KnowledgeSearchResponse, KnowledgeResult } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EvidenceBadge } from "@/components/evidence-badge";
import { Sprout } from "lucide-react";

function AyurvedaContent() {
  const [query, setQuery] = React.useState("pregnancy");
  const [results, setResults] = React.useState<KnowledgeResult[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const search = React.useCallback((q: string) => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ query: q, domain: "ayurveda" });
    api
      .get<KnowledgeSearchResponse>(`/knowledge/search?${params.toString()}`)
      .then((res) => setResults(res.results))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load Ayurvedic knowledge."))
      .finally(() => setLoading(false));
  }, []);

  React.useEffect(() => {
    search(query);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="mx-auto w-full max-w-[1000px] px-6 py-10">
      <div className="rise-in flex items-center gap-3.5 border-b border-border pb-9">
        <Sprout className="h-6 w-6 text-accent" aria-hidden="true" />
        <h1 className="display text-[2.5rem] leading-none">Ayurvedic wisdom</h1>
      </div>

      <div className="mt-7 flex items-start gap-3.5 border-l-2 border-blush-500 bg-blush-100 px-5 py-4">
        <span className="eyebrow-sm shrink-0 pt-0.5 text-blush-500">▲</span>
        <div>
          <p className="eyebrow-sm text-blush-500">Traditional knowledge, not a medical guarantee</p>
          <p className="mt-1.5 text-sm leading-relaxed text-foreground/80">
            Content here reflects traditional and Ayurvedic sources. It is labeled as such and never presented
            as equivalent to clinical evidence — always consult your doctor before acting on it.
          </p>
        </div>
      </div>

      <form
        className="mt-8 flex gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          search(query);
        }}
      >
        <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search rituals, herbs, practices…" />
        <Button type="submit" className="shrink-0">
          Search
        </Button>
      </form>

      {loading && <LoadingState label="Searching traditional sources..." />}
      {!loading && error && (
        <Alert variant="destructive" className="mt-8">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {!loading && !error && results.length === 0 && (
        <p className="mt-8 text-sm text-muted-foreground">No Ayurvedic content found for this search.</p>
      )}

      <div className="mt-2">
        {results.map((r) => (
          <article key={r.chunk_id} className="border-b border-border py-8">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h2 className="display text-2xl leading-[1.2]">{r.document_title}</h2>
              <EvidenceBadge level={r.source.evidence_level} />
            </div>
            <p className="mt-3 max-w-3xl text-[15px] leading-relaxed text-foreground/85">{r.content}</p>
            <p className="eyebrow-sm mt-4 text-accent">
              Source: {r.source.title || r.source.name}
            </p>
          </article>
        ))}
      </div>
    </main>
  );
}

export default function AyurvedaPage() {
  return (
    <RequireAuth>
      <AyurvedaContent />
    </RequireAuth>
  );
}
