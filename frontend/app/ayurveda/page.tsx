"use client";

import * as React from "react";
import { RequireAuth } from "@/components/require-auth";
import { api, ApiError } from "@/lib/api";
import type { KnowledgeSearchResponse, KnowledgeResult } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
    <main className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-10">
      <div className="flex items-center gap-2">
        <Sprout className="h-6 w-6 text-primary" />
        <h1 className="text-2xl font-semibold text-foreground">Ayurveda & traditional knowledge</h1>
      </div>
      <Alert variant="warning">
        <AlertTitle>Traditional knowledge, not a medical guarantee</AlertTitle>
        <AlertDescription>
          Content on this page reflects traditional and Ayurvedic sources. It is labeled as such and is never
          presented as equivalent to modern clinical evidence. Always consult your doctor before acting on it.
        </AlertDescription>
      </Alert>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          search(query);
        }}
      >
        <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search Ayurvedic topics..." />
        <Button type="submit">Search</Button>
      </form>
      {loading && <LoadingState label="Searching traditional sources..." />}
      {!loading && error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {!loading && !error && results.length === 0 && (
        <p className="text-sm text-muted-foreground">No Ayurvedic content found for this search.</p>
      )}
      <div className="flex flex-col gap-4">
        {results.map((r) => (
          <Card key={r.chunk_id}>
            <CardHeader>
              <CardTitle className="text-base">{r.document_title}</CardTitle>
              <div className="flex flex-wrap gap-1.5">
                <EvidenceBadge level={r.source.evidence_level} />
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-foreground/90">{r.content}</p>
              <p className="mt-2 text-xs text-muted-foreground">Source: {r.source.title || r.source.name}</p>
            </CardContent>
          </Card>
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
