"use client";

import * as React from "react";
import { RequireAuth } from "@/components/require-auth";
import { api, ApiError } from "@/lib/api";
import type { GuidelineResponse } from "@/lib/types";
import { LoadingState } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EvidenceBadge } from "@/components/evidence-badge";

function GuidanceContent() {
  const [guidelines, setGuidelines] = React.useState<GuidelineResponse[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    api
      .get<GuidelineResponse[]>("/guidelines")
      .then(setGuidelines)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load guidance."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="mx-auto w-full max-w-[1000px] px-6 py-10">
      <div className="rise-in border-b border-border pb-9">
        <p className="eyebrow text-accent">Guidance</p>
        <h1 className="display mt-3 text-[2.5rem] leading-none">Stage-wise guidance</h1>
        <p className="mt-3 text-sm text-muted-foreground">
          Official guidelines from recognized health authorities.
        </p>
      </div>

      {loading && <LoadingState label="Loading guidelines..." />}
      {!loading && error && (
        <Alert variant="destructive" className="mt-8">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {!loading && !error && guidelines.length === 0 && (
        <p className="mt-8 text-sm text-muted-foreground">No active guidelines found.</p>
      )}

      <div>
        {guidelines.map((g) => (
          <article
            key={g.id}
            className={`flex flex-wrap items-center justify-between gap-4 border-b border-l-2 border-border py-6 pl-6 transition-colors hover:bg-foreground/[0.02] ${
              g.status === "active" ? "border-l-sage-500" : "border-l-blush-500"
            }`}
          >
            <div>
              <div className="flex items-center gap-3">
                <h2 className="display text-xl leading-none">{g.authority}</h2>
                <span
                  className={`eyebrow-sm ${g.status === "active" ? "text-sage-600" : "text-blush-500"}`}
                >
                  {g.status === "active" ? "◆ Active" : `◇ ${g.status}`}
                </span>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                {g.jurisdiction} · {g.source.title}
              </p>
              <p className="eyebrow-sm mt-2 text-muted-foreground">
                {g.effective_date && <>Effective {g.effective_date}</>}
                {g.effective_date && g.version && <> · </>}
                {g.version && <>Version {g.version}</>}
              </p>
            </div>
            <EvidenceBadge level={g.source.evidence_level} />
          </article>
        ))}
      </div>
    </main>
  );
}

export default function GuidancePage() {
  return (
    <RequireAuth>
      <GuidanceContent />
    </RequireAuth>
  );
}
