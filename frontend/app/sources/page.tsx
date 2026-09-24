"use client";

import * as React from "react";
import { RequireAuth } from "@/components/require-auth";
import { api, ApiError } from "@/lib/api";
import type { KnowledgeSearchResponse, KnowledgeResult, SourceResponse } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EvidenceBadge } from "@/components/evidence-badge";

function SourcesContent() {
  const [query, setQuery] = React.useState("");
  const [results, setResults] = React.useState<KnowledgeResult[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [detail, setDetail] = React.useState<SourceResponse | null>(null);
  const [detailError, setDetailError] = React.useState<string | null>(null);

  const search = React.useCallback((q: string) => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ query: q });
    api
      .get<KnowledgeSearchResponse>(`/knowledge/search?${params.toString()}`)
      .then((res) => setResults(res.results))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not search sources."))
      .finally(() => setLoading(false));
  }, []);

  React.useEffect(() => {
    search("");
  }, [search]);

  const openDetail = async (sourceId: string) => {
    setDetailError(null);
    setDetail(null);
    try {
      const res = await api.get<SourceResponse>(`/sources/${sourceId}`);
      setDetail(res);
    } catch (err) {
      setDetailError(err instanceof ApiError ? err.message : "Could not load source detail.");
    }
  };

  const uniqueSources = React.useMemo(() => {
    const map = new Map<string, SourceResponse>();
    results.forEach((r) => map.set(r.source.id, r.source));
    return Array.from(map.values());
  }, [results]);

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-10">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Sources & evidence explorer</h1>
        <p className="text-muted-foreground">Browse the underlying sources behind MATRIVA&apos;s guidance.</p>
      </div>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          search(query);
        }}
      >
        <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search topics or keywords..." />
        <Button type="submit">Search</Button>
      </form>
      {loading && <LoadingState label="Loading sources..." />}
      {!loading && error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {!loading && !error && uniqueSources.length === 0 && (
        <p className="text-sm text-muted-foreground">No sources found.</p>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {uniqueSources.map((s) => (
          <Card key={s.id} className="cursor-pointer hover:border-primary" onClick={() => openDetail(s.id)}>
            <CardHeader>
              <CardTitle className="text-base">{s.title || s.name}</CardTitle>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">{s.source_type}</p>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-1.5">
              <EvidenceBadge level={s.evidence_level} />
            </CardContent>
          </Card>
        ))}
      </div>

      {detailError && (
        <Alert variant="destructive">
          <AlertDescription>{detailError}</AlertDescription>
        </Alert>
      )}
      {detail && (
        <Card className="border-primary">
          <CardHeader>
            <CardTitle>{detail.title}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 text-sm">
            <p>Authority: {detail.authority || "—"}</p>
            <p>Jurisdiction: {detail.jurisdiction || "—"}</p>
            <p>Topic: {detail.topic || "—"}</p>
            {detail.url && (
              <a href={detail.url} target="_blank" rel="noreferrer" className="text-primary underline">
                View source
              </a>
            )}
            <EvidenceBadge level={detail.evidence_level} />
          </CardContent>
        </Card>
      )}
    </main>
  );
}

export default function SourcesPage() {
  return (
    <RequireAuth>
      <SourcesContent />
    </RequireAuth>
  );
}
