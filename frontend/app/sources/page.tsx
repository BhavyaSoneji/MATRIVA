"use client";

import * as React from "react";
import { RequireAuth } from "@/components/require-auth";
import { api, ApiError } from "@/lib/api";
import type { KnowledgeSearchResponse, KnowledgeResult, SourceResponse } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EvidenceBadge } from "@/components/evidence-badge";
import { ArrowUpRight } from "lucide-react";

function SourcesContent() {
  const [query, setQuery] = React.useState("");
  const [results, setResults] = React.useState<KnowledgeResult[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [activeId, setActiveId] = React.useState<string | null>(null);
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
    setActiveId(sourceId);
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
    <main className="mx-auto w-full max-w-[1400px] px-6 py-10">
      <div className="rise-in border-b border-border pb-9">
        <p className="eyebrow text-accent">Evidence</p>
        <h1 className="display mt-3 text-[2.5rem] leading-none">Sources & evidence explorer</h1>
        <p className="mt-3 text-sm text-muted-foreground">
          Browse the underlying sources behind MATRIVA&apos;s guidance.
        </p>
      </div>

      <form
        className="mt-8 max-w-sm"
        onSubmit={(e) => {
          e.preventDefault();
          search(query);
        }}
      >
        <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search topics or keywords…" />
      </form>

      {loading && <LoadingState label="Loading sources..." />}
      {!loading && error && (
        <Alert variant="destructive" className="mt-8">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {!loading && !error && uniqueSources.length === 0 && (
        <p className="mt-8 text-sm text-muted-foreground">No sources found.</p>
      )}

      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_1.1fr]">
        <div className="flex flex-col">
          {uniqueSources.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => openDetail(s.id)}
              className={`flex items-center justify-between gap-4 border-b border-border px-4 py-4 text-left transition-colors first:border-t ${
                activeId === s.id ? "bg-sage-100" : "hover:bg-foreground/[0.02]"
              }`}
            >
              <div>
                <p className="display text-lg leading-[1.2]">{s.title || s.name}</p>
                <p className="eyebrow-sm mt-1.5 text-muted-foreground">{s.source_type}</p>
              </div>
              <EvidenceBadge level={s.evidence_level} />
            </button>
          ))}
        </div>

        <div>
          {detailError && (
            <Alert variant="destructive">
              <AlertDescription>{detailError}</AlertDescription>
            </Alert>
          )}
          {!detailError && !detail && (
            <div className="flex h-full min-h-[16rem] items-center justify-center border border-dashed border-border p-8 text-center">
              <p className="text-sm text-muted-foreground">Select a source to see its detail.</p>
            </div>
          )}
          {detail && (
            <div className="bg-ink p-9 text-cream-100">
              <p className="eyebrow-sm text-sage-300">{detail.authority || "Source"}</p>
              <h2 className="display mt-3 text-[1.7rem] leading-[1.25]">{detail.title}</h2>

              <dl className="mt-7 flex flex-wrap gap-8">
                <div>
                  <dt className="eyebrow-sm text-cream-100/55">Jurisdiction</dt>
                  <dd className="mt-1.5 text-sm font-semibold">{detail.jurisdiction || "—"}</dd>
                </div>
                <div>
                  <dt className="eyebrow-sm text-cream-100/55">Topic</dt>
                  <dd className="mt-1.5 text-sm font-semibold">{detail.topic || "—"}</dd>
                </div>
              </dl>

              <div className="mt-8 flex items-center justify-between border-t border-cream-100/15 pt-6">
                <EvidenceBadge level={detail.evidence_level} />
                {detail.url && (
                  <a
                    href={detail.url}
                    target="_blank"
                    rel="noreferrer"
                    className="eyebrow-sm flex items-center gap-1.5 text-cream-100 transition-opacity hover:opacity-75"
                  >
                    View original source
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  </a>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
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
